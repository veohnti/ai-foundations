"""Tools the Campus Customs agent can call.

Everything here is read-only catalogue and inventory access against the shop
database. The agent reaches these through thin wrappers registered in agent.py;
keeping the real work here means the API and the agent share one definition of
"search the catalogue" and "check stock".

This module owns its own tiny DB connector rather than importing from main.py,
so there is no import cycle (main -> agent -> tools -> main).
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)

from models import CustomerProfile, HistoryMessage, ProductCard, ProductInfo, SizeStock, StockCheck

# backend/tools.py -> backend -> HW4; the DB lives at HW4/data/.
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "campus_customs.db"

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _image_url(image_file_path: str) -> str:
    """Catalogue stores a relative path; the app serves images at /images/<file>."""
    return "/images/" + Path(image_file_path).name + "?v=white-bg-1"  # see main.IMAGE_VERSION


def _in_stock_sizes(conn: sqlite3.Connection, product_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)
    ).fetchall()
    have = {r["size"]: r["quantity"] for r in rows}
    return [s for s in SIZE_ORDER if have.get(s, 0) > 0]


def _card(conn: sqlite3.Connection, row: sqlite3.Row) -> ProductCard:
    return ProductCard(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        price=row["price"],
        image_url=_image_url(row["image_file_path"]),
        colors=json.loads(row["colors"]),
        available_sizes=_in_stock_sizes(conn, row["product_id"]),
    )


# Shopper words -> the fragment that appears in the stored garment_type values.
# garment_type is not normalized ("hoodie", "pullover hoodie", "full-zip hooded
# sweatshirt"), so categories are matched on a shared fragment.
GARMENT_SYNONYMS = {
    "hoodie": "hood", "hoody": "hood", "hooded": "hood", "hood": "hood",
    "tee": "t-shirt", "tshirt": "t-shirt", "t shirt": "t-shirt", "t-shirt": "t-shirt",
    "shirt": "shirt",
    "crew": "crewneck", "crew neck": "crewneck", "crewneck": "crewneck",
    "quarter zip": "quarter-zip", "quarter-zip": "quarter-zip", "1/4 zip": "quarter-zip",
    "half zip": "quarter-zip", "zip": "zip", "full zip": "full-zip", "full-zip": "full-zip",
    "jacket": "jacket", "fleece": "fleece", "bomber": "bomber",
    "sweatshirt": "sweatshirt", "mockneck": "mockneck", "mock neck": "mockneck",
}


def normalize_garment_type(garment_type: str) -> str:
    """Map a shopper's category word to the fragment stored in garment_type.

    Lowercases, drops a plural "s"/"es" ("crewnecks" -> "crewneck",
    "hoodies" -> "hoodie" -> "hood"), then applies GARMENT_SYNONYMS.
    """
    term = garment_type.strip().lower()
    if term in GARMENT_SYNONYMS:
        return GARMENT_SYNONYMS[term]
    for suffix in ("es", "s"):
        if term.endswith(suffix) and term[: -len(suffix)] in GARMENT_SYNONYMS:
            return GARMENT_SYNONYMS[term[: -len(suffix)]]
    return term[:-1] if term.endswith("s") and len(term) > 3 else term


def search_catalogue(
    query: str | None = None,
    garment_type: str | None = None,
    max_price: float | None = None,
    color: str | None = None,
    limit: int | None = 6,
) -> list[ProductCard]:
    """Search the catalogue and return product cards.

    All filters are optional and combine with AND. `garment_type` is normalized
    (see normalize_garment_type) and matched as a fragment of the stored value.
    `query` is split into words and every word must appear somewhere in the
    name, type, description, colors, or tags, so "navy crewneck" matches a row
    whose name says crewneck and whose colors say navy. `limit=None` returns
    every match (used for page updates). Results are UI-ready ProductCards with
    in-stock sizes only, cheapest first.
    """
    type_fragment = normalize_garment_type(garment_type) if garment_type else None
    words = query.lower().split() if query else []

    with _connect() as conn:
        rows = conn.execute("SELECT * FROM catalogue").fetchall()

        def matches(row: sqlite3.Row) -> bool:
            if max_price is not None and row["price"] > max_price:
                return False
            if type_fragment and type_fragment not in row["garment_type"].lower():
                return False
            if color and color.lower() not in row["colors"].lower():
                return False
            if words:
                haystack = " ".join(
                    [row["name"], row["garment_type"], row["description"],
                     row["colors"], row["search_tags"]]
                ).lower()
                if not all(w in haystack for w in words):
                    return False
            return True

        hits = [r for r in rows if matches(r)]
        hits.sort(key=lambda r: (r["price"], r["name"]))
        if limit is not None:
            hits = hits[:limit]
        return [_card(conn, r) for r in hits]


def cards_for_ids(product_ids: list[str]) -> list[ProductCard]:
    """Rebuild product cards from the database for the given ids, in order.

    Unknown ids are dropped and duplicates collapsed. Used to replace the cards
    the model attaches to a chat reply with the database's own values, so a
    card's name, price, image, and sizes can never drift from the catalogue.
    """
    cards: list[ProductCard] = []
    seen: set[str] = set()
    with _connect() as conn:
        for pid in product_ids:
            if pid in seen:
                continue
            seen.add(pid)
            row = conn.execute(
                "SELECT * FROM catalogue WHERE product_id = ?", (pid,)
            ).fetchone()
            if row is not None:
                cards.append(_card(conn, row))
    return cards


def get_product_info(product_id: str) -> ProductInfo | None:
    """Look up one product's description, price, colors, and stock.

    Returns a ProductInfo with per-size stock and a total, or None if no product
    has that id. Every value is read from the database — `catalogue` for the
    description/price/colors and `inventory` for the quantities — so the agent
    can answer product, price, and stock questions without inventing anything.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM catalogue WHERE product_id = ?", (product_id,)
        ).fetchone()
        if row is None:
            return None
        inv = conn.execute(
            "SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)
        ).fetchall()

    have = {r["size"]: r["quantity"] for r in inv}
    sizes = [
        SizeStock(size=s, quantity=have[s], in_stock=have[s] > 0)
        for s in SIZE_ORDER
        if s in have
    ]
    total = sum(s.quantity for s in sizes)
    return ProductInfo(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        description=row["description"],
        price=row["price"],
        colors=json.loads(row["colors"]),
        image_url=_image_url(row["image_file_path"]),
        total_in_stock=total,
        in_stock=total > 0,
        sizes=sizes,
    )


