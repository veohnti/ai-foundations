# Campus Customs — Agent Harness

**What this is:** a team of five AI agents that works the shop's support tickets (customer orders, rent notices, discount requests) for Campus Customs, a small Yale merch shop on Chapel Street.
- **What agents do:** look things up, prepare payments and purchase orders, and draft messages.
- **What only a human does:** approve money and send messages.

This document explains every part — the data, the agents, their tools, the web API, the dashboard, and the safety rules — so a manager can see exactly what the system can and cannot do.

## At a glance

| | |
|---|---|
| **Agents** | 5: Boss, Inventory, Accounting, Facilities, Customer Service (PydanticAI) |
| **Model** | `gpt-5.6-luna` for every agent, via Portkey (`PORTKEY_API_KEY` in the root `.env`) |
| **Shop data** | SQLite: `data/campus_customs_new.db` (working copy) · `data/campus_customs.db` (original, never changed) |
| **Tools** | 14 tools on one MCP server (`mcp_server/server.py`). They are the *only* way agents touch shop data |
| **Web API** | FastAPI, `backend/main.py`, http://localhost:8000 |
| **Dashboard** | React + TypeScript + Vite, `frontend/`, http://localhost:5173 |
| **Human in the loop** | Every payment and purchase order needs a human Approve click. Agents can't approve or pay |
| **Messages** | Never sent. Every customer, vendor, and landlord message is a draft on the board |
| **Audit** | Every run, tool call, approval, and reset is appended to `output/audit_trail.json` (append-only) |
| **Latest result** | Problem 9 full run: all 3 tickets resolved; checking $3,400 → $152 (see the end of this document) |

## How the pieces fit together

```
  You (human) ──► Dashboard (React, :5173)
                     │  start a run · watch agents live · Approve / Deny · see cash · read drafts
                     ▼
                  Web API (FastAPI, :8000)
                     │  runs the agent team in the background, logs everything
                     ▼
     Boss ──► Inventory · Accounting · Facilities · Customer Service   (gpt-5.6-luna)
       ▲            ▲  specialists can also consult each other directly
       └────────────┘
                     │  every lookup and change goes through …
                     ▼
                  MCP server (FastMCP) ── enforces the shop rules in code
                     ▼
                  data/campus_customs_new.db (SQLite)
```

## Ground rules

1. **Today is `desk.date_today`** (2026-08-31). Agents use it for every due, overdue, and arrival judgment, never the real clock.
2. **Only database facts.** Every number, date, and name must come from a tool result. If something isn't in the database, the agents say it's unknown.
3. **Humans approve money.** Agents only *prepare* payments and purchase orders. Money moves only when a human clicks Approve.
4. **No negative balances.** An approval that would overdraw checking is refused. Cash only goes out in this assignment.
5. **A vendor with an open invoice won't ship.** Restocks from that vendor must wait until the invoice is paid.
6. **Nothing is ever sent.** All outside messages are drafts on the board.
7. **Fresh start before a full run.** The working database is reset to the original values first.
8. **One model:** GPT Luna for every agent, to keep cost down.

---

## 1. The data

Nine tables come from the original database. Two working tables (`approvals`, `board`) are added by the MCP server to the working copy only, and a reset recreates them empty.

| Table | Fields | What it holds | Why it matters to the agents |
|---|---|---|---|
| **desk** | `date_today`, `notes` | The shop's "today" | Every due, overdue, and arrival date is measured from it |
| **tickets** | `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at` | The work queue (101 order, 102 rent, 103 discount) | Every run starts here. Its link fields point to the rows to check. Status: open → waiting_on_approval → resolved |
| **inventory** | `sku`, `name`, `size`, `qty`, `location` (key: sku + size) | Units on hand per size, and their aisle | Whether an order can be filled now, and how short it is |
| **pricing** | `sku`, `unit_cost`, `list_price` | What the shop pays and charges | The discount floor (never below cost) and purchase-order cost |
| **vendors** | `id`, `name`, `specialty`, `lead_days` | Who restocks what, and how fast | Picks the restock source and estimates arrival (today + lead days) |
| **invoices** | `id`, `vendor_id`, `amount`, `due_date`, `status`, `description` | What the shop owes vendors | An open invoice blocks that vendor from shipping and competes for cash |
| **leases** | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | The Chapel Street lease | Checks rent notices. Paying rent moves `next_due` forward one month |
| **cash_accounts** | `name`, `balance`, `date` | The checking balance | The hard limit on spending. Shown live on the dashboard |
| **payments** | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | Every payment made (invoice, rent, purchase order) | The money trail. Each row names the human approver |
| **approvals** *(working)* | `id`, `kind`, `ticket_id`, `ref_id`, `vendor_id`, `sku`, `size`, `qty`, `amount`, `account`, `reason`, `requested_by`, `status`, `decided_by`, `decided_at`, `decision_note`, `created_at` | Payment and purchase-order requests | The human gate: pending → paid (approved) or denied |
| **board** *(working)* | `id`, `ticket_id`, `author_agent`, `audience`, `recipient`, `subject`, `body`, `status`, `created_at` | Message drafts and the boss's decision notes | The only place messages go. Always `draft`, never sent |

