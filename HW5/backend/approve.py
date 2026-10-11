"""Human approval step (terminal version of the board's Approve button).

Lists every PENDING request through the MCP server, asks the human y/n for
each one, and records the decision with the human-only record_human_approval
tool. Approving is what pays: it debits cash and updates the tables, or is
refused if cash is short. Each decision is appended to output/audit_trail.json.

Standalone:  .venv/bin/python backend/approve.py --approver "Your Name"
Then let the agents act on the decisions:  .venv/bin/python backend/run_team.py --follow-up
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import datetime

from agents import shop_mcp
from audit import AuditTrail


def _describe(req: dict) -> str:
    if req["kind"] == "purchase_order":
        what = (f"PURCHASE ORDER: vendor {req['vendor_id']}, {req['qty']} x {req['sku']} {req['size']}, "
                f"${req['amount']:,.2f} (unit_cost x qty)")
    else:
        target = "invoice" if req["kind"] == "invoice_payment" else "lease"
        what = f"PAYMENT: {req['kind']} for {target} {req['ref_id']}, ${req['amount']:,.2f} from {req['account']}"
    return (f"#{req['id']} {what}\n    ticket {req['ticket_id']} | requested by {req['requested_by']}\n"
            f"    reason: {req['reason']}")


async def review_pending(audit: AuditTrail, approver: str) -> list[dict]:
    """Ask the human about each pending request. Returns the decisions made."""
    pending = (await shop_mcp.direct_call_tool("list_approval_requests", {"status": "pending"}))["approvals"]
    if not pending:
        print("No pending approval requests.")
        return []
    cash = await shop_mcp.direct_call_tool("get_cash_and_obligations", {})
    print(f"\nCash on hand: ${cash['totals']['cash_on_hand']:,.2f} (desk date {cash['desk_date_today']})")
    decisions = []
    for req in pending:
        print("\n" + _describe(req))
        answer = input("    Approve? [y]es / [n]o / [s]kip: ").strip().lower()
        if answer not in ("y", "n"):
            print("    skipped (still pending)")
            continue
        decision = "approved" if answer == "y" else "denied"
        note = input("    Note (optional): ").strip()
        result = await shop_mcp.direct_call_tool(
            "record_human_approval",
            {"approval_id": req["id"], "decision": decision, "approver": approver, "note": note})
        audit.log("human_decision", approval_id=req["id"], decision=decision, approver=approver,
                  note=note, request=req, result=result)
        print(f"    -> {result['status']}" if result.get("ok") else f"    -> not recorded: {result.get('reason')}")
        if result.get("ok"):
            decisions.append({"approval_id": req["id"], "ticket_id": req["ticket_id"], "decision": decision})
    return decisions


async def main() -> None:
    parser = argparse.ArgumentParser(description="Approve or deny pending payments and purchase orders.")
    parser.add_argument("--approver", help="Your name, recorded as approved_by")
    args = parser.parse_args()
    approver = args.approver or input("Approver name: ").strip()
    run_id = f"approve-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    audit = AuditTrail(run_id)
    audit.log("approval_session_started", approver=approver)
    async with shop_mcp:
        decisions = await review_pending(audit, approver)
    audit.log("approval_session_finished", decisions=decisions)


if __name__ == "__main__":
    asyncio.run(main())
