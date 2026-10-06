"""Campus Customs backend.

For now this just reads the shop database and serves products and their images
to the React front end. Later problems grow this into the agent backend, so the
database access is kept in small functions that a tool layer can reuse.
"""

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from agent import run_chat
from models import ChatReply, ChatRequest, HistoryMessage
from tools import get_customer, load_chat_history

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "campus_customs.db"
IMAGES_DIR = BASE_DIR / "data" / "products"

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
IMAGE_VERSION = "?v=white-bg-1"

# --------------------------------------------------------------------------
# Passwords and login sessions
# --------------------------------------------------------------------------
# Passwords: PBKDF2-HMAC-SHA256, 390,000 iterations, random 16-byte salt per
# account, stored as pbkdf2_sha256$<iterations>$<salt>$<hash>, checked in
# constant time. There is no way to turn a stored hash back into a password.

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 390_000  # OWASP-recommended floor for PBKDF2-HMAC-SHA256
SALT_BYTES = 16


def hash_password(password: str, *, iterations: int = ITERATIONS) -> str:
    """Return a self-describing hash string for a new or changed password."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check a candidate password against a stored hash, in constant time."""
    try:
        algorithm, iter_str, salt_hex, hash_hex = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        iterations = int(iter_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


# --------------------------------------------------------------------------
# Login sessions
# --------------------------------------------------------------------------
# After a successful login or signup the server issues a random session token
# in an HttpOnly cookie. Each later request (chat, chat history, /api/me) finds
# the customer from that cookie, so the browser can never claim to be another
# user by sending a different user id.
#
# Only a SHA-256 hash of the token is stored in the `sessions` table: someone
# who reads the database gets hashes, not working sessions. A plain hash (not
# PBKDF2) is enough because the token is 32 random bytes, not a guessable
# password.


SESSION_COOKIE = "cc_session"
SESSION_DAYS = 30


def ensure_sessions_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    conn.commit()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    """Start a session for this user and return the raw token for the cookie."""
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) "
        "VALUES (?, ?, datetime('now', ?))",
        (_token_hash(token), user_id, f"+{SESSION_DAYS} days"),
    )
    conn.commit()
    return token


def user_id_for_session(conn: sqlite3.Connection, token: str | None) -> int | None:
    """The user id behind a session token, or None if missing, unknown, or expired."""
    if not token:
        return None
    row = conn.execute(
        "SELECT user_id FROM sessions WHERE token_hash = ? AND expires_at > datetime('now')",
        (_token_hash(token),),
    ).fetchone()
    return row[0] if row else None


def delete_session(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        conn.commit()


app = FastAPI(title="Campus Customs API", version="0.1.0")

# The Vite dev server runs on a different port, so the browser needs CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


# The data pack seeds one test account whose documented login is published
# with the assignment. Its stored hash uses an older format this app doesn't
# verify, so on a fresh data pack it's re-hashed once with that documented
# password. Only this one account is touched, and only while it's still in the
# old format; real customers' passwords are never known or changed.
SEED_TEST_EMAIL = "test@campuscustoms.yale.edu"
SEED_TEST_PASSWORD = "password"  # published with the assignment's data pack


@app.on_event("startup")
def create_runtime_tables() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        # The seed database has no sessions table; create it once if missing.
        ensure_sessions_table(conn)
        row = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?", (SEED_TEST_EMAIL,)
        ).fetchone()
        if row and len(row[0].split("$")) != 4:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE email = ?",
                (hash_password(SEED_TEST_PASSWORD), SEED_TEST_EMAIL),
            )
            conn.commit()
            print("[startup] re-hashed the seeded test account to the app's PBKDF2 format")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def product_from_row(row: sqlite3.Row) -> dict:
    """Shape a catalogue row for the front end.

    colors and search_tags are stored as JSON strings; the image path is turned
    into a URL the browser can actually request.
    """
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "garment_type": row["garment_type"],
        "description": row["description"],
        "colors": json.loads(row["colors"]),
        "search_tags": json.loads(row["search_tags"]),
        "price": row["price"],
        # ?v= changes whenever the photos are reprocessed, so browsers fetch the
        # new white-background versions instead of their cached black ones.
        "image_url": "/images/" + Path(row["image_file_path"]).name + IMAGE_VERSION,
    }


@app.get("/api/health")
def health() -> dict:
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM catalogue").fetchone()[0]
    return {"status": "ok", "products": count}


