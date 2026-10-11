# HW5 — Campus Customs Agent Desk

Five PydanticAI agents (Boss, Inventory, Accounting, Facilities, Customer Service) work the support tickets of **Campus Customs**, a small Yale merch shop.
- **Agents' tools:** they read and change shop data **only** through an MCP server over a SQLite database.
- **Approvals:** a human approves every payment and purchase order on a React dashboard.
- **Messages:** never sent. They stay as drafts on the board.

**Model and access:** every agent uses `gpt-5.6-luna` through Portkey (`PORTKEY_API_KEY`).

For the full design, read [`output/harness.md`](output/harness.md). It covers every table, tool, agent, API route, the dashboard, and the safety rules.

## Layout

```
HW5/
├── AI_prompts.md            prompt log for Problems 1–11
├── README.md                (this file)
├── requirements.txt         Python dependencies (MCP server, agents, backend)
├── .env.example             copy to .env and add your PORTKEY_API_KEY
├── .gitignore
├── .mcp.json                registers the MCP server (paths relative to HW5/)
├── data/
│   ├── campus_customs.db       original, never modified
│   └── campus_customs_new.db   working copy the agents read and update
├── mcp_server/
│   ├── server.py            FastMCP server: 14 tools, shop rules enforced in code
│   ├── smoke_test.py        tests the first 3 tools → output/mcp_smoke.json
│   └── README.md
├── backend/
│   ├── main.py              FastAPI routes (tickets, run, events, approvals, board, cash, reset)
│   ├── models.py            data types (agent outputs, run context, API bodies)
│   ├── agents.py            the 5 agents, delegation, budgets, MCP wiring
│   ├── audit.py             append-only audit trail
│   ├── run_team.py          command-line runner (optional)
│   ├── approve.py           command-line approvals (optional)
│   └── prompts/             boss.md · inventory.md · accounting.md · facilities.md · customer_service.md
├── frontend/                React + TypeScript + Vite dashboard
└── output/
    ├── harness.md               how everything works (manager-readable)
    ├── mcp_smoke.json           MCP tool test evidence
    ├── desk_tickets.html        expected vs. actual per ticket, cash ledger, reflections
    ├── design.md                dashboard design choices
    ├── resolved_tickets.json    outcome of the full 3-ticket run
    ├── resolved_board.html      screenshots of the resolved dashboard (double-click to open)
    ├── audit_trail.json         every run, tool call, approval, and reset (append-only, one JSON event per line)
    └── github_url.txt           link to this folder on GitHub
```

## Setup (once)

You need Python 3.12+ (tested on 3.14), Node 20+, and a Portkey API key. Run everything from this `HW5/` folder.

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install --only-binary=cryptography -r requirements.txt
```

```bash
cp .env.example .env
```

Then open `.env` and put your key after `PORTKEY_API_KEY=`. The real `.env` is git-ignored and never committed.

`--only-binary=cryptography` avoids a source build that fails on some Macs.

## Running it

### 1. Copy the original database to the working copy (for a clean run)

The agents only ever change `data/campus_customs_new.db`. **The copy in this repo is the state after our full run** (all tickets resolved, $152 left in checking). Start clean by copying the original over it:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

The working tables `approvals` and `board` are recreated automatically the first time the MCP server touches the database.

### 2. Start the MCP server

The backend **starts the MCP server for you**: it reads `.mcp.json` and launches `mcp_server/server.py` over stdio. You only need to run it yourself to test it, or to connect it to an MCP client such as Claude Code, which picks up `.mcp.json` when opened in this folder:

```bash
.venv/bin/python mcp_server/server.py
```

The server then waits on stdin for an MCP client (press Ctrl-C to stop). To check that the tools work against the database:

```bash
.venv/bin/python mcp_server/smoke_test.py
```

### 3. Start the FastAPI backend (port 8000)

In a new terminal:

```bash
cd backend && ../.venv/bin/python -m uvicorn main:app --reload --port 8000
```

API docs are at http://localhost:8000/docs. The browser is allowed to call the API from the dashboard's address (`localhost:5173`).

### 4. Start the React board (port 5173)

In another terminal:

```bash
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173**.

### 5. Reset the database before a full 3-ticket run

Always start a full run from the original values. Use any one of these:
- the **Reset database** button in the dashboard header;
- `curl -X POST http://localhost:8000/reset`;
- with the backend stopped, the `cp` command from step 1.

Checking should read **$3,400.00**, and tickets 101–103 should read **OPEN**.

### 6. Work the tickets

1. Click a ticket, then **Start the agent team**. Watch the team web and agent cards fill in live.
2. When a request appears under **Your approval**, click **Approve & pay** or **Deny**. Approving is what moves money, and checking updates in the header.
3. Click **Continue with the team** so the agents act on your decision. Repeat until the ticket is stamped **COMPLETE**.
4. The **Board** tab summarizes every ticket's status, money, and drafted messages.

Our run (101 → 102 → 103): approve invoice 501 ($840), the rent ($2,400), and the 1-tee purchase order ($8). Deny the 12-hoodie purchase order ($264, more than the cash left). That ends with all three resolved and checking at $152.00.

#### Command-line alternative (no dashboard)

`run_team.py` resets the database, works all open tickets, and asks you to approve each request in the terminal:

```bash
.venv/bin/python backend/run_team.py
```

## Safety, in short

- Agents can't pay. They only prepare **pending** requests, and money moves only on a human approval.
- An approval that would make checking go negative is refused.
- No email, text, or call tool exists. Every message is a draft on the board.
- Customer drafts that mention vendors, invoices, payments, approvals, costs, or lead times are refused by the MCP server.
- Every run, tool call, approval, and reset is **appended** to `output/audit_trail.json`.
- Each ticket run is capped at 30 model requests and 150k tokens, using one model (`gpt-5.6-luna`).