**How the tables connect:**
- `tickets.sku` + `size` → `inventory` (stock), and `tickets.sku` → `pricing`
- `tickets.lease_id` → `leases`
- `tickets.invoice_id` → `invoices.vendor_id` → `vendors`
- `approvals` → the invoice, lease, or SKU it pays for
- `payments.ref_id` + `kind` → the invoice, lease, or purchase-order approval. `payments.account` → `cash_accounts`
- `board.ticket_id` → `tickets`

---

## 2. The agents

All five are PydanticAI agents on `gpt-5.6-luna`.
- **Code:** `backend/agents.py`.
- **Prompts:** `backend/prompts/<agent>.md` (detailed role, tools, rules, and report format).
- **Data types:** `backend/models.py`.

Each agent gets **only its own allowlist** of MCP tools. Each write tool is told which agent is calling by the system, not the model, so one agent can't pose as another.

| Agent | Job | MCP tools it can use | Talks to |
|---|---|---|---|
| **Boss** | Reads the ticket, picks the lead specialist, makes the final call, and is the only one who sets ticket status | `list_open_tickets`, `get_ticket_with_links`, `list_approval_requests`, `read_board`, `update_ticket_status` | Any specialist (`ask_<agent>_agent`) |
| **Inventory** | Stock by SKU and size, shortfalls, which vendor can restock, and when it would arrive | `get_ticket_with_links`, `check_stock_and_price`, `get_vendor_restock_options`, `post_draft_to_board` (vendor/internal) | Accounting, Facilities, Customer Service |
| **Accounting** | Cash, invoices, margins; prepares payment requests and purchase orders for the human; never pays | `get_ticket_with_links`, `get_cash_and_obligations`, `check_margin`, `check_stock_and_price`, `get_vendor_restock_options`, `request_payment_approval`, `prepare_purchase_order`, `list_approval_requests`, `post_draft_to_board` (vendor/internal) | Inventory, Facilities, Customer Service |
| **Facilities** | Lease and rent: checks notices against the lease and rent timing against cash, and drafts landlord replies | `get_ticket_with_links`, `get_cash_and_obligations`, `list_approval_requests`, `read_board`, `post_draft_to_board` (landlord/internal) | Accounting (to prepare rent), Inventory, Customer Service |
| **Customer Service** | Drafts customer messages that say what the customer gets, the price, and roughly when, and nothing internal | `get_ticket_with_links`, `check_stock_and_price`, `read_board`, `post_draft_to_board` (customer/internal) | Inventory (before every draft), Accounting (prices) |
| **Human (you)** | Approves or denies payments and purchase orders; resets the database | `record_human_approval` (Approve/Deny buttons), `reset_database_to_original` (Reset button). **No agent has these** | — |

### The team is fully connected

The boss hands the lead specialist the whole job, and specialists consult each other directly with `consult_teammate`. Examples from the real run:
- Inventory → Accounting: "is invoice 501 paid?"
- Facilities → Accounting: "prepare the rent request".
- Customer Service → Inventory: "what can the customer get, and when?"

**Limits:**
- The chain can be at most 2 levels deep (boss → specialist → peer).
- No agent can call an agent already above it in the chain, so hand-offs can't loop.

### How a ticket is worked

