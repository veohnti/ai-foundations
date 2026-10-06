"""Shared Pydantic types for the Campus Customs chat backend.

These cover two things:
  * the shapes the chat API accepts and returns (ChatRequest / ChatReply), and
  * the product card the agent emits when it wants the web app to render a
    product visually next to its text answer (ProductCard).

Keeping them here means the agent (agent.py), its tools (tools.py), and the API
(main.py) all agree on one definition of a "product card" and one definition of
a "chat reply".
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProductCard(BaseModel):
    """A single product the agent chose to surface, shaped for the UI.

    This is deliberately a trimmed view of a catalogue row — just what a card in
    the chat panel needs to show, plus the id and a size list so the front end
    can link through to the full product page.
    """

    product_id: str
    name: str
    garment_type: str
    price: float
    image_url: str
    colors: list[str] = Field(default_factory=list)
    available_sizes: list[str] = Field(default_factory=list)
    # Set only when the ranking agent recommended this product: a one-line,
    # data-backed reason ("Fleece-lined, warmest option under $100").
    reason: str | None = None


class SizeStock(BaseModel):
    """Stock for one product in one size — one `inventory` row."""

    size: str
    quantity: int
    in_stock: bool


class ProductInfo(BaseModel):
    """Everything the agent needs to answer a product / price / stock question.

    This is the return type of the `get_product_info` tool. Every field comes
    straight from the database (`catalogue` + `inventory`); the agent must answer
    only from these values and never invent a price, color, or stock number.
    """

    product_id: str
    name: str
    garment_type: str
    description: str
    price: float
    colors: list[str] = Field(default_factory=list)
    image_url: str
    total_in_stock: int           # sum of quantity across all sizes
    in_stock: bool                # true if any size has stock
    sizes: list[SizeStock] = Field(default_factory=list)


class StockCheck(BaseModel):
    """Answer to "is <product> available in <size>?" — the return type of the
    `check_size_stock` tool.

    `exists` distinguishes "we don't stock that size at all" from "that size is
    just sold out", so the agent can phrase the two cases differently instead of
    guessing.
    """

    product_id: str
    size: str
    exists: bool
    in_stock: bool
    quantity: int


class ChatMessage(BaseModel):
    """One prior turn, sent by the front end so the agent has context."""

    role: str  # "user" or "assistant"
    content: str


class PageContext(BaseModel):
    """What the shopper is looking at when they send a chat message.

    Sent by the website with every chat request so the agent can resolve "this",
    "it", or "these" ("do you have this in another color?"). Only ids and the
    shopper's own filter text are trusted from the browser; product names and
    details are looked up from the database on the server.
    """

    path: str = ""
    # On a product detail page: which product, and the size they've selected.
    viewing_product_id: str | None = None
    selected_size: str | None = None
    # On the compare page: the two products side by side (left, right).
    comparing_product_ids: list[str] = Field(default_factory=list, max_length=2)
    # On the Products page: what the grid is currently showing.
    list_label: str | None = None             # e.g. "Crewnecks" or "All products"
    list_total: int | None = None             # how many tiles are visible
    listed_product_ids: list[str] = Field(default_factory=list, max_length=60)
    search_text: str | None = None            # the page's own search box
    category: str | None = None               # the page's own category dropdown


class ChatRequest(BaseModel):
    """What the website POSTs to /api/chat."""

    message: str = Field(min_length=1, max_length=2000)
    # Running transcript from the browser. Used only for shoppers who are NOT
    # logged in; for a logged-in customer the server reads their history from
    # the chat_messages table instead, so the browser can't rewrite it.
    history: list[ChatMessage] = Field(default_factory=list)
    page_context: PageContext | None = None


class CustomerProfile(BaseModel):
    """The logged-in customer, as the agent sees them (put in the agent's deps).

    Deliberately excludes password_hash and anything about other users.
    """

    id: int
    first_name: str | None
    last_name: str | None
    name: str
    email: str


class HistoryMessage(BaseModel):
    """One stored chat turn, as returned to the website to repopulate the panel."""

    role: str
    content: str
    products: list[ProductCard] = Field(default_factory=list)
    created_at: str


class SearchFilters(BaseModel):
    """The criteria behind a page update, echoed back so the UI can label it."""

    query: str | None = None
    garment_type: str | None = None
    max_price: float | None = None
    color: str | None = None


class PageResults(BaseModel):
    """Products the website's Products page should switch to showing.

    Built by the backend from a real catalogue search (the
    `show_products_on_page` tool), never written by the model, so every tile on
    the page is a real product with real price and stock.
    """

    label: str                    # short heading, e.g. "Crewnecks"
    filters: SearchFilters
    total: int
    products: list[ProductCard] = Field(default_factory=list)


class AgentAnswer(BaseModel):
    """What the model itself produces: the chat text plus which products to show.

    The model only names products by id; the backend builds each card from the
    database. That keeps the model from having to copy names, prices, and image
    URLs (which it could get wrong, forcing a retry), and it means the model has
    no `page_results` field to fill in. That part comes only from the search tool.
    """

    reply: str
    product_ids: list[str] = Field(
        default_factory=list,
        description="product_id of each product to show as a card under the reply, in order (max 5).",
    )


# --------------------------------------------------------------------------
# Back-end sub-agents
# --------------------------------------------------------------------------


class RankedItem(BaseModel):
    """One product as ranked by the ranking agent."""

    product_id: str
    score: float = Field(ge=0, le=1, description="How well it fits the request, 0-1.")
    reason: str = Field(
        max_length=160,
        description="One short line, based only on the product data given, on why it fits.",
    )


class RankedSuggestions(BaseModel):
    """Output of the ranking agent: candidates ordered best-first."""

    ranked: list[RankedItem]


class ClarifyDecision(BaseModel):
    """Output of the clarifying agent."""

    needs_clarification: bool = Field(
        description="True only if one question would clearly improve the search."
    )
    question: str = Field(
        default="",
        max_length=200,
        description="The single question to ask the shopper (empty if not needed).",
    )
    options: list[str] = Field(
        default_factory=list,
        description="2-4 short quick-reply answers the shopper can tap; each must exist in the catalogue facts given.",
    )
    reason: str = Field(
        default="", max_length=200, description="Why this question (or why none is needed)."
    )


class ChatReply(BaseModel):
    """The /api/chat response contract.

    `reply` is the markdown the chat panel shows; `products` is any highlight
    cards for the chat bubble; `page_results` is present only when the shopper
    asked to browse a type/category, and tells the website to update the
    Products page to exactly these products. Absent means "leave the page alone".
    """

    reply: str
    products: list[ProductCard] = Field(default_factory=list)
    page_results: PageResults | None = None
    # Quick-reply buttons for a clarifying question (from the clarifying agent).
    suggested_replies: list[str] = Field(default_factory=list)
