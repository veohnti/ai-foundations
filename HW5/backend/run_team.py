"""Run the Campus Customs agent team over the open tickets.

Full run (default):
  1. Reset data/campus_customs_new.db to the original (through the MCP server).
  2. The boss works each open ticket, delegating to the specialists.
  3. The human approves/denies any pending payments or purchase orders.
  4. Follow-up: the boss acts on those decisions (approving already paid; e.g. a now-unblocked PO).

  .venv/bin/python backend/run_team.py [--ticket 101] [--approver "Your Name"] [--skip-approvals]

Follow-up only (no reset), after approving with backend/approve.py:
  .venv/bin/python backend/run_team.py --follow-up

Every step is appended to output/audit_trail.json.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime

from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded

from agents import MODEL_NAME, TICKET_USAGE_LIMITS, run_agent, shop_mcp
from approve import review_pending
from audit import AuditTrail
from models import TeamDeps


async def work_ticket(ticket_id: int, task: str, audit: AuditTrail, run_id: str):
    deps = TeamDeps(agent_name="boss", run_id=run_id, ticket_id=ticket_id, audit=audit)
    try:
        decision = await run_agent("boss", task, deps)
    except (UsageLimitExceeded, UnexpectedModelBehavior) as e:
        audit.log("ticket_stopped", ticket_id=ticket_id, error=str(e))
        print(f"Ticket {ticket_id}: stopped ({type(e).__name__}: {e})")
        return None
    print(f"\nTicket {ticket_id} -> {decision.new_status}\n  {decision.final_decision}")
    if decision.pending_human_approvals:
        print(f"  waiting on human approval: {decision.pending_human_approvals}")
    return decision


def first_pass_task(ticket_id: int) -> str:
    return (f"Work ticket {ticket_id}. Read it with get_ticket_with_links, delegate to the right "
            "teammates, make the final call, and record it with update_ticket_status.")


def follow_up_task(ticket_id: int) -> str:
    return (f"Follow-up on ticket {ticket_id}: the human has decided on approval requests. "
            "Check list_approval_requests (all statuses); approved requests are already paid. "
            "Handle denials without paying. If a paid invoice unblocks a restock, have "
            "accounting prepare the purchase order for approval. Have customer service post an "
            "updated customer draft only if the outlook changed. Resolve the ticket once a draft on the "
            "board clearly tells the requester what will happen and when (or that it can't be done) "
            "and nothing it depends on is pending approval.")


async def follow_up(audit: AuditTrail, run_id: str, only: set[int] | None) -> None:
    tickets = (await shop_mcp.direct_call_tool("list_open_tickets", {}))["tickets"]
    targets = [t["id"] for t in tickets
               if t["status"] == "waiting_on_approval" and (not only or t["id"] in only)]
    audit.log("follow_up_started", tickets=targets)
    for tid in targets:
        await work_ticket(tid, follow_up_task(tid), audit, run_id)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team.")
    parser.add_argument("--ticket", type=int, action="append", help="Only this ticket (repeatable)")
    parser.add_argument("--follow-up", action="store_true",
                        help="Don't reset; act on human approval decisions already recorded")
    parser.add_argument("--approver", help="Your name for approvals (asked if omitted)")
    parser.add_argument("--skip-approvals", action="store_true",
                        help="Leave requests pending; approve later with backend/approve.py")
    args = parser.parse_args()
    only = set(args.ticket) if args.ticket else None

    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    audit = AuditTrail(run_id)
    audit.log("run_started", mode="follow_up" if args.follow_up else "full", tickets=args.ticket,
              model=MODEL_NAME, ticket_usage_limits=vars(TICKET_USAGE_LIMITS))
    print(f"Run {run_id} ({MODEL_NAME})")

    async with shop_mcp:
        if args.follow_up:
            await follow_up(audit, run_id, only)
        else:
            reset = await shop_mcp.direct_call_tool("reset_database_to_original", {})
            audit.log("database_reset", result=reset)
            print(f"Database reset to original: {reset['row_counts']}")

            tickets = (await shop_mcp.direct_call_tool("list_open_tickets", {}))["tickets"]
            for t in tickets:
                if not only or t["id"] in only:
                    await work_ticket(t["id"], first_pass_task(t["id"]), audit, run_id)

            if args.skip_approvals or not sys.stdin.isatty():
                print("\nApprovals left pending. Approve with backend/approve.py, then run --follow-up.")
            else:
                approver = args.approver or input("\nApprover name: ").strip()
                decisions = await review_pending(audit, approver)
                if decisions:
                    await follow_up(audit, run_id, only)

        board = (await shop_mcp.direct_call_tool("read_board", {}))["board"]
        approvals = (await shop_mcp.direct_call_tool("list_approval_requests", {}))["approvals"]
        cash = await shop_mcp.direct_call_tool("get_cash_and_obligations", {})

    audit.log("run_finished", board_drafts=len(board), approvals=approvals,
              cash_on_hand=cash["totals"]["cash_on_hand"], payments=cash["payments_recorded"])
    print(f"\nBoard drafts: {len(board)} | approvals: "
          f"{[(a['id'], a['kind'], a['status']) for a in approvals]} | "
          f"cash: ${cash['totals']['cash_on_hand']:,.2f}")


if __name__ == "__main__":
    asyncio.run(main())
