"""Campus Customs MCP server.

Exposes the shop database (data/campus_customs_new.db) to the HW5 agents.
This server is the only way agents read or change shop data. Every value
returned comes straight from the database; when a row is missing the tool
says so instead of guessing.

Shop rules enforced here (not just in prompts):
- desk.date_today is "today" for every due/overdue/arrival calculation.
- Agents only prepare payments and purchase orders. Money moves only when the
  human approves (record_human_approval), and it refuses if the account would
  go negative. Cash only goes out.
- A vendor with an open invoice will not ship, so purchase orders to it are refused.
- Nothing is ever sent: messages are saved as drafts on the board.
- Amounts are taken from the database (invoice amount, monthly rent, unit cost),
  never from the agent.
"""

import shutil
import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "campus_customs_new.db"
ORIGINAL_DB_PATH = DATA_DIR / "campus_customs.db"

AGENTS = ("boss", "inventory", "accounting", "facilities", "customer_service")
# Which agent may address which audience on the board.
BOARD_AUDIENCES = {
    "customer": {"customer_service"},
    "vendor": {"accounting", "inventory"},
    "landlord": {"facilities"},
    "internal": set(AGENTS),
}
# Internal business details that must never appear in a customer draft. Vendor names are added
# from the vendors table at check time.
CUSTOMER_FORBIDDEN = [
    (r"\bvendors?\b", "vendor"), (r"\bsuppliers?\b", "supplier"), (r"\binvoices?\b", "invoice"),
    (r"\bpurchase[- ]orders?\b", "purchase order"), (r"\bPOs?\b", "PO"),
    (r"\bapprov(al|als|ed|e)\b", "approval"), (r"\bpaid\b", "paid"),
    (r"\boverdue\b", "overdue"), (r"\bchecking account\b|\bcash (on hand|balance)\b", "cash position"),
    (r"\bunit[_ ]cost\b|\bour cost\b|\bmargins?\b", "cost/margin"),
    (r"\blead[- ]time\b", "lead time"),
]

TICKET_STATUSES = ("open", "in_progress", "waiting_on_approval", "waiting_on_vendor", "resolved")

