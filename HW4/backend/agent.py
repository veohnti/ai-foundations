"""Campus Customs chat agent — wiring and entry point.

Builds a PydanticAI agent that answers shopper questions using the catalogue and
inventory tools in tools.py, and returns a structured ChatReply (markdown text
plus any product cards). The model is gpt-5.6-terra, reached through Portkey's
OpenAI-compatible gateway with PORTKEY_API_KEY from the root .env.

main.py imports `run_chat` and calls it per request; the `__main__` block lets
you smoke-test the agent straight from the command line without the web server.
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext, capture_run_messages
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits

from models import (
    AgentAnswer,
    ClarifyDecision,
    RankedItem,
    RankedSuggestions,
    ChatMessage,
    ChatReply,
    CustomerProfile,
    PageContext,
    PageResults,
    SearchFilters,
)
from tools import (
    now,
    record_run,
    redact_sensitive,
    cards_for_ids,
    catalogue_facets,
    ranking_candidates,
    load_chat_history,
    save_chat_turn,
    check_size_stock as tool_check_size_stock,
    get_product_info as tool_get_product_info,
    search_catalogue,
)

ROOT = Path(__file__).resolve().parent
PROMPT_PATH = ROOT / "prompts" / "prompt.md"


def load_prompts() -> dict[str, str]:
    """Split prompts/prompt.md into the three agents' instructions.

    The shop assistant gets everything before the first "<!-- prompt: ... -->"
    marker; the ranking and clarifying agents get only their own sections.
    """
    text = PROMPT_PATH.read_text()
    parts = re.split(r"<!--\s*prompt:\s*(\w+)\s*-->", text)
    prompts = {"shop_assistant": parts[0].split("<!-- ====")[0].strip()}
    for name, body in zip(parts[1::2], parts[2::2]):
        prompts[name] = body.strip()
    return prompts

# A shopping turn is: maybe call a tool or two (some of which consult a
# sub-agent), then answer. Sub-agent calls share this budget (their usage is
# passed through), so the cap covers the whole turn. It stops a misbehaving run
# fast instead of looping on the library default of 50 requests.
LOOP_LIMITS = UsageLimits(request_limit=10)


# --------------------------------------------------------------------------
# Model: gpt-5.6-terra through Portkey, shared by all three agents
# --------------------------------------------------------------------------

MODEL = "gpt-5.6-terra"
BASE_URL_DEFAULT = "https://api.portkey.ai/v1"


@lru_cache(maxsize=1)
def make_model() -> OpenAIChatModel:
    # HW4/.env first (copy .env.example there), then the folder above HW4.
    load_dotenv(ROOT.parent / ".env")
    load_dotenv(ROOT.parent.parent / ".env")
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        sys.exit("PORTKEY_API_KEY not found. Add it to the root .env file.")
    provider = OpenAIProvider(
        base_url=os.getenv("PORTKEY_BASE_URL", BASE_URL_DEFAULT), api_key=api_key
    )
    return OpenAIChatModel(MODEL, provider=provider)


# --------------------------------------------------------------------------
# Back-end sub-agents: ranking and clarifying
# --------------------------------------------------------------------------
# Two small PydanticAI agents the shop assistant consults through tools
# (rank_suggestions, ask_clarifying_question). Each has its own section of
# prompts/prompt.md and a typed output, and their output is checked in code so
# a model mistake can't put a made-up product or a dead-end option in front of
# a shopper.



@lru_cache(maxsize=1)
def ranker_agent() -> Agent[None, RankedSuggestions]:
    return Agent(
        make_model(),
        output_type=RankedSuggestions,
        instructions=load_prompts()["ranker"],
    )


@lru_cache(maxsize=1)
def clarifier_agent() -> Agent[None, ClarifyDecision]:
    return Agent(
        make_model(),
        output_type=ClarifyDecision,
        instructions=load_prompts()["clarifier"],
    )


async def rank_products(
    request: str,
    candidates: list[dict],
    usage: RunUsage | None = None,
    turn_id: str = "",
    user: str = "guest",
) -> list[RankedItem]:
    """Rank candidates for a request. Only ids from `candidates` survive."""
    if not candidates:
        return []
    prompt = (
        f"Shopper request: {request}\n\n"
        f"Candidate products ({len(candidates)}), from the shop database:\n"
        f"{json.dumps(candidates, indent=1)}"
    )
    started = now()
    result = await ranker_agent().run(prompt, usage=usage)

    allowed = {c["product_id"] for c in candidates}
    seen: set[str] = set()
    ranked = []
    for item in sorted(result.output.ranked, key=lambda r: -r.score):
        if item.product_id in allowed and item.product_id not in seen:
            seen.add(item.product_id)
            ranked.append(item)
    record_run(
        turn_id=turn_id, agent="ranking_agent", started=started, user=user,
        messages=result.new_messages(), requests=1, stop_reason="final_answer",
        summary="; ".join(f"{r.product_id} ({r.score:.2f})" for r in ranked[:5]),
        extra={"candidates": len(candidates), "dropped_unknown_ids": len(result.output.ranked) - len(ranked)},
    )
    return ranked


async def decide_clarification(
    message: str,
    recent_turns: list[str],
    facets: dict,
    usage: RunUsage | None = None,
    turn_id: str = "",
    user: str = "guest",
) -> ClarifyDecision:
    """Ask the clarifying agent whether to ask a question, then sanity-check it."""
    prompt = (
        f"Shopper's latest message: {message}\n\n"
        "Recent conversation (oldest first):\n"
        + ("\n".join(recent_turns[-6:]) or "(none)")
        + f"\n\nCatalogue facts for what currently matches:\n{json.dumps(facets, indent=1)}"
    )
    started = now()
    run = await clarifier_agent().run(prompt, usage=usage)
    decision = run.output

    def log(final: ClarifyDecision) -> ClarifyDecision:
        record_run(
            turn_id=turn_id, agent="clarifying_agent", started=started, user=user,
            messages=run.new_messages(), requests=1,
            stop_reason="ask" if final.needs_clarification else "no_question",
            summary=final.question or final.reason,
            extra={"options": final.options, "matching_products": facets.get("matching_products")},
        )
        return final

    # Enforce the contract in code too: short, distinct options, at most 4, and
    # no question at all if it came back without at least two choices.
    options: list[str] = []
    for opt in decision.options:
        opt = opt.strip()
        if opt and len(opt) <= 40 and opt.lower() not in {o.lower() for o in options}:
            options.append(opt)
    options = options[:4]
    if decision.needs_clarification and (not decision.question.strip() or len(options) < 2):
        return log(ClarifyDecision(
            needs_clarification=False,
            reason="Clarifier didn't produce a usable question; proceeding without one.",
        ))
    decision.options = options if decision.needs_clarification else []
    return log(decision)


# How much stored history goes into each request for a logged-in customer
# (user + assistant messages). Older turns stay reachable via a tool.
HISTORY_WINDOW = 20


@dataclass
class ChatDeps:
    """Per-request state shared with the agent's instructions and tools.

    - `customer`: the logged-in customer (name + email), or None for a guest.
      Comes from the session cookie on the server, never from the browser body.
    - `page`: what the shopper is looking at (product page or product grid).
    - `page_results`: set by show_products_on_page and returned to the website
      as-is; the model never writes it.
    """

    customer: CustomerProfile | None = None
    page: PageContext | None = None
    page_results: PageResults | None = None
    # Audit trail: links this turn's entries (main agent + sub-agents).
    turn_id: str = ""
    audit_user: str = "guest"
    # Recent conversation lines, for the clarifying agent's judgement.
    recent_turns: list[str] = field(default_factory=list)
    # Set by the sub-agent tools; attached to the reply in run_chat().
    rank_reasons: dict[str, str] = field(default_factory=dict)
    suggested_replies: list[str] = field(default_factory=list)
    clarifying_question: str | None = None


def describe_customer(customer: CustomerProfile | None) -> str:
    if customer is None:
        return (
            "## Who you're talking to\n"
            "A guest who is not logged in. You don't know their name; don't ask for "
            "it or for an email. This conversation is not saved."
        )
    first = customer.first_name or customer.name.split()[0]
    return (
        "## Who you're talking to\n"
        f"A logged-in customer. First name: {first}. Full name: {customer.name}. "
        f"Email: {customer.email}.\n"
        f"Address them as {first} when it feels natural (\"Here you go, {first}\"). "
        "Mention their email only if they ask what account they're signed in with. "
        "This conversation is saved to their account, and earlier turns from past "
        "visits appear in the conversation history."
    )


def describe_page(page: PageContext | None) -> str:
    """Turn the browser's page context into text for the agent.

    Product names, colors, and stock are looked up here from the database by
    id. The only browser-supplied text that reaches the agent is the shopper's
    own search-box text and the list label, both marked as data.
    """
    header = "## What the shopper is looking at right now\n"
    if page is None:
        return header + "Unknown."

    if page.comparing_product_ids:
        lines = []
        for side, pid in zip(("Left", "Right"), page.comparing_product_ids):
            info = tool_get_product_info(pid)
            if info is None:
                continue
            in_stock = [s.size for s in info.sizes if s.in_stock]
            lines.append(
                f"- {side}: **{info.name}** (product_id: {info.product_id}), a {info.garment_type} "
                f"at ${info.price:.2f}. Colors: {', '.join(info.colors)}. "
                f"Sizes in stock: {', '.join(in_stock) or 'none'}."
            )
        if lines:
            return header + "The compare page, with two products side by side:\n" + "\n".join(lines) + (
                "\nWhen they say \"these\", \"both\", \"the left one\", or \"which is better\", "
                "they mean these two."
            )

    if page.viewing_product_id:
        info = tool_get_product_info(page.viewing_product_id)
        if info is None:
            return header + f"A product page for an id the catalogue doesn't have ({page.viewing_product_id!r})."
        in_stock = [s.size for s in info.sizes if s.in_stock]
        line = (
            f"The product page for **{info.name}** (product_id: {info.product_id}), "
            f"a {info.garment_type} at ${info.price:.2f}. Colors: {', '.join(info.colors)}. "
            f"Sizes in stock: {', '.join(in_stock) or 'none'}."
        )
        if page.selected_size:
            line += f" They have size {page.selected_size} selected."
        return header + line + (
            "\nWhen they say \"this\", \"it\", or \"this one\", they mean this product."
        )

    if page.list_total is not None:
        parts = [f"The Products page, showing {page.list_total} product tiles"]
        if page.list_label:
            parts.append(f'under the heading "{page.list_label}"')
        line = " ".join(parts) + "."
        if page.search_text:
            line += f' Their search box contains: "{page.search_text}".'
        if page.category and page.category != "all":
            line += f' Category filter: "{page.category}".'
        cards = cards_for_ids(page.listed_product_ids)
        if cards:
            names = "; ".join(f"{c.name} ({c.product_id})" for c in cards)
            line += f"\nThe tiles on screen, in order: {names}."
            line += "\nWhen they say \"these\", \"any of them\", or \"the first one\", they mean these tiles."
        elif page.list_total > len(cards):
            line += " (Too many tiles to list; it's the broad catalogue view.)"
        return header + line

    return header + f"A page with no products on it ({page.path or 'unknown path'})."


@lru_cache(maxsize=1)
def build_agent() -> Agent[ChatDeps, AgentAnswer]:
    """Construct the agent once and reuse it across requests.

    Cached because building the model/provider and reading the prompt on every
    chat message would be wasteful; the agent itself is stateless per run.
    """
    agent: Agent[ChatDeps, AgentAnswer] = Agent(
        make_model(),
        deps_type=ChatDeps,
        output_type=AgentAnswer,
        instructions=load_prompts()["shop_assistant"],
    )

    @agent.instructions
    def customer_and_page(ctx: RunContext[ChatDeps]) -> str:
        """Per-request context: who the customer is and what's on their screen."""
        return describe_customer(ctx.deps.customer) + "\n\n" + describe_page(ctx.deps.page)

    @agent.tool
    async def rank_suggestions(
        ctx: RunContext[ChatDeps],
        request: str,
        query: str | None = None,
        garment_type: str | None = None,
        max_price: float | None = None,
        color: str | None = None,
        top_n: int = 3,
    ) -> dict:
        """Get the best-fitting products for a recommendation request, ranked by the ranking agent.

        Use this when the shopper wants a recommendation rather than a list:
        "what's the best hoodie for winter?", "a gift for my dad under $70",
        "which crewneck should I get for game day?". Pass the shopper's need in
        `request` (in their words, including occasion, size, or recipient) and
        any hard filters you know. The backend pulls matching in-stock products
        from the database and a separate ranking agent orders them with a reason
        for each. Put the top results' ids in your `product_ids`, in this order.

        Put needs like "warm", "gift", "for my dad", or "game day" in `request`,
        NOT in `query`: `query` only matches words literally in the product data
        (a team, college, or design such as "Saybrook", "tennis", "bulldog").

        Args:
            request: What the shopper is looking for, in their words.
            query: Optional literal text filter (team, college, design).
            garment_type: Optional category, e.g. "hoodie", "crewneck", "jacket".
            max_price: Optional budget ceiling in USD.
            color: Optional color filter.
            top_n: How many recommendations to return (1-5).
        """
        candidates = ranking_candidates(query, garment_type, max_price, color)
        note = None
        if not candidates and query:
            # The text filter matched nothing (often a need like "warm" passed
            # as text); rank across the other filters instead of giving up.
            candidates = ranking_candidates(None, garment_type, max_price, color)
            note = f"No product text mentions {query!r}; ranked across the other filters instead."
        if not candidates:
            return {"ranked": [], "note": "No in-stock products match those filters."}
        ranked = await rank_products(
            request, candidates, usage=ctx.usage, turn_id=ctx.deps.turn_id, user=ctx.deps.audit_user
        )
        top = ranked[: max(1, min(top_n, 5))]
        by_id = {c["product_id"]: c for c in candidates}
        for item in top:
            ctx.deps.rank_reasons[item.product_id] = item.reason
        return {
            "note": note,
            "candidates_considered": len(candidates),
            "ranked": [
                {
                    "rank": i + 1,
                    "product_id": item.product_id,
                    "name": by_id[item.product_id]["name"],
                    "price": by_id[item.product_id]["price"],
                    "sizes_in_stock": by_id[item.product_id]["sizes_in_stock"],
                    "reason": item.reason,
                }
                for i, item in enumerate(top)
            ],
        }

    @agent.tool
    async def ask_clarifying_question(
        ctx: RunContext[ChatDeps],
        query: str | None = None,
        garment_type: str | None = None,
        max_price: float | None = None,
        color: str | None = None,
    ) -> dict:
        """Check whether one clarifying question would help, using the clarifying agent.

        Call this BEFORE searching when the request is broad or missing a key
        detail ("I need a gift", "something warm", "what should I get?"). Pass any
        filters the shopper already gave. A separate agent looks at what the
        catalogue has for those filters and decides. If `needs_clarification` is
        true, your reply should ask exactly the returned `question` (you may
        not list products yet. The website shows that question with the `options`
        as tappable buttons. If false, go ahead and search.

        Pass only concrete filters. Words like "gift", "warm", or "nice" are the
        need being clarified, not a text filter, so leave `query` empty for them.

        Args:
            query: Optional literal text filter (team, college, design) already given.
            garment_type: Optional category the shopper already gave.
            max_price: Optional budget the shopper already gave.
            color: Optional color the shopper already gave.
        """
        facets = catalogue_facets(query, garment_type, max_price, color)
        if facets["matching_products"] == 0 and query:
            # Same fallback as rank_suggestions: a need word passed as text
            # matches nothing, so describe the catalogue without it.
            facets = catalogue_facets(None, garment_type, max_price, color)
        message = ctx.deps.recent_turns[-1] if ctx.deps.recent_turns else ""
        decision = await decide_clarification(
            message, ctx.deps.recent_turns[:-1], facets, usage=ctx.usage,
            turn_id=ctx.deps.turn_id, user=ctx.deps.audit_user,
        )
        if decision.needs_clarification:
            ctx.deps.suggested_replies = decision.options
            ctx.deps.clarifying_question = decision.question
        return decision.model_dump()

    @agent.tool
    def get_past_conversations(ctx: RunContext[ChatDeps], limit: int = 60) -> dict:
        """Read further back in this customer's saved chat history.

        The most recent turns are already in the conversation. Use this only when
        the customer refers to something older ("the hoodie you showed me last
        week") that isn't there. Only works for a logged-in customer, and only
        ever returns that customer's own messages.

        Args:
            limit: How many messages to read, newest first, up to 200.
        """
        if ctx.deps.customer is None:
            return {"logged_in": False, "messages": []}
        history = load_chat_history(ctx.deps.customer.id, limit=max(1, min(limit, 200)))
        return {
            "logged_in": True,
            "messages": [
                {
                    "role": m.role,
                    "when": m.created_at,
                    "content": m.content,
                    "products_shown": [f"{p.name} ({p.product_id})" for p in m.products],
                }
                for m in history
            ],
        }

    @agent.tool_plain
    def find_products(
        query: str | None = None,
        garment_type: str | None = None,
        max_price: float | None = None,
        color: str | None = None,
    ) -> list[dict]:
        """Search the shop catalogue for products matching the shopper's request.

        Args:
            query: Free text to match against name, description, tags, and colors
                (e.g. "Saybrook", "game day", "navy crewneck").
            garment_type: Loose category filter, e.g. "hoodie", "crewneck",
                "t-shirt", "quarter-zip", "jacket".
            max_price: Only return products at or below this price in USD.
            color: Only return products available in this color.

        Returns product cards (id, name, type, price, image, colors, in-stock
        sizes). Put the ids of the ones you recommend in your `product_ids`.
        """
        return [c.model_dump() for c in search_catalogue(query, garment_type, max_price, color)]

    @agent.tool
    def show_products_on_page(
        ctx: RunContext[ChatDeps],
        label: str,
        query: str | None = None,
        garment_type: str | None = None,
        max_price: float | None = None,
        color: str | None = None,
    ) -> dict:
        """Update the website's Products page to show every product matching a browse request.

        Call this when the shopper wants to browse a type or category of product
        ("what crewnecks do you have?", "show me hoodies", "anything navy under
        $60?"). The backend runs the search against the database and the page
        switches to exactly those products as tiles. Don't call it for a question
        about one specific product.

        Args:
            label: Short heading for the page, e.g. "Crewnecks" or "Navy under $60".
            query: Free text to match (team, college, style), e.g. "Saybrook".
            garment_type: Category, e.g. "crewneck", "hoodie", "t-shirt",
                "quarter-zip", "jacket". Plurals are fine.
            max_price: Only products at or below this price in USD.
            color: Only products available in this color.

        Returns how many products are now on the page and their names/prices,
        so you can summarize them in chat. If total is 0 the page was NOT
        changed; tell the shopper nothing matched.
        """
        cards = search_catalogue(query, garment_type, max_price, color, limit=None)
        if cards:
            ctx.deps.page_results = PageResults(
                label=label,
                filters=SearchFilters(
                    query=query, garment_type=garment_type, max_price=max_price, color=color
                ),
                total=len(cards),
                products=cards,
            )
        return {
            "page_updated": bool(cards),
            "total": len(cards),
            "products": [
                {"product_id": c.product_id, "name": c.name, "price": c.price,
                 "colors": c.colors, "available_sizes": c.available_sizes}
                for c in cards
            ],
        }

    @agent.tool_plain
    def get_product_info(product_id: str) -> dict | None:
        """Look up a product's description, price, colors, and stock from the database.

        Use this for any question about what a product is, what it costs, or how
        many are in stock. Returns description, price, colors, a total stock count,
        and stock per size. Returns null if there is no product with that id — in
        which case say you can't find it rather than guessing.

        Args:
            product_id: The catalogue id, e.g. "basic-hoodie-big-yale".
        """
        info = tool_get_product_info(product_id)
        return info.model_dump() if info else None

    @agent.tool_plain
    def check_size_stock(product_id: str, size: str) -> dict:
        """Check stock for one product in one specific size, straight from the database.

        Use this when the shopper asks about a particular size. `exists` is false
        when the shop doesn't carry that size at all (different from sold out).

        Args:
            product_id: The catalogue id.
            size: One of XS, S, M, L, XL, XXL.
        """
        return tool_check_size_stock(product_id, size).model_dump()

    return agent