def check_size_stock(product_id: str, size: str) -> StockCheck:
    """How many of one product, in one specific size, are on hand right now.

    `exists` is False when the shop simply doesn't carry that product/size pair,
    which is different from carrying it but being sold out (`exists` True,
    `in_stock` False). Reads the single matching `inventory` row.
    """
    size = size.strip().upper()
    with _connect() as conn:
        row = conn.execute(
            "SELECT quantity FROM inventory WHERE product_id = ? AND size = ?",
            (product_id, size),
        ).fetchone()
    if row is None:
        return StockCheck(product_id=product_id, size=size, exists=False,
                          in_stock=False, quantity=0)
    return StockCheck(product_id=product_id, size=size, exists=True,
                      in_stock=row["quantity"] > 0, quantity=row["quantity"])


# --------------------------------------------------------------------------
# Customer memory (logged-in shoppers only)
# --------------------------------------------------------------------------
# Chat history lives in the existing `chat_messages` table: one row per turn,
# keyed by user_id, with the product cards shown on that turn kept in
# products_json. Nothing here is ever called for an anonymous shopper.


def get_customer(user_id: int) -> CustomerProfile | None:
    """The customer fields the agent is allowed to see. Never the password hash."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, name, email, first_name, last_name FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return CustomerProfile(
        id=row["id"], name=row["name"], email=row["email"],
        first_name=row["first_name"], last_name=row["last_name"],
    )


def _stored_product_ids(products_json: str | None) -> list[str]:
    """Product ids from a products_json cell, whatever shape the row was saved in.

    Older seed rows hold whole catalogue rows; rows saved by this app hold
    product cards. Both carry `product_id`, which is all that's needed: cards
    are rebuilt from the catalogue so they show today's price and stock.
    """
    if not products_json:
        return []
    try:
        items = json.loads(products_json)
    except (TypeError, ValueError):
        return []
    return [i["product_id"] for i in items if isinstance(i, dict) and "product_id" in i]


def load_chat_history(user_id: int, limit: int = 30) -> list[HistoryMessage]:
    """The customer's most recent chat turns, oldest first."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content, products_json, created_at FROM chat_messages
            WHERE user_id = ? ORDER BY id DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [
        HistoryMessage(
            role=r["role"],
            content=r["content"],
            products=cards_for_ids(_stored_product_ids(r["products_json"])),
            created_at=r["created_at"],
        )
        for r in reversed(rows)
    ]


