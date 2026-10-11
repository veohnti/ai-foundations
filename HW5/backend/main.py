"""Campus Customs desk API (FastAPI).

Start from backend/:  uvicorn main:app --reload --port 8000

Every shop read and write goes through the campus-customs MCP server (one
connection, opened for the app's lifetime). Agents run in the background so the
board can poll /events while they work. Agents only prepare payments and
purchase orders; POST /approvals/{id}/approve is what actually moves cash.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agents import MODEL_NAME, shop_mcp
from audit import AUDIT_PATH, AuditTrail
from models import ApprovalDecisionIn
from run_team import first_pass_task, follow_up_task, work_ticket

DEFAULT_APPROVER = os.getenv("APPROVER_NAME", "Veohnti")

# One agent run at a time: runs share the database, and reset must not race a run.
RUNS: dict[str, dict] = {}
_run_lock = asyncio.Lock()
_tasks: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with shop_mcp:
        yield


app = FastAPI(title="Campus Customs Desk API", lifespan=lifespan)
# Let the Vite dashboard (npm run dev) call these routes from the browser.
FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["GET", "POST"],
                   allow_headers=["*"])


async def mcp(tool: str, args: dict | None = None) -> dict:
    return await shop_mcp.direct_call_tool(tool, args or {})


def _api_audit() -> AuditTrail:
    return AuditTrail(f"api-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}")


def _active_run() -> dict | None:
    return next((r for r in RUNS.values() if r["state"] == "running"), None)


# (a) tickets -----------------------------------------------------------------

@app.get("/tickets")
async def list_tickets():
    """All tickets with status and is_open / is_resolved."""
    data = await mcp("list_open_tickets", {"include_resolved": True})
    return {"desk_date_today": data["desk_date_today"], "tickets": data["tickets"]}


# (b) run the team on one ticket ----------------------------------------------------

async def _run_ticket(run_id: str, ticket_id: int, task: str) -> None:
    audit = AuditTrail(run_id)
    run = RUNS[run_id]
    async with _run_lock:
        audit.log("run_started", ticket_id=ticket_id, mode=run["mode"], model=MODEL_NAME, source="api")
        try:
            decision = await work_ticket(ticket_id, task, audit, run_id)
            run["state"] = "finished" if decision else "stopped"
            run["decision"] = decision.model_dump() if decision else None
        except Exception as e:  # keep the API alive; the error is in the audit trail
            run["state"], run["error"] = "failed", f"{type(e).__name__}: {e}"
            audit.log("run_failed", ticket_id=ticket_id, error=run["error"])
        run["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        audit.log("run_finished", ticket_id=ticket_id, state=run["state"])


@app.post("/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int, mode: Literal["auto", "first_pass", "follow_up"] = "auto"):
    """Start the agent team on one ticket. Returns a run_id; poll /events?run_id=... for progress.

    mode=auto runs a follow-up if the ticket is waiting_on_approval and nothing is still
    pending (the human has decided), otherwise a first pass. This does not reset the database.
    """
    if (active := _active_run()):
        raise HTTPException(409, f"Run {active['run_id']} on ticket {active['ticket_id']} is still running.")
    linked = await mcp("get_ticket_with_links", {"ticket_id": ticket_id})
    if not linked.get("found"):
        raise HTTPException(404, linked.get("message", f"No ticket {ticket_id}."))
    if mode == "auto":
        pending = (await mcp("list_approval_requests", {"status": "pending", "ticket_id": ticket_id}))["approvals"]
        mode = "follow_up" if linked["ticket"]["status"] == "waiting_on_approval" and not pending else "first_pass"
    task = follow_up_task(ticket_id) if mode == "follow_up" else first_pass_task(ticket_id)

    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    RUNS[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "mode": mode, "state": "running",
                    "started_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    t = asyncio.create_task(_run_ticket(run_id, ticket_id, task))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    return {"run_id": run_id, "ticket_id": ticket_id, "mode": mode, "state": "running",
            "events_url": f"/events?run_id={run_id}"}


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    """State of one run: running, finished, stopped, or failed (plus the boss's decision)."""
    if run_id not in RUNS:
        raise HTTPException(404, f"No run {run_id} since the server started.")
    return RUNS[run_id]


# (c) agent events for the board -----------------------------------------------------

BOARD_EVENTS = {"run_started", "agent_started", "agent_step", "tool_called", "agent_finished", "agent_failed",
                "agent_stopped_budget", "ticket_stopped", "run_failed", "run_finished",
                "human_decision", "database_reset"}


def _said(event: dict) -> str | None:
    out = event.get("output") or {}
    return out.get("final_decision") or out.get("summary")


@app.get("/events")
async def events(run_id: str | None = None, ticket_id: int | None = None, after: int = 0):
    """What each agent was asked, which tools it called (with results), and what it said.

    Reads output/audit_trail.json. Pass after=<next> from the previous response to
    get only new events, so the board can refresh cheaply.
    """
    if not AUDIT_PATH.exists():
        return {"events": [], "next": 0, "runs": list(RUNS.values())}
    lines = AUDIT_PATH.read_text(encoding="utf-8").splitlines()
    out = []
    for i, line in enumerate(lines[after:], start=after):
        e = json.loads(line)
        if e["event"] not in BOARD_EVENTS:
            continue
        if run_id and e.get("run_id") != run_id:
            continue
        if ticket_id is not None and e.get("ticket_id") not in (ticket_id, None):
            continue
        item = {"index": i, "ts": e["ts"], "run_id": e["run_id"], "event": e["event"],
                "agent": e.get("agent"), "ticket_id": e.get("ticket_id")}
        if e["event"] == "agent_started":
            item.update(task=e.get("task"), asked_by=(e.get("chain") or [None])[-1])
        elif e["event"] == "agent_step":
            item.update(thoughts=e.get("thoughts", []), tool_requests=e.get("tool_requests", []))
        elif e["event"] == "tool_called":
            item.update(tool=e.get("tool"), args=e.get("args"), result=e.get("result"))
        elif e["event"] == "agent_finished":
            item.update(said=_said(e), output=e.get("output"),
                        tools_used=[c["tool"] for c in e.get("tool_calls", [])],
                        usage=e.get("ticket_usage_so_far"))
        else:
            item.update({k: v for k, v in e.items() if k not in item and k not in ("ts", "run_id", "event")})
        out.append(item)
    return {"events": out, "next": len(lines), "runs": list(RUNS.values())}


# (d) human approval: this is what moves cash --------------------------------------------

@app.get("/approvals")
async def list_approvals(status: str | None = None, ticket_id: int | None = None):
    """Payment and purchase-order requests the agents prepared (for the Approve/Deny buttons)."""
    args = {k: v for k, v in {"status": status, "ticket_id": ticket_id}.items() if v is not None}
    return await mcp("list_approval_requests", args)


async def _decide(approval_id: int, decision: str, body: ApprovalDecisionIn | None) -> dict:
    body = body or ApprovalDecisionIn()
    approver = (body.approver or DEFAULT_APPROVER).strip()
    result = await mcp("record_human_approval", {"approval_id": approval_id, "decision": decision,
                                                 "approver": approver, "note": body.note})
    _api_audit().log("human_decision", approval_id=approval_id, decision=decision, approver=approver,
                     note=body.note, result=result)
    if not result.get("ok"):
        raise HTTPException(409, result.get("reason", "Refused."))
    return result


@app.post("/approvals/{approval_id}/approve")
async def approve(approval_id: int, body: ApprovalDecisionIn | None = None):
    """Human clicked Approve: pays the request (debits cash, adds a payments row, updates the
    invoice/lease). Refused with 409 if cash is short or the request isn't pending."""
    return await _decide(approval_id, "approved", body)


@app.post("/approvals/{approval_id}/deny")
async def deny(approval_id: int, body: ApprovalDecisionIn | None = None):
    """Human clicked Deny: marks the request denied. No money moves."""
    return await _decide(approval_id, "denied", body)


# board: drafts and decision notes ---------------------------------------------------------

@app.get("/board")
async def board(ticket_id: int | None = None):
    """Everything on the board: message drafts (never sent) and the boss's internal decision notes."""
    return await mcp("read_board", {} if ticket_id is None else {"ticket_id": ticket_id})


# (e) checking balance ------------------------------------------------------------------

@app.get("/cash")
async def cash():
    """Current checking balance from cash_accounts."""
    data = await mcp("get_cash_and_obligations")
    checking = next((a for a in data["cash_accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, "No checking account in cash_accounts.")
    return {"account": "checking", "balance": checking["balance"], "as_of": checking["date"],
            "desk_date_today": data["desk_date_today"]}


# (f) reset ----------------------------------------------------------------------------

@app.post("/reset")
async def reset():
    """Reset campus_customs_new.db to the original values for a fresh run."""
    if (active := _active_run()):
        raise HTTPException(409, f"Run {active['run_id']} is still running; reset after it finishes.")
    async with _run_lock:
        result = await mcp("reset_database_to_original")
    _api_audit().log("database_reset", result=result, source="api")
    return result
