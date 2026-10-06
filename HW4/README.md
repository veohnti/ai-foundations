# Campus Customs (HW4)

An online shop for Yale apparel with an AI shop assistant. React + Vite +
TypeScript front end, FastAPI back end, and a PydanticAI agent (`gpt-5.6-terra`
via Portkey) that answers from the shop's database.

**Read next:** [`output/harness.md`](output/harness.md) explains how the whole
system works (models, tools, safety, specs). The other files in `output/` cover
the design, usability, and test evidence.

## Layout

```
HW4/
├── AI_prompts.md
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── frontend/              # Vite React TypeScript app
├── backend/
│   ├── main.py            # FastAPI app: run with: uvicorn main:app --reload --port 8000
│   ├── agent.py
│   ├── models.py
│   ├── tools.py
│   └── prompts/
│       └── prompt.md
├── scripts/               # helper scripts (photo cleanup, offline copy)
└── output/
    ├── harness.md
    ├── design.md
    ├── usability.md
    ├── app_check.html
    ├── app_check_images/  # screenshots linked from app_check.html
    └── audit_trail.json
```

The agent itself is the four files in `backend/`: `prompts/prompt.md`,
`agent.py`, `tools.py`, and `models.py`.

## 1. Place the data pack

The database and product photos are **not** in git. Put the data pack inside
`HW4/` so it looks like this:

```
HW4/data/
├── campus_customs.db
└── products/          # images referenced by the catalogue
```

## 2. Add your API key

```bash
cd HW4
cp .env.example .env
```

Then edit `.env` and replace the placeholder with your Portkey key:

```
PORTKEY_API_KEY=your-real-key
```

`.env` is ignored by git, so it is never committed.

## 3. Install (once)

You need Python 3.11+ and Node.js 20+.

```bash
cd HW4
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd frontend && npm install
```

**Optional (recommended):** the data pack's photos have black backgrounds. This
turns them white to match the site, and keeps the originals in
`data/products_original/`:

```bash
cd HW4
.venv/bin/python scripts/whiten_backgrounds.py
```

## 4. Run the back end

In one terminal:

```bash
cd HW4/backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

Check it with <http://localhost:8000/api/health>; it should report 102
products. On first start the backend creates its `sessions` table and prepares
the seeded test account (below).

## 5. Run the front end

In a second terminal:

```bash
cd HW4/frontend
npm run dev -- --port 5174
```

Then open **<http://localhost:5174>**. The dev server forwards `/api` and
`/images` to the back end on port 8000.

## Try it

- **Test login:** `test@campuscustoms.yale.edu` / `password`, or create your own
  account. Logged-in customers get their chat history saved and restored, and
  the assistant greets them by name.
- **Chat** (the button at the bottom right):
  - "How many of this do you have in each size?" on a product page gives real
    stock per size.
  - "What crewnecks do you have?" fills the Products page with the matching
    products.
  - "What's the warmest thing under $100?" gives ranked picks with reasons.
  - "I need a gift" asks one clarifying question with tappable answers.
- **Compare:** open any product, then "Compare with another item".

Every chat turn is logged to `output/audit_trail.json` (append-only).

## Optional extras

| Command | What it does |
|---|---|
| `.venv/bin/python scripts/export_static_site.py` (from `HW4/`) | Builds `output/website/index.html`, a copy of the site that opens straight from the file with no server (chat and accounts are off in it) |
| `node scripts/app_check.mjs` (from `HW4/frontend/`, both servers running, Google Chrome installed) | Re-runs the live-app check and re-captures the screenshots in `output/app_check_images/` |
| `../.venv/bin/python agent.py "your question"` (from `HW4/backend/`) | Asks the shop assistant one question from the terminal |
