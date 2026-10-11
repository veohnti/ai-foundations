"""Smoke test: connect to the MCP server through .mcp.json, call each tool,
check the results against data/campus_customs_new.db with independent SQL,
and save the evidence to output/mcp_smoke.json.

Run from HW5/:  .venv/bin/python mcp_server/smoke_test.py  (or with any Python that has requirements.txt installed)
"""

import asyncio
import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

from fastmcp import Client

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"
OUT_PATH = ROOT / "output" / "mcp_smoke.json"

PROMPTS = {
    "get_ticket_with_links": (
        "get_ticket_with_links(ticket_id): Test tickets 101, 102, and 103 to verify that each "
        "ticket and its linked lease, invoice, and vendor records are retrieved accurately, "
        "especially ticket 101’s linked $840 invoice that is three days overdue."
    ),
    "check_stock_and_price": (
        "check_stock_and_price(sku, size, qty_requested): Test the SKUs and quantities associated "
        "with tickets 101 and 103 to verify stock availability across sizes, quantity shortages, "
        "unit cost, and list price, specifically confirming the $22 cost and $58 list price "
        "relevant to ticket 103’s discount decision."
    ),
    "get_cash_and_obligations": (
        "get_cash_and_obligations(): Verify that the tool accurately returns the checking balance, "
        "outstanding invoices and overdue days, rent due, and recorded payments, then independently "
        "calculate whether paying all outstanding obligations correctly leaves $160 in cash."
    ),
}


def db_one(sql, params=()):
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def db_all(sql, params=()):
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def check(label, actual, expected):
    return {"check": label, "tool_value": actual, "db_value": expected, "pass": actual == expected}


async def call(client, name, args):
    result = await client.call_tool(name, args)
    data = result.structured_content
    if data is None:
        data = json.loads(result.content[0].text)
    return data