# Working tables the agents need that the original database doesn't have.
# They are recreated (empty) after every reset.
EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- invoice_payment | rent_payment | purchase_order
    ticket_id INTEGER,
    ref_id INTEGER,                  -- invoices.id or leases.id (payments)
    vendor_id INTEGER,               -- purchase orders
    sku TEXT, size TEXT, qty INTEGER,
    amount REAL NOT NULL,
    account TEXT,
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL,            -- pending | approved | denied | paid
    decided_by TEXT, decided_at TEXT, decision_note TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS board (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    author_agent TEXT NOT NULL,
    audience TEXT NOT NULL,          -- customer | vendor | landlord | internal
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL
);
"""

mcp = FastMCP("campus-customs")


def _ensure_extra_tables() -> None:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.executescript(EXTRA_SCHEMA)
        conn.commit()


def _connect(write: bool = False) -> sqlite3.Connection:
    """Open the working copy. Reads use a read-only connection."""
    _ensure_extra_tables()
    if write:
        conn = sqlite3.connect(DB_PATH)
    else:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _today(conn: sqlite3.Connection) -> str:
    return conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()[0]


def _refuse(reason: str, **extra) -> dict:
    return {"ok": False, "refused": True, "reason": reason, **extra}


def _check_author(author_agent: str, allowed: set[str], action: str) -> dict | None:
    if author_agent not in allowed:
        return _refuse(f"{author_agent!r} is not allowed to {action}; "
                       f"allowed: {sorted(allowed)}.")
    return None


def _add_months(iso_day: str, months: int) -> str:
    d = date.fromisoformat(iso_day)
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            continue
    raise ValueError(iso_day)


def _row(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days


@mcp.tool()
def get_ticket_with_links(ticket_id: int) -> dict:
    """Read one ticket and the database rows it points to.

    Returns the ticket, plus its linked lease (lease_id), linked invoice and
    that invoice's vendor (invoice_id -> vendor_id), and the shop's
    desk.date_today. Links that are empty on the ticket come back as null.
    """
    with closing(_connect()) as conn:
        ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"found": False, "ticket_id": ticket_id,
                    "message": f"No ticket with id {ticket_id} in the database."}

        desk = _row(conn, "SELECT date_today, notes FROM desk LIMIT 1")
        lease = (_row(conn, "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],))
                 if ticket["lease_id"] is not None else None)
        invoice = vendor = None
        if ticket["invoice_id"] is not None:
            invoice = _row(conn, "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],))
            if invoice:
                vendor = _row(conn, "SELECT * FROM vendors WHERE id = ?", (invoice["vendor_id"],))

    return {"found": True, "desk": desk, "ticket": ticket,
            "linked_lease": lease, "linked_invoice": invoice, "linked_vendor": vendor}


@mcp.tool()
def check_stock_and_price(sku: str, size: str, qty_requested: int | None = None) -> dict:
    """Check on-hand stock and pricing for a SKU.

    Returns the inventory row for the requested size, every other size of the
    same SKU, and the SKU's unit_cost and list_price. If qty_requested is
    given, also reports whether that size covers it and the shortfall.
    """
    with closing(_connect()) as conn:
        all_sizes = _rows(conn, "SELECT sku, name, size, qty, location FROM inventory "
                                "WHERE sku = ? ORDER BY rowid", (sku,))
        pricing = _row(conn, "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))

    if not all_sizes:
        return {"found": False, "sku": sku,
                "message": f"SKU {sku} is not in inventory.", "pricing": pricing}

    requested = next((r for r in all_sizes if r["size"] == size), None)
    result = {"found": True, "sku": sku, "requested_size": size,
              "requested_size_row": requested, "all_sizes": all_sizes, "pricing": pricing}
    if requested is None:
        result["message"] = f"SKU {sku} has no size {size} in inventory."
    elif qty_requested is not None:
        result["qty_requested"] = qty_requested
        result["can_fill_from_stock"] = requested["qty"] >= qty_requested
        result["shortfall"] = max(qty_requested - requested["qty"], 0)
    return result


@mcp.tool()
def get_cash_and_obligations() -> dict:
    """Show cash on hand against everything the shop owes.

    Returns cash account balances, open invoices (with vendor and days until
    due / overdue vs desk.date_today), lease rent with days until next_due,
    and payments already recorded. Totals are simple sums of those rows.
    """
    with closing(_connect()) as conn:
        desk = _row(conn, "SELECT date_today, notes FROM desk LIMIT 1")
        accounts = _rows(conn, "SELECT name, balance, date FROM cash_accounts")
        invoices = _rows(conn, "SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, "
                               "i.due_date, i.status, i.description FROM invoices i "
                               "LEFT JOIN vendors v ON v.id = i.vendor_id "
                               "WHERE i.status = 'open' ORDER BY i.due_date")
        leases = _rows(conn, "SELECT id, space_name, landlord, monthly_rent, next_due, notes "
                             "FROM leases ORDER BY next_due")
        payments = _rows(conn, "SELECT * FROM payments ORDER BY paid_at")

    today = desk["date_today"] if desk else None
    if today:
        for inv in invoices:
            inv["days_until_due"] = _days_between(today, inv["due_date"])
            inv["overdue"] = inv["days_until_due"] < 0
        for lease in leases:
            lease["days_until_due"] = _days_between(today, lease["next_due"])

    total_cash = sum(a["balance"] for a in accounts)
    total_open_invoices = sum(i["amount"] for i in invoices)
    total_rent_due = sum(l["monthly_rent"] for l in leases)
    return {
        "desk_date_today": today,
        "cash_accounts": accounts,
        "open_invoices": invoices,
        "leases": leases,
        "payments_recorded": payments,
        "totals": {
            "cash_on_hand": total_cash,
            "open_invoices": total_open_invoices,
            "next_rent_due": total_rent_due,
            "cash_left_if_all_paid": total_cash - total_open_invoices - total_rent_due,
        },
    }


# ---------------------------------------------------------------------------
# Tools added in Problem 5
# ---------------------------------------------------------------------------

@mcp.tool()
def list_open_tickets(include_resolved: bool = False) -> dict:
    """List tickets oldest first, with desk.date_today. Resolved tickets only if include_resolved."""
    sql = ("SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, "
           "created_at FROM tickets")
    if not include_resolved:
        sql += " WHERE status != 'resolved'"
    with closing(_connect()) as conn:
        tickets = _rows(conn, sql + " ORDER BY created_at")
        for t in tickets:
            t["is_resolved"] = t["status"] == "resolved"
            t["is_open"] = not t["is_resolved"]
        return {"desk_date_today": _today(conn), "tickets": tickets}


@mcp.tool()
def get_vendor_restock_options(specialty_contains: str | None = None) -> dict:
    """List vendors with lead_days, their open invoices, and whether they can ship.

    A vendor with any open invoice will NOT ship new products (shop rule), so
    it is marked can_ship_new_orders = false. earliest_arrival_if_ordered_today
    is desk.date_today + lead_days. The vendors table has no SKU column, so
    match products to vendors by the `specialty` text only.
    """
    with closing(_connect()) as conn:
        today = _today(conn)
        sql, params = "SELECT * FROM vendors", ()
        if specialty_contains:
            sql, params = sql + " WHERE specialty LIKE ?", (f"%{specialty_contains}%",)
        vendors = _rows(conn, sql + " ORDER BY id", params)
        for v in vendors:
            v["open_invoices"] = _rows(conn, "SELECT id, amount, due_date, description FROM invoices "
                                             "WHERE vendor_id = ? AND status = 'open'", (v["id"],))
            for inv in v["open_invoices"]:
                inv["days_overdue"] = max(_days_between(inv["due_date"], today), 0)
            v["can_ship_new_orders"] = not v["open_invoices"]
            v["earliest_arrival_if_ordered_today"] = date.fromordinal(
                date.fromisoformat(today).toordinal() + v["lead_days"]).isoformat()
    return {"desk_date_today": today, "vendors": vendors,
            "rule": "A vendor with an open invoice will not ship new products until it is paid."}


@mcp.tool()
def check_margin(sku: str, unit_price: float, qty: int = 1) -> dict:
    """Margin math for selling `qty` units of `sku` at `unit_price`, using pricing.unit_cost and list_price."""
    with closing(_connect()) as conn:
        pricing = _row(conn, "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
    if pricing is None:
        return {"found": False, "message": f"SKU {sku} has no pricing row."}
    cost, list_price = pricing["unit_cost"], pricing["list_price"]
    return {
        "found": True, "sku": sku, "qty": qty, "unit_price": unit_price,
        "unit_cost": cost, "list_price": list_price,
        "discount_vs_list_pct": round((list_price - unit_price) / list_price * 100, 2),
        "margin_per_unit": round(unit_price - cost, 2),
        "margin_pct_of_price": round((unit_price - cost) / unit_price * 100, 2) if unit_price else None,
        "total_revenue": round(unit_price * qty, 2),
        "total_cost": round(cost * qty, 2),
        "total_margin": round((unit_price - cost) * qty, 2),
        "below_cost": unit_price < cost,
    }


@mcp.tool()
def request_payment_approval(kind: str, ref_id: int, reason: str, author_agent: str,
                             ticket_id: int | None = None, account: str = "checking") -> dict:
    """Create a PENDING payment request for the human to approve. Moves no money.

    kind: 'invoice_payment' (ref_id = invoices.id) or 'rent_payment' (ref_id = leases.id).
    The amount is read from the database (invoice amount or monthly_rent).
    Refused if the invoice isn't open or a request for the same item is already pending/approved.
    """
    if (bad := _check_author(author_agent, {"accounting"}, "request payments")):
        return bad
    if kind not in ("invoice_payment", "rent_payment"):
        return _refuse("kind must be 'invoice_payment' or 'rent_payment'.")
    with closing(_connect(write=True)) as conn:
        if kind == "invoice_payment":
            item = _row(conn, "SELECT * FROM invoices WHERE id = ?", (ref_id,))
            if item is None:
                return _refuse(f"No invoice {ref_id}.")
            if item["status"] != "open":
                return _refuse(f"Invoice {ref_id} status is {item['status']!r}, not 'open'.")
            amount = item["amount"]
        else:
            item = _row(conn, "SELECT * FROM leases WHERE id = ?", (ref_id,))
            if item is None:
                return _refuse(f"No lease {ref_id}.")
            amount = item["monthly_rent"]
        dup = _row(conn, "SELECT id, status FROM approvals WHERE kind = ? AND ref_id = ? "
                         "AND status IN ('pending', 'approved')", (kind, ref_id))
        if dup:
            return _refuse(f"Approval request {dup['id']} for this item is already {dup['status']}.",
                           existing_approval_id=dup["id"])
        acct = _row(conn, "SELECT balance FROM cash_accounts WHERE name = ?", (account,))
        if acct is None:
            return _refuse(f"No cash account {account!r}.")
        cur = conn.execute(
            "INSERT INTO approvals (kind, ticket_id, ref_id, amount, account, reason, requested_by, "
            "status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (kind, ticket_id, ref_id, amount, account, reason, author_agent, _now()))
        conn.commit()
        return {"ok": True, "approval_id": cur.lastrowid, "status": "pending", "kind": kind,
                "ref_id": ref_id, "amount": amount, "account": account,
                "account_balance_now": acct["balance"],
                "balance_after_if_paid": acct["balance"] - amount,
                "next_step": "Waiting for human approval. No money has moved."}


@mcp.tool()
def prepare_purchase_order(vendor_id: int, sku: str, size: str, qty: int, reason: str,
                           author_agent: str, ticket_id: int | None = None) -> dict:
    """Create a PENDING restock purchase order for human approval. Sends nothing to the vendor.

    Refused if the vendor has an open invoice (it will not ship), or the sku/size
    isn't in inventory. estimated_cost = pricing.unit_cost * qty; the vendor's
    real price will come on its invoice. expected_arrival_if_approved_today =
    desk.date_today + vendors.lead_days.
    """
    if (bad := _check_author(author_agent, {"accounting"}, "prepare purchase orders")):
        return bad
    if qty <= 0:
        return _refuse("qty must be positive.")
    with closing(_connect(write=True)) as conn:
        vendor = _row(conn, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        if vendor is None:
            return _refuse(f"No vendor {vendor_id}.")
        open_inv = _rows(conn, "SELECT id, amount, due_date FROM invoices "
                               "WHERE vendor_id = ? AND status = 'open'", (vendor_id,))
        if open_inv:
            return _refuse(f"{vendor['name']} has open invoice(s) and will not ship new products. "
                           "The open invoice must be paid first.", open_invoices=open_inv)
        stock = _row(conn, "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (sku, size))
        pricing = _row(conn, "SELECT unit_cost FROM pricing WHERE sku = ?", (sku,))
        if stock is None or pricing is None:
            return _refuse(f"{sku} size {size} is not in inventory/pricing.")
        dup = _row(conn, "SELECT id, status FROM approvals WHERE kind = 'purchase_order' AND sku = ? "
                         "AND size = ? AND status IN ('pending', 'approved')", (sku, size))
        if dup:
            return _refuse(f"Purchase order {dup['id']} for {sku} {size} is already {dup['status']}.",
                           existing_approval_id=dup["id"])
        today = _today(conn)
        estimated = round(pricing["unit_cost"] * qty, 2)
        cur = conn.execute(
            "INSERT INTO approvals (kind, ticket_id, vendor_id, sku, size, qty, amount, reason, "
            "requested_by, status, created_at) VALUES ('purchase_order', ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (ticket_id, vendor_id, sku, size, qty, estimated, reason, author_agent, _now()))
        conn.commit()
        return {"ok": True, "approval_id": cur.lastrowid, "status": "pending", "vendor": vendor["name"],
                "sku": sku, "size": size, "qty": qty, "estimated_cost": estimated,
                "estimate_basis": "pricing.unit_cost x qty",
                "lead_days": vendor["lead_days"],
                "expected_arrival_if_approved_today": date.fromordinal(
                    date.fromisoformat(today).toordinal() + vendor["lead_days"]).isoformat(),
                "next_step": "Waiting for human approval. Nothing has been sent to the vendor."}


@mcp.tool()
def list_approval_requests(status: str | None = None, ticket_id: int | None = None) -> dict:
    """List approval requests (payments and purchase orders), optionally filtered by status or ticket."""
    sql, params = "SELECT * FROM approvals WHERE 1=1", []
    if status:
        sql += " AND status = ?"; params.append(status)
    if ticket_id is not None:
        sql += " AND ticket_id = ?"; params.append(ticket_id)
    with closing(_connect()) as conn:
        return {"approvals": _rows(conn, sql + " ORDER BY id", tuple(params))}


@mcp.tool()
def record_human_approval(approval_id: int, decision: str, approver: str, note: str = "") -> dict:
    """HUMAN ONLY. Approve or deny a pending request. Approving is what moves the money.

    Not given to any agent; called when the human clicks Approve/Deny (backend/main.py)
    or answers in backend/approve.py.

    decision='approved' pays the request in one transaction:
      - invoice_payment: invoice amount; invoice status -> 'paid'
      - rent_payment: monthly_rent; lease next_due moves forward one month
      - purchase_order: unit_cost x qty paid to the vendor (inventory updates
        only when the goods arrive, after vendors.lead_days)
    Each one debits cash_accounts, adds a payments row (approved_by = the human),
    and marks the approval 'paid'. If the balance is lower than the amount, the
    approval is refused and the request stays 'pending' (no negative balances).
    decision='denied' marks the request denied and moves no money.
    """
    if decision not in ("approved", "denied"):
        return _refuse("decision must be 'approved' or 'denied'.")
    if approver in AGENTS or not approver.strip():
        return _refuse("Approvals must come from a named human, not an agent.")
    with closing(_connect(write=True)) as conn:
        req = _row(conn, "SELECT * FROM approvals WHERE id = ?", (approval_id,))
        if req is None:
            return _refuse(f"No approval request {approval_id}.")
        if req["status"] != "pending":
            return _refuse(f"Request {approval_id} is {req['status']!r}, not 'pending'.")
        now = _now()
        if decision == "denied":
            conn.execute("UPDATE approvals SET status = 'denied', decided_by = ?, decided_at = ?, "
                         "decision_note = ? WHERE id = ?", (approver, now, note, approval_id))
            conn.commit()
            return {"ok": True, "approval_id": approval_id, "status": "denied", "decided_by": approver,
                    "money_moved": False}

        account = req["account"] or "checking"
        acct = _row(conn, "SELECT * FROM cash_accounts WHERE name = ?", (account,))
        if acct is None:
            return _refuse(f"No cash account {account!r}.")
        if acct["balance"] < req["amount"]:
            return _refuse(f"Not enough cash: {account} has {acct['balance']}, request is "
                           f"{req['amount']}. Paying would make the balance negative, so the "
                           "request stays pending.", balance=acct["balance"], amount=req["amount"])
        if req["kind"] == "invoice_payment":
            inv = _row(conn, "SELECT status FROM invoices WHERE id = ?", (req["ref_id"],))
            if inv is None or inv["status"] != "open":
                return _refuse(f"Invoice {req['ref_id']} is no longer open.")
        if req["kind"] == "purchase_order":
            open_inv = _rows(conn, "SELECT id FROM invoices WHERE vendor_id = ? AND status = 'open'",
                             (req["vendor_id"],))
            if open_inv:
                return _refuse("This vendor now has an open invoice and will not ship; pay it first.",
                               open_invoices=open_inv)

        today = _today(conn)
        kind = {"invoice_payment": "invoice", "rent_payment": "rent", "purchase_order": "purchase_order"}[req["kind"]]
        ref_id = approval_id if kind == "purchase_order" else req["ref_id"]
        new_balance = acct["balance"] - req["amount"]
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
                     (new_balance, today, account))
        cur = conn.execute("INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
                           "VALUES (?, ?, ?, ?, ?, ?)", (kind, ref_id, req["amount"], account, today, approver))
        updated: dict = {"cash_accounts": account, "payments": cur.lastrowid}
        if kind == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
            updated["invoices"] = {"id": req["ref_id"], "status": "paid"}
        elif kind == "rent":
            lease = _row(conn, "SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],))
            next_due = _add_months(lease["next_due"], 1)
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, req["ref_id"]))
            updated["leases"] = {"id": req["ref_id"], "next_due": next_due}
        else:
            lead = _row(conn, "SELECT lead_days FROM vendors WHERE id = ?", (req["vendor_id"],))["lead_days"]
            updated["expected_arrival"] = date.fromordinal(date.fromisoformat(today).toordinal() + lead).isoformat()
        conn.execute("UPDATE approvals SET status = 'paid', decided_by = ?, decided_at = ?, decision_note = ? "
                     "WHERE id = ?", (approver, now, note, approval_id))
        conn.commit()
        return {"ok": True, "approval_id": approval_id, "status": "paid", "decided_by": approver,
                "money_moved": True, "payment_id": cur.lastrowid, "kind": kind, "amount": req["amount"],
                "account": account, "paid_at": today, "balance_before": acct["balance"],
                "balance_after": new_balance, "tables_updated": updated}


@mcp.tool()
def post_draft_to_board(audience: str, recipient: str, subject: str, body: str,
                        author_agent: str, ticket_id: int | None = None) -> dict:
    """Save a message DRAFT on the board. Nothing is ever emailed, texted, or called.

    audience: 'customer' (customer_service only), 'vendor' (accounting/inventory),
    'landlord' (facilities), or 'internal' (any agent).
    """
    allowed = BOARD_AUDIENCES.get(audience)
    if allowed is None:
        return _refuse(f"audience must be one of {sorted(BOARD_AUDIENCES)}.")
    if (bad := _check_author(author_agent, allowed, f"write {audience} drafts")):
        return bad
    if audience == "customer" and (leaks := _customer_leaks(f"{subject}\n{body}")):
        return _refuse("Customer drafts must not reveal internal business details. Remove: "
                       + ", ".join(leaks) + ". Describe only what the customer gets and when "
                       "(e.g. 'back in stock', 'about a week'), never how the shop gets it.",
                       found=leaks)
    with closing(_connect(write=True)) as conn:
        cur = conn.execute("INSERT INTO board (ticket_id, author_agent, audience, recipient, subject, "
                           "body, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?)",
                           (ticket_id, author_agent, audience, recipient, subject, body, _now()))
        conn.commit()
        return {"ok": True, "board_id": cur.lastrowid, "status": "draft",
                "note": "Saved to the board only. Not sent."}


def _customer_leaks(text: str) -> list[str]:
    """Internal details (vendors, payments, invoices, approvals, costs...) found in customer-facing text."""
    import re
    found = [label for pattern, label in CUSTOMER_FORBIDDEN if re.search(pattern, text, re.IGNORECASE)]
    with closing(_connect()) as conn:
        names = [r["name"] for r in _rows(conn, "SELECT name FROM vendors")]
    found += [f"vendor name '{n}'" for n in names if n.lower() in text.lower()]
    return found


@mcp.tool()
def read_board(ticket_id: int | None = None) -> dict:
    """Read board drafts and notes, optionally for one ticket."""
    with closing(_connect()) as conn:
        if ticket_id is None:
            return {"board": _rows(conn, "SELECT * FROM board ORDER BY id")}
        return {"board": _rows(conn, "SELECT * FROM board WHERE ticket_id = ? ORDER BY id", (ticket_id,))}


@mcp.tool()
def update_ticket_status(ticket_id: int, status: str, note: str, author_agent: str) -> dict:
    """Boss only. Set a ticket's status and post the decision as an internal board note.

    status: open | in_progress | waiting_on_approval | waiting_on_vendor | resolved.
    The ticket's original notes are left untouched.
    """
    if (bad := _check_author(author_agent, {"boss"}, "change ticket status")):
        return bad
    if status not in TICKET_STATUSES:
        return _refuse(f"status must be one of {list(TICKET_STATUSES)}.")
    with closing(_connect(write=True)) as conn:
        old = _row(conn, "SELECT status FROM tickets WHERE id = ?", (ticket_id,))
        if old is None:
            return _refuse(f"No ticket {ticket_id}.")
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        cur = conn.execute("INSERT INTO board (ticket_id, author_agent, audience, recipient, subject, "
                           "body, status, created_at) VALUES (?, 'boss', 'internal', 'team', ?, ?, 'draft', ?)",
                           (ticket_id, f"Ticket {ticket_id}: {old['status']} -> {status}", note, _now()))
        conn.commit()
        return {"ok": True, "ticket_id": ticket_id, "old_status": old["status"],
                "new_status": status, "board_id": cur.lastrowid}


@mcp.tool()
def reset_database_to_original() -> dict:
    """HUMAN/RUNNER ONLY. Overwrite campus_customs_new.db with the original campus_customs.db.

    Not given to any agent. Run before every full ticket run. The approvals and
    board tables are recreated empty.
    """
    shutil.copyfile(ORIGINAL_DB_PATH, DB_PATH)
    _ensure_extra_tables()
    with closing(_connect()) as conn:
        counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("tickets", "invoices", "payments", "approvals", "board")}
        return {"ok": True, "reset_from": ORIGINAL_DB_PATH.name, "reset_to": DB_PATH.name,
                "desk_date_today": _today(conn), "row_counts": counts}


if __name__ == "__main__":
    mcp.run(show_banner=False)