1. **First pass:** the boss reads the ticket and delegates. Specialists check stock, cash, and leases, prepare any payment or purchase-order requests (left **pending**), and draft messages. The ticket goes to `waiting_on_approval` if something is pending.
2. **The human decides** each request on the dashboard. **Approve pays it immediately**; **Deny** moves no money.
3. **Follow-up:** "Continue with the team". The boss reads the decisions; a paid invoice can unblock a restock purchase order, which needs another approval. Customer Service updates the draft.
4. **Resolved** when a draft on the board **clearly tells the requester what will happen and when, or that it can't be done**, and nothing the ticket depends on is still pending approval. Goods still on their way don't keep a ticket open, as long as the requester has been given the estimate.

**Ticket statuses:**
- `open`
- `in_progress`
- `waiting_on_approval`
- `waiting_on_vendor` (only if the requester hasn't been given a timing estimate yet)
- `resolved`

---

## 3. MCP tools (14)

The tools live in `mcp_server/server.py` (FastMCP) and are registered for Claude Code in `.mcp.json`. They return only database values, plus simple date math and sums. A missing row gives `found: false`, and a broken rule gives a **refusal** with the reason, never a guess.

| Tool | What it does | Reads | Writes | Used by |
|---|---|---|---|---|
| `get_ticket_with_links(ticket_id)` | The ticket plus its linked lease, invoice, invoice vendor, and the desk date | tickets, leases, invoices, vendors, desk | — | all agents |
| `check_stock_and_price(sku, size, qty_requested)` | Stock for the size and every other size, cost and list price, shortfall | inventory, pricing | — | Inventory, Accounting, Customer Service |
| `get_cash_and_obligations()` | Checking vs. open invoices (with days overdue), rent due, payments made, totals | cash_accounts, invoices, vendors, leases, payments, desk | — | Accounting, Facilities |
| `list_open_tickets(include_resolved)` | Tickets with `is_open`/`is_resolved` | tickets, desk | — | Boss, `GET /tickets` |
| `get_vendor_restock_options(specialty_contains)` | Vendors, lead days, open invoices, whether each can ship, earliest arrival | vendors, invoices, desk | — | Inventory, Accounting |
| `check_margin(sku, unit_price, qty)` | Margin and discount math at a proposed price, plus a below-cost flag | pricing | — | Accounting |
| `request_payment_approval(kind, ref_id, reason, ticket_id)` | Creates a **pending** invoice or rent payment request. The amount comes from the database. No duplicates | invoices or leases, cash_accounts, approvals | approvals | Accounting |
| `prepare_purchase_order(vendor_id, sku, size, qty, reason, ticket_id)` | Creates a **pending** purchase order (unit_cost × qty). Refused if the vendor has an open invoice | vendors, invoices, inventory, pricing, approvals, desk | approvals | Accounting |
| `list_approval_requests(status, ticket_id)` | Pending, paid, and denied requests | approvals | — | Boss, Accounting, Facilities, `GET /approvals` |
| `post_draft_to_board(audience, recipient, subject, body, ticket_id)` | Saves a **draft**. Audience is checked against role. Customer drafts that reveal internal details are refused | vendors | board | specialists |
| `read_board(ticket_id)` | Drafts and decision notes | board | — | Boss, Facilities, Customer Service, `GET /board` |
| `update_ticket_status(ticket_id, status, note)` | Sets the status and posts the boss's decision as an internal note | tickets | tickets.status, board | Boss |
| `record_human_approval(approval_id, decision, approver, note)` | **Human only.** Approve = pay in one transaction (debit cash, add a payments row, mark the invoice paid, move the lease's next due date forward, or charge the purchase order). Refused if cash is short. Deny = no money moves | approvals, cash_accounts, invoices, leases, vendors, desk | approvals, cash_accounts, payments, invoices, leases | `POST /approvals/{id}/approve` or `/deny` |
| `reset_database_to_original()` | **Human only.** Copies the original database over the working copy | campus_customs.db | campus_customs_new.db | `POST /reset` |

**The original three tools (Problem 3) and the ticket each one unlocked:**
- `get_ticket_with_links` exposed ticket 101's real blocker: linked invoice 501, $840, overdue.
- `check_stock_and_price` showed ticket 103's shortfall (8 of 20 on hand) and its $22 cost / $58 list.
- `get_cash_and_obligations` put ticket 102's $2,400 rent against $3,400 in checking and the open invoice.

---

## 4. Web API routes

Server: `backend/main.py` (FastAPI). Start it from `backend/` with `uvicorn main:app --reload --port 8000`. Every route goes through the MCP server. The browser may call it only from the dashboard's address (`localhost:5173` / `127.0.0.1:5173`).

- **Tickets:** all tickets with status, `is_open`, and `is_resolved` — `GET http://localhost:8000/tickets`
- **Run the team on a ticket:** starts the agents in the background and returns a `run_id`. One run at a time (409 if busy). `mode=auto|first_pass|follow_up`. No reset — `POST http://localhost:8000/tickets/{ticket_id}/run`
- **Run status:** running, finished, stopped, or failed, plus the boss's decision — `GET http://localhost:8000/runs/{run_id}`
- **Agent events:** each agent's task, thinking, tool calls with results, and final words. `after=` returns only new events — `GET http://localhost:8000/events?run_id=&ticket_id=&after=`
- **Approval requests:** what the agents prepared, for the Approve and Deny buttons — `GET http://localhost:8000/approvals?status=&ticket_id=`
- **Approve:** the human approves, which **pays**: debits checking, adds a payments row, and updates the invoice, lease, or purchase order. 409 if cash is short — `POST http://localhost:8000/approvals/{approval_id}/approve`
- **Deny:** marks it denied; no money moves — `POST http://localhost:8000/approvals/{approval_id}/deny`
- **Board:** every draft (never sent) and decision note — `GET http://localhost:8000/board?ticket_id=`
- **Cash:** the current checking balance from `cash_accounts` — `GET http://localhost:8000/cash`
- **Reset:** restores the working database to the original values. 409 while a run is going — `POST http://localhost:8000/reset`

---

## 5. The dashboard

React + TypeScript + Vite in `frontend/`. Start it with `npm run dev`, then open http://localhost:5173. The design choices (white page, typewriter fonts, palette from the inspiration photo, one color per agent) are in `output/design.md`.

**Always visible**
- **Fixed header:** the shop date, the **checking balance** (it shows the drop, e.g. −$840, after you approve), and **Reset database**.
- **Tickets (left):** each ticket with a rubber-stamp status (Open, Needs approval, Agents working, Complete). Click one to open it.
- **Your approval (left):** turns coral when something is waiting. Each request shows what it is, its amount, its reason, and the agent who prepared it, with **Approve & pay** and **Deny** buttons.

**Agent desk tab: one ticket, live**
1. **Run button:** Start the agent team → Team at work… → Waiting on your approval → Continue with the team. A resolved ticket shows a **COMPLETE** stamp instead.
2. **Team web:** the five agents on a dark panel, all connected.
   - **Live hand-off:** glows in the sender's color with dashes flowing toward the teammate.
   - **Reporting back:** a streak runs back the other way.
   - **Finished hand-offs:** stay as arrows.
   - **Numbered chips:** list every hand-off in order, including worker-to-worker.
3. **Agent cards:** one per agent, with a live feed of **Asked** (by whom), **Thinking**, **Doing** (each tool call in plain English), and **Saying** (its report).
4. **Run summary:** the boss's final call and next steps, plus what each agent did, its drafts, and its tools.

**Board tab: everything at once**
- **Totals:** open tickets, drafted messages, the amount waiting on you, and checking.
- **Per ticket:** where it stands (the boss's latest note), a status timeline, money requests with their outcome, and every draft (newest first, with a **Copy text** button). Completed tickets are grouped at the bottom.

---

## 6. Safety rules

### Money
- **Agents can't pay.** They only create **pending** requests. Money moves only when a human approves on the dashboard (`record_human_approval`), and agent names are refused as approvers.
- **No negative balances.** An approval that would overdraw checking is refused, and the request stays pending. In the real run, a $264 purchase order against $152 had to be denied for this reason.
- **Cash only goes out.** No tool can add money.
- **Amounts come from the database** (invoice amount, monthly rent, unit_cost × qty). A model can't type in or inflate an amount.
- **No duplicates.** A second request for the same invoice, lease, or SKU and size is refused while one is pending, and paying twice is impossible.
- **All-or-nothing payments.** Cash debit, payments row, invoice or lease update, and approval status change happen in one transaction.
- **Least privilege.** Only Accounting can request payments or prepare purchase orders. Only the Boss changes ticket status. No agent can approve or reset.
- **Identity can't be faked.** The calling agent's name is filled in by the system and checked against role rules on the server.

### Vendors and stock
- **Open invoices block restocks.** A vendor with an open invoice won't ship, so a purchase order to it is refused until the invoice is paid.
- **Lead times come only from the database.** Arrival dates are `vendors.lead_days` + `desk.date_today`, always labeled estimates.

### Customers and outside parties
- **Nothing is sent.** There is no email, text, or call tool. Every message is a `draft` on the board, and the audience is checked against the author's role (only Customer Service writes to customers).
- **Customer privacy guard.** A customer draft is **refused** if it mentions vendors or a vendor's name, invoices, purchase orders, approvals, "paid", overdue bills, the cash position, costs or margins, or lead times. Customers hear only what they get, the price, and roughly when. In the real run the guard refused 6 drafts, and Customer Service rewrote each one cleanly.
- **Honest drafts.** Prices are list price or a boss-decided discount, never below unit cost. There are no invented contact details (the database has none) and no promises beyond the vendor's lead time.

### Data and records
- **No invented facts.** Prompts require tool-sourced numbers, and tools return `found: false` or a refusal reason instead of guessing.
- **The original database is preserved.** Only the working copy changes, and it is reset before every full run.
- **Append-only audit trail.** `output/audit_trail.json` is only ever opened in append mode, with one JSON event per line. It records each run, agent task, model step, tool call (arguments and result), output, token use, human decision, and reset.
- **Secrets:** `PORTKEY_API_KEY` is read from `.env` only, and never logged, printed, or committed.

### Token and cost limits
- **One model:** `gpt-5.6-luna` for every agent, with no fallback to pricier models.
- **Per-ticket budget across all agents:** 30 model requests, 40 tool calls, 150,000 tokens. When it's hit, the run stops and the stop is logged. The heaviest real run (ticket 103's first pass) used 29 requests, about 91k tokens.
- **Per response:** 4,000 tokens maximum. **Retries:** 1. **Delegation depth:** 2.
- **One run at a time,** and runs start only when you click the button. There are no background loops.

---

## 7. Running it

```bash
.venv/bin/pip install --only-binary=cryptography -r requirements.txt
```

```bash
cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

**Command-line alternatives:**
- `backend/run_team.py` (with `--ticket`, `--follow-up`, `--skip-approvals`)
- `backend/approve.py`
- `mcp_server/smoke_test.py`, which checks the first three tools and writes `output/mcp_smoke.json`

---

## 8. Latest full run (Problem 9)

The working database was reset first (checking $3,400). All three tickets were run from the dashboard on real GPT Luna, with the human approving or denying each request.

| Ticket | Result | Human decisions | Cash |
|---|---|---|---|
| **101** Bulldog tee | **Resolved.** Size S was out of stock and the vendor was blocked by overdue invoice 501. The invoice was paid, then a 1-unit restock was ordered. The customer draft gives an estimated arrival of Sept 5, 2026 and offers sizes M/L/XL now | #1 invoice 501 ✔ · #3 1-tee purchase order ✔ | −$840, −$8 |
| **102** Rent due | **Resolved.** The notice matched lease 1. Rent was paid, and the landlord draft confirms it | #2 rent ✔ | −$2,400 |
| **103** Bulk hoodies | **Resolved.** Only 8 of 20 were in stock. A 12-unit purchase order ($264) was denied because it exceeded cash. The customer draft offers 8 now at $46.40 (20% off) and says the other 12 can't be supplied right now | #4 12-hoodie purchase order ✘ | $0 |

**Checking:** $3,400 → **$152.00**, which matches `cash_accounts`.

**Details:**
- `output/resolved_tickets.json` — the run data.
- `output/desk_tickets.html` — expected vs. actual, and the cash ledger.
- `output/resolved_board.html` — dashboard screenshots.

**What we learned from the run:**
- **Peer communication worked.** There were 13 worker-to-worker consults across the three tickets.
- **Two quirks to fix:**
  - **A draft with no ticket id:** one draft was saved without its ticket id. It's now filled in automatically.
  - **Rent due date:** after rent is paid, the lease's `next_due` moves forward, and Facilities read that as a disagreement with the notice. Its prompt should explain that the date moves after payment.
- **The discount needs no human sign-off.** Only payments and purchase orders require approval, so a sign-off step for discounts could be added.