async def main():
    config = json.loads((ROOT / ".mcp.json").read_text())
    for server in config["mcpServers"].values():  # .mcp.json paths are relative to HW5/
        server["command"] = sys.executable
        server["args"] = [str(ROOT / a) if a.endswith(".py") else a for a in server.get("args", [])]
    today = db_one("SELECT date_today FROM desk")["date_today"]

    async with Client(config) as client:
        listed = sorted(t.name for t in await client.list_tools())

        # Tool 1: tickets 101, 102, 103 and their links
        t1_calls, t1_checks = [], []
        for tid in (101, 102, 103):
            out = await call(client, "get_ticket_with_links", {"ticket_id": tid})
            t1_calls.append({"arguments": {"ticket_id": tid}, "output": out})
            ticket = db_one("SELECT * FROM tickets WHERE id = ?", (tid,))
            t1_checks.append(check(f"ticket {tid} row", out["ticket"], ticket))
            lease = db_one("SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)) if ticket["lease_id"] else None
            invoice = db_one("SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],)) if ticket["invoice_id"] else None
            vendor = db_one("SELECT * FROM vendors WHERE id = ?", (invoice["vendor_id"],)) if invoice else None
            t1_checks.append(check(f"ticket {tid} linked lease", out["linked_lease"], lease))
            t1_checks.append(check(f"ticket {tid} linked invoice", out["linked_invoice"], invoice))
            t1_checks.append(check(f"ticket {tid} linked vendor", out["linked_vendor"], vendor))
        inv501 = t1_calls[0]["output"]["linked_invoice"]
        overdue_days = (date.fromisoformat(today) - date.fromisoformat(inv501["due_date"])).days
        t1_checks.append(check("ticket 101 invoice amount is $840", inv501["amount"], 840.0))
        t1_checks.append(check("ticket 101 invoice days overdue vs desk.date_today", overdue_days, 3))

        # Tool 2: SKUs/quantities from tickets 101 and 103
        t2_calls, t2_checks = [], []
        for tid in (101, 103):
            ticket = db_one("SELECT sku, size, qty FROM tickets WHERE id = ?", (tid,))
            args = {"sku": ticket["sku"], "size": ticket["size"], "qty_requested": ticket["qty"]}
            out = await call(client, "check_stock_and_price", args)
            t2_calls.append({"ticket_id": tid, "arguments": args, "output": out})
            sizes = db_all("SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? ORDER BY rowid", (ticket["sku"],))
            row = next(r for r in sizes if r["size"] == ticket["size"])
            price = db_one("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (ticket["sku"],))
            t2_checks.append(check(f"ticket {tid} all sizes of {ticket['sku']}", out["all_sizes"], sizes))
            t2_checks.append(check(f"ticket {tid} stock for size {ticket['size']}", out["requested_size_row"]["qty"], row["qty"]))
            t2_checks.append(check(f"ticket {tid} shortfall", out["shortfall"], max(ticket["qty"] - row["qty"], 0)))
            t2_checks.append(check(f"ticket {tid} can fill from stock", out["can_fill_from_stock"], row["qty"] >= ticket["qty"]))
            t2_checks.append(check(f"ticket {tid} pricing", out["pricing"], price))
        t2_checks.append(check("ticket 103 unit_cost is $22", t2_calls[1]["output"]["pricing"]["unit_cost"], 22.0))
        t2_checks.append(check("ticket 103 list_price is $58", t2_calls[1]["output"]["pricing"]["list_price"], 58.0))

        # Tool 3: cash vs obligations, with an independent $160 calculation
        out3 = await call(client, "get_cash_and_obligations", {})
        checking = db_one("SELECT balance FROM cash_accounts WHERE name = 'checking'")["balance"]
        open_inv = db_all("SELECT id, amount, due_date FROM invoices WHERE status = 'open'")
        rent = db_all("SELECT id, monthly_rent, next_due FROM leases")
        payments = db_all("SELECT * FROM payments")
        independent_left = checking - sum(i["amount"] for i in open_inv) - sum(l["monthly_rent"] for l in rent)
        t3_checks = [
            check("checking balance", out3["cash_accounts"][0]["balance"], checking),
            check("open invoice ids and amounts",
                  [(i["id"], i["amount"]) for i in out3["open_invoices"]],
                  [(i["id"], i["amount"]) for i in open_inv]),
            check("invoice 501 days_until_due (negative = overdue)", out3["open_invoices"][0]["days_until_due"],
                  (date.fromisoformat(open_inv[0]["due_date"]) - date.fromisoformat(today)).days),
            check("rent due amount", out3["leases"][0]["monthly_rent"], rent[0]["monthly_rent"]),
            check("rent days until due", out3["leases"][0]["days_until_due"],
                  (date.fromisoformat(rent[0]["next_due"]) - date.fromisoformat(today)).days),
            check("recorded payments", out3["payments_recorded"], payments),
            check("tool cash_left_if_all_paid vs independent calc", out3["totals"]["cash_left_if_all_paid"], independent_left),
            check("independent calc leaves $160", independent_left, 160.0),
        ]
    all_checks = t1_checks + t2_checks + t3_checks
    evidence = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "connection": {"config_file": ".mcp.json", "server": "campus-customs", "transport": "stdio",
                       "tools_listed_by_server": listed},
        "database": "data/campus_customs_new.db",
        "desk_date_today": today,
        "tools": [
            {"prompt": PROMPTS["get_ticket_with_links"], "tool_name": "get_ticket_with_links",
             "calls": t1_calls, "db_checks": t1_checks},
            {"prompt": PROMPTS["check_stock_and_price"], "tool_name": "check_stock_and_price",
             "calls": t2_calls, "db_checks": t2_checks},
            {"prompt": PROMPTS["get_cash_and_obligations"], "tool_name": "get_cash_and_obligations",
             "calls": [{"arguments": {}, "output": out3}],
             "independent_calculation": {
                 "formula": "checking balance - open invoices - rent due",
                 "values": f"{checking} - {sum(i['amount'] for i in open_inv)} - {sum(l['monthly_rent'] for l in rent)}",
                 "result": independent_left},
             "db_checks": t3_checks},
        ],
        "summary": {"checks_run": len(all_checks), "checks_passed": sum(c["pass"] for c in all_checks),
                    "all_passed": all(c["pass"] for c in all_checks)},
    }
    OUT_PATH.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"tools": listed, **evidence["summary"]}))
    for c in all_checks:
        if not c["pass"]:
            print("FAIL:", c["check"], c["tool_value"], "!=", c["db_value"])


if __name__ == "__main__":
    asyncio.run(main())