def _history_text(history: list[ChatMessage]) -> str:
    """Fold prior turns into the prompt so follow-ups keep their context.

    Kept simple for now (a transcript prepended to the new message). A later
    problem can switch this to PydanticAI's native message history.
    """
    if not history:
        return ""
    lines = [f"{m.role}: {m.content}" for m in history[-HISTORY_WINDOW:]]
    return "Conversation so far:\n" + "\n".join(lines) + "\n\n"


def _stored_history(customer: CustomerProfile) -> list[ChatMessage]:
    """The logged-in customer's recent turns from the database, as ChatMessages.

    Assistant turns note which products were shown, so "the second one" can be
    resolved against a reply from an earlier visit.
    """
    messages = []
    for m in load_chat_history(customer.id, limit=HISTORY_WINDOW):
        content = m.content
        if m.role == "assistant" and m.products:
            shown = ", ".join(f"{p.name} ({p.product_id})" for p in m.products)
            content += f"\n[product cards shown: {shown}]"
        messages.append(ChatMessage(role=m.role, content=content))
    return messages


async def run_chat(
    message: str,
    history: list[ChatMessage] | None = None,
    customer: CustomerProfile | None = None,
    page: PageContext | None = None,
) -> ChatReply:
    """Run one shopper message through the agent and return a ChatReply.

    The chat text and the choice of highlight cards come from the model, but each
    card's contents are re-read from the database. `page_results` comes only from
    the show_products_on_page tool (via deps), so it is either a real search
    result or absent.
    """
    agent = build_agent()
    deps = ChatDeps(customer=customer, page=page)
    # Logged in: the saved history in the database is the record, so the
    # browser's copy is ignored. Guest: use the browser's running transcript.
    turns = _stored_history(customer) if customer else list(history or [])
    # Defensive: if a client also put the new message at the end of its
    # history, drop it. Seeing the question twice made the agent repeat its
    # lookup in a loop until it hit the request cap.
    if turns and turns[-1].role == "user" and turns[-1].content.strip() == message.strip():
        turns = turns[:-1]
    deps.recent_turns = [f"{m.role}: {m.content}" for m in turns[-6:]] + [f"user: {message}"]
    prompt = _history_text(turns) + f"Shopper: {message}"
    # Occasionally a turn spirals (the model gateway returns something odd and
    # the agent loops on retries until it hits the request cap). The same
    # question succeeds on a fresh attempt, so retry once, logging the failed
    # turn's tool calls so a repeat can be diagnosed.
    turn_id = uuid.uuid4().hex[:12]
    audit_user = f"user:{customer.id}" if customer else "guest"
    audit_extra = {
        "message": redact_sensitive(message)[:200],
        "page": page.path if page else None,
    }
    result = None
    for attempt in (1, 2):
        attempt_deps = ChatDeps(
            customer=customer, page=page, recent_turns=deps.recent_turns,
            turn_id=turn_id, audit_user=audit_user,
        )
        started = now()
        with capture_run_messages() as messages:
            try:
                result = await agent.run(prompt, deps=attempt_deps, usage_limits=LOOP_LIMITS)
                deps = attempt_deps
                break
            except (UsageLimitExceeded, UnexpectedModelBehavior) as exc:
                calls = [
                    p.tool_name
                    for m in messages
                    if isinstance(m, ModelResponse)
                    for p in m.parts
                    if isinstance(p, ToolCallPart)
                ]
                print(f"[chat] attempt {attempt} failed ({type(exc).__name__}): tool calls {calls}")
                record_run(
                    turn_id=turn_id, agent="shop_assistant", started=started, user=audit_user,
                    messages=list(messages), requests=None,
                    stop_reason="usage_limit_exceeded" if isinstance(exc, UsageLimitExceeded) else "model_error",
                    summary=str(exc), extra={**audit_extra, "attempt": attempt},
                )
                if attempt == 2:
                    raise
    # One line per turn so slow or runaway turns are visible in the server log.
    print(f"[chat] model requests this turn: {result.usage.requests} (cap {LOOP_LIMITS.request_limit})")
    # The model picks which products to highlight; the database supplies what
    # they say. Rebuilding by id drops any card whose id isn't a real product.
    reply_text = result.output.reply
    product_ids = result.output.product_ids[:5]
    if deps.clarifying_question:
        # The clarifying agent's question is the reply, word for word, so the
        # question and its tappable options always come from the same source.
        reply_text = deps.clarifying_question
        product_ids = []
    highlights = cards_for_ids(product_ids)
    # A recommended card carries the ranking agent's reason; the model's own
    # wording for `reason` (if any) is discarded with the rest of its card.
    for card in highlights:
        card.reason = deps.rank_reasons.get(card.product_id)
    record_run(
        turn_id=turn_id, agent="shop_assistant", started=started, user=audit_user,
        messages=result.all_messages(), requests=result.usage.requests,
        stop_reason="clarifying_question" if deps.clarifying_question else "final_answer",
        summary=reply_text,
        extra={
            **audit_extra,
            "attempt": attempt,
            "cards": [c.product_id for c in highlights],
            "page_update": deps.page_results.total if deps.page_results else None,
        },
    )
    if customer is not None:
        # Remember this exchange. Guests' chats are never written anywhere, and
        # card numbers / SSNs / passwords a shopper types are redacted first.
        save_chat_turn(customer.id, redact_sensitive(message), reply_text, highlights)
    return ChatReply(
        reply=reply_text,
        products=highlights,
        page_results=deps.page_results,
        suggested_replies=deps.suggested_replies,
    )


if __name__ == "__main__":
    import asyncio

    msg = " ".join(sys.argv[1:]) or "What hoodies do you have under $70?"
    reply = asyncio.run(run_chat(msg))
    print("REPLY:\n", reply.reply)
    if reply.products:
        print("\nPRODUCT CARDS:")
        for p in reply.products:
            print(f"  - {p.name} (${p.price}) {p.available_sizes}")
    if reply.page_results:
        pr = reply.page_results
        print(f"\nPAGE UPDATE: {pr.label!r} -> {pr.total} products")