@app.get("/api/products")
def list_products() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM catalogue ORDER BY name").fetchall()
    return [product_from_row(row) for row in rows]


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> dict:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM catalogue WHERE product_id = ?", (product_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        sizes = conn.execute(
            "SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)
        ).fetchall()

    product = product_from_row(row)
    by_size = {s["size"]: s["quantity"] for s in sizes}
    product["sizes"] = [
        {"size": size, "quantity": by_size[size], "in_stock": by_size[size] > 0}
        for size in SIZE_ORDER
        if size in by_size
    ]
    product["in_stock"] = any(s["in_stock"] for s in product["sizes"])
    return product


# --------------------------------------------------------------------------
# Accounts & authentication
# --------------------------------------------------------------------------
# These endpoints create accounts and log users in. Passwords are hashed by
# backend.auth before they ever touch the database; the plaintext is used only
# to compute the hash inside the request and is never stored or logged.

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupRequest(BaseModel):
    email: str
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    password: str = Field(min_length=8)
    confirm_password: str

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address.")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


def user_public(row: sqlite3.Row) -> dict:
    """The user fields that are safe to return — never the password hash."""
    return {
        "id": row["id"],
        "email": row["email"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "name": row["name"],
    }


@app.post("/api/signup")
def signup(req: SignupRequest, response: Response) -> dict:
    if req.password != req.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    full_name = f"{req.first_name.strip()} {req.last_name.strip()}"
    stored = hash_password(req.password)

    with connect() as conn:
        existing = conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (req.email,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="An account with that email already exists.")

        cursor = conn.execute(
            """
            INSERT INTO users (name, email, password_hash, first_name, last_name)
            VALUES (?, ?, ?, ?, ?)
            """,
            (full_name, req.email, stored, req.first_name.strip(), req.last_name.strip()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()

    start_session(response, row["id"])
    return {"user": user_public(row)}


@app.post("/api/login")
def login(req: LoginRequest, response: Response) -> dict:
    email = req.email.strip().lower()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

    # Same error whether the email is unknown or the password is wrong, so the
    # response can't be used to probe which emails have accounts.
    if row is None or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    start_session(response, row["id"])
    return {"user": user_public(row)}


def start_session(response: Response, user_id: int) -> None:
    """Issue a session cookie for a user who just logged in or signed up.

    HttpOnly so page scripts can't read it; SameSite=Lax so other sites can't
    ride on it. (Add secure=True once this is served over HTTPS.)
    """
    with connect() as conn:
        token = create_session(conn, user_id)
    response.set_cookie(
        SESSION_COOKIE, token,
        max_age=SESSION_DAYS * 24 * 3600, httponly=True, samesite="lax", path="/",
    )


def current_user_id(request: Request) -> int | None:
    """The logged-in user's id from the session cookie, or None for a guest."""
    with connect() as conn:
        return user_id_for_session(conn, request.cookies.get(SESSION_COOKIE))


@app.get("/api/me")
def me(request: Request) -> dict:
    """Who the session cookie belongs to: `{"user": {...}}`, or `{"user": null}`
    for a guest. The website calls this on load so a stale "logged in" state in
    the browser can't outlive the real session. Being a guest is a normal
    answer here, not an error."""
    user_id = current_user_id(request)
    if user_id is None:
        return {"user": None}
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return {"user": user_public(row) if row else None}


@app.post("/api/logout")
def logout(request: Request, response: Response) -> dict:
    with connect() as conn:
        delete_session(conn, request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


# --------------------------------------------------------------------------
# Chat — the PydanticAI agent
# --------------------------------------------------------------------------
# The website's floating chat panel POSTs here. The request carries the new
# message plus any running history; the agent (backend/agent.py) answers using
# the catalogue/inventory tools and returns markdown text plus product cards.


@app.get("/api/chat/history", response_model=list[HistoryMessage])
def chat_history(request: Request) -> list[HistoryMessage]:
    """The logged-in customer's saved chat, so the panel can repopulate on login
    or reload. Guests have no saved chat, so they get 401."""
    user_id = current_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return load_chat_history(user_id)


@app.post("/api/chat", response_model=ChatReply)
async def chat(req: ChatRequest, request: Request) -> ChatReply:
    # Who's asking comes from the session cookie, never from the request body.
    user_id = current_user_id(request)
    customer = get_customer(user_id) if user_id is not None else None
    try:
        return await run_chat(req.message, req.history, customer, req.page_context)
    except Exception as exc:  # noqa: BLE001
        # Never leak a stack trace or provider/internal detail to the browser;
        # log-and-wrap into a clean 502 the UI can show as a friendly failure.
        print(f"[chat] agent error: {exc}")
        raise HTTPException(
            status_code=502,
            detail="The shop assistant is having a moment. Please try again.",
        )