def save_chat_turn(
    user_id: int, user_message: str, reply: str, products: list[ProductCard]
) -> None:
    """Append one exchange (shopper message + assistant reply) to chat_messages."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'user', ?, NULL)",
            (user_id, user_message),
        )
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'assistant', ?, ?)",
            (user_id, reply, json.dumps([p.model_dump() for p in products])),
        )
        conn.commit()


# --------------------------------------------------------------------------
# Data for the back-end sub-agents (ranking and clarifying)
# --------------------------------------------------------------------------

# Same groupings the website's category filter uses.
CATEGORY_GROUPS = [
    ("hoodies", lambda t: "hood" in t),
    ("crewnecks", lambda t: "crewneck" in t),
    ("t-shirts", lambda t: "t-shirt" in t),
    ("quarter-zips", lambda t: "quarter-zip" in t),
    ("jackets & fleece", lambda t: "jacket" in t or "fleece" in t),
    ("other", lambda t: True),
]


def _category_of(garment_type: str) -> str:
    t = garment_type.lower()
    for name, test in CATEGORY_GROUPS:
        if test(t):
            return name
    return "other"


def ranking_candidates(
    query: str | None = None,
    garment_type: str | None = None,
    max_price: float | None = None,
    color: str | None = None,
    limit: int = 40,
) -> list[dict]:
    """In-stock products matching the filters, with everything the ranker needs.

    Description and tags are included because "warmest" or "good for game day"
    can only be judged from them. Products with no stock at all are left out,
    since there's no point recommending something that can't be bought.

    When more than `limit` products match, the pool is a balanced spread taken
    round-robin across categories. Search results are sorted cheapest-first, so
    simply cutting the list would hand the ranker nothing but $32 tees and it
    could never pick, say, a fleece jacket as the warmest option.
    """
    cards = [c for c in search_catalogue(query, garment_type, max_price, color, limit=None)
             if c.available_sizes]

    if len(cards) > limit:
        groups: dict[str, list[ProductCard]] = {}
        for c in cards:
            groups.setdefault(_category_of(c.garment_type), []).append(c)
        queues = list(groups.values())
        cards = []
        while len(cards) < limit and any(queues):
            for q in queues:
                if q and len(cards) < limit:
                    cards.append(q.pop(0))

    out = []
    with _connect() as conn:
        for c in cards:
            row = conn.execute(
                "SELECT description, search_tags FROM catalogue WHERE product_id = ?",
                (c.product_id,),
            ).fetchone()
            out.append({
                "product_id": c.product_id,
                "name": c.name,
                "garment_type": c.garment_type,
                "price": c.price,
                "colors": c.colors,
                "sizes_in_stock": c.available_sizes,
                "description": row["description"],
                "tags": json.loads(row["search_tags"]),
            })
    return out


def catalogue_facets(
    query: str | None = None,
    garment_type: str | None = None,
    max_price: float | None = None,
    color: str | None = None,
) -> dict:
    """What the catalogue actually offers for these filters, for the clarifying agent.

    Counts by category, the most common colors, and the price range of the
    matching products, so a clarifying question only offers choices that exist.
    """
    cards = search_catalogue(query, garment_type, max_price, color, limit=None)
    categories: dict[str, int] = {}
    colors: dict[str, int] = {}
    for c in cards:
        cat = _category_of(c.garment_type)
        categories[cat] = categories.get(cat, 0) + 1
        for col in c.colors:
            colors[col.lower()] = colors.get(col.lower(), 0) + 1
    prices = sorted({c.price for c in cards})
    return {
        "matching_products": len(cards),
        "by_category": dict(sorted(categories.items(), key=lambda kv: -kv[1])),
        "top_colors": dict(sorted(colors.items(), key=lambda kv: -kv[1])[:8]),
        "price_points": prices,
        "filters_applied": {
            "query": query, "garment_type": garment_type,
            "max_price": max_price, "color": color,
        },
    }


# --------------------------------------------------------------------------
# Safety: redact sensitive details before anything is stored
# --------------------------------------------------------------------------
# Backs up the prompt's "never ask for sensitive information" rule: if a shopper
# volunteers a card number, SSN, or password anyway, it is masked before the
# message is saved to chat_messages or the audit trail.

# Payment card: 13-19 digits, optionally grouped by spaces or dashes.
_CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
# US Social Security number.
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# "password is X", "pw: X", "passcode X" -> keep the word, drop the value.
_PASSWORD = re.compile(r"(?i)\b(pass(?:word|code)?|pw)\b(\s*(?:is|:|=)?\s*)(\S+)")


def redact_sensitive(text: str) -> str:
    """Mask card numbers, SSNs, and anything given as a password."""
    if not text:
        return text
    text = _SSN.sub("[redacted SSN]", text)
    text = _CARD.sub("[redacted card number]", text)
    text = _PASSWORD.sub(lambda m: f"{m.group(1)}{m.group(2)}[redacted]", text)
    return text


# --------------------------------------------------------------------------
# Audit trail: append-only log of agent activity (output/audit_trail.json)
# --------------------------------------------------------------------------
# One entry per agent run (shop assistant, ranking agent, clarifying agent),
# linked by turn_id: time, user id or "guest" (never an email), each tool call
# with short args/result, model requests used, and the stop reason.
#
# Append-only: the file is a JSON array and new entries are written in place
# over its closing "]" only, so earlier entries are never rewritten, the file
# is never truncated or recreated once it exists, and it stays valid JSON. An
# exclusive lock serialises concurrent chats. Logging failures are printed and
# swallowed so the audit trail can never break a shopper's chat.

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"
SHORT = 240  # characters kept from any argument or result


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def short(value: Any, limit: int = SHORT) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    text = redact_sensitive(" ".join(text.split()))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def steps_from_messages(messages: list[ModelMessage]) -> list[dict]:
    """One step per tool call: its time, name, short args, and short result."""
    steps: list[dict] = []
    by_call_id: dict[str, dict] = {}
    for message in messages:
        if isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, ToolCallPart):
                    step = {
                        "time": message.timestamp.isoformat(timespec="milliseconds"),
                        "tool": part.tool_name,
                        "args": short(part.args if part.args is not None else {}),
                        "result": None,
                    }
                    steps.append(step)
                    by_call_id[part.tool_call_id] = step
        elif isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, ToolReturnPart) and part.tool_call_id in by_call_id:
                    by_call_id[part.tool_call_id]["result"] = short(part.content)
                elif isinstance(part, RetryPromptPart) and part.tool_call_id in by_call_id:
                    by_call_id[part.tool_call_id]["result"] = "RETRY: " + short(part.content, 160)
    return steps


def append_entry(entry: dict) -> None:
    """Append one entry to the JSON array without rewriting anything before it."""
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(entry, ensure_ascii=False, indent=2)
        # "a+" creates the file if missing and never truncates it.
        with open(AUDIT_PATH, "a+b") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size == 0:
                    f.write(("[\n" + body + "\n]\n").encode("utf-8"))
                    return
                # Find the closing bracket at the end of the file and write from
                # there; only that "]" (and trailing whitespace) is replaced.
                f.seek(max(0, size - 64))
                tail = f.read()
                close = tail.rstrip().rfind(b"]")
                if close == -1:
                    raise ValueError("audit_trail.json does not end with ']'")
                pos = size - len(tail) + close
                # On macOS/Linux "a" mode forces writes to the end, so reopen r+b.
                with open(AUDIT_PATH, "r+b") as w:
                    w.seek(pos)
                    w.write((",\n" + body + "\n]\n").encode("utf-8"))
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as exc:  # noqa: BLE001
        print(f"[audit] could not write audit entry: {exc}")


def record_run(
    *,
    turn_id: str,
    agent: str,
    started: str,
    user: str,
    messages: list[ModelMessage],
    requests: int | None,
    stop_reason: str,
    summary: str | None = None,
    extra: dict | None = None,
) -> None:
    entry = {
        "turn_id": turn_id,
        "agent": agent,
        "started": started,
        "finished": now(),
        "user": user,
        "steps": steps_from_messages(messages),
        "model_requests": requests,
        "stop_reason": stop_reason,
        "summary": short(summary) if summary else None,
    }
    if extra:
        entry.update(extra)
    append_entry(entry)
