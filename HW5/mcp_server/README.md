# Campus Customs MCP Server

A FastMCP server that gives every HW5 agent (all running GPT Luna) one shared set of tools for reading and updating the Campus Customs shop database. Tools return only what is in the database. If a row doesn't exist, the tool says so and never guesses.

**Database:** `../data/campus_customs_new.db` (the working copy; the original `campus_customs.db` is never touched). Read tools open it read-only; write tools change only this copy. `reset_database_to_original` restores it from the original.

## Tools (14)

The server is the only way the agents read or change shop data. It enforces the shop rules in code: agents only prepare payments (the human's approval is what pays), no negative balances, no purchase orders to vendors with open invoices, drafts only, and amounts read from the database.

**Read tools**

| Tool | What it returns |
|---|---|
| `get_ticket_with_links(ticket_id)` | The ticket row plus its linked lease, invoice, and invoice vendor, and `desk.date_today` |
| `check_stock_and_price(sku, size, qty_requested=None)` | Stock for that size and every other size, `unit_cost`, `list_price`, and the shortfall |
| `get_cash_and_obligations()` | Cash balances, open invoices (vendor, days overdue), rent due, recorded payments, totals |
| `list_open_tickets(include_resolved=False)` | Tickets (not yet `resolved`, or all) with `is_open`/`is_resolved`, and `desk.date_today` |
| `get_vendor_restock_options(specialty_contains=None)` | Vendors, `lead_days`, open invoices, `can_ship_new_orders`, earliest arrival |
| `check_margin(sku, unit_price, qty=1)` | Margin per unit and total, discount vs list, `below_cost` flag |
| `list_approval_requests(status=None, ticket_id=None)` | Payment and purchase-order requests and their status |
| `read_board(ticket_id=None)` | Drafts and internal notes on the board |

**Write tools (agents)**

| Tool | What it does |
|---|---|
| `request_payment_approval(kind, ref_id, reason, author_agent, ticket_id=None, account="checking")` | Creates a **pending** invoice or rent payment request. The amount is read from the database. Accounting only. |
| `prepare_purchase_order(vendor_id, sku, size, qty, reason, author_agent, ticket_id=None)` | Creates a **pending** PO (charged at unit_cost × qty when approved). Refused if the vendor has an open invoice. Accounting only. |
| `post_draft_to_board(audience, recipient, subject, body, author_agent, ticket_id=None)` | Saves a **draft** (never sent). The audience is checked against the author's role. Customer drafts are refused if they reveal internal details (vendors or vendor names, invoices, POs, approvals, "paid", overdue bills, cash position, cost or margin, lead time). |
| `update_ticket_status(ticket_id, status, note, author_agent)` | Sets the ticket status and posts the decision as an internal note. Boss only. |

**Human/runner only (not given to any agent)**

| Tool | What it does |
|---|---|
| `record_human_approval(approval_id, decision, approver, note="")` | Approves or denies a pending request. **Approving pays it** in one transaction: debits cash, adds a payments row, and marks the invoice paid, moves the lease's next_due forward, or charges the PO. Refused if cash is short (no negative balances). Used by `POST /approvals/{id}/approve` and `backend/approve.py`. |
| `reset_database_to_original()` | Copies `campus_customs.db` over `campus_customs_new.db`. Used by `POST /reset` and `backend/run_team.py`. |

`author_agent` is filled in by the agent runner from the calling agent; the model never sees or sets it.

The server also adds two working tables to `campus_customs_new.db`: `approvals` and `board`. A reset recreates them empty.

## Connecting and testing

- `HW5/.mcp.json` registers this server as `campus-customs` (stdio, `.venv/bin/python mcp_server/server.py`, with paths relative to `HW5/`). The backend reads the same file and launches the server with its own Python.
- Run it on its own from `HW5/` with `.venv/bin/python mcp_server/server.py`. It waits on stdin for an MCP client; normally you don't need to start it, because the backend starts it.
- `smoke_test.py` connects through `.mcp.json`, calls the first 3 tools, checks every value against the database with separate SQL, and writes `../output/mcp_smoke.json`.

```bash
python3 -m venv .venv && .venv/bin/pip install --only-binary=cryptography -r requirements.txt
```

```bash
.venv/bin/python mcp_server/smoke_test.py
```
