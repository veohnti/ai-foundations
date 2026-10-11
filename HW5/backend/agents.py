"""The Campus Customs agent team: boss, inventory, accounting, facilities, customer service.

All five are PydanticAI agents on gpt-5.6-luna through Portkey (PORTKEY_API_KEY
from the root .env). Every shop fact and every database change goes through the
campus-customs MCP server registered in HW5/.mcp.json; there is no other tools
layer. Each agent sees only its own allowlist of MCP tools.

Delegation:
- The boss delegates with ask_<specialist>_agent tools.
- Specialists can consult each other with consult_teammate, one level deep.
  Boss -> specialist -> peer is the longest chain, and nobody can call an agent
  already above them in the chain.
All runs for a ticket share one usage counter, so the ticket budget in
TICKET_USAGE_LIMITS covers the whole delegation tree.

Every agent run is appended to output/audit_trail.json by run_agent().
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Any

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv
from fastmcp import Client
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import RetryPromptPart, TextPart, ThinkingPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import RunUsage, UsageLimits

from models import AgentName, BossDecision, SpecialistName, SpecialistReport, TeamDeps

HW5 = Path(__file__).resolve().parent.parent
PROMPTS = Path(__file__).resolve().parent / "prompts"

# ---------------------------------------------------------------------------
# Model and budget: gpt-5.6-luna only
# ---------------------------------------------------------------------------

MODEL_NAME = "gpt-5.6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Per model response, and per ticket across the whole delegation tree.
MODEL_SETTINGS = ModelSettings(max_tokens=4000)
TICKET_USAGE_LIMITS = UsageLimits(request_limit=30, tool_calls_limit=40, total_tokens_limit=150_000)
MAX_DELEGATION_DEPTH = 2  # boss (0) -> specialist (1) -> peer (2); no deeper


@lru_cache(maxsize=1)
def get_model() -> OpenAIChatModel:
    load_dotenv(HW5 / ".env")         # HW5/.env (copy .env.example)
    load_dotenv(HW5.parent / ".env")  # or the course-root .env
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY not found. Copy .env.example to .env and add your key.")
    provider = OpenAIProvider(base_url=PORTKEY_BASE_URL, api_key=api_key)
    return OpenAIChatModel(MODEL_NAME, provider=provider)


# ---------------------------------------------------------------------------
# MCP: one connection to the campus-customs server, filtered per agent
# ---------------------------------------------------------------------------

AGENT_TOOLS: dict[AgentName, set[str]] = {
    "boss": {"list_open_tickets", "get_ticket_with_links", "list_approval_requests",
             "read_board", "update_ticket_status"},
    "inventory": {"get_ticket_with_links", "check_stock_and_price", "get_vendor_restock_options",
                  "post_draft_to_board"},
    "accounting": {"get_ticket_with_links", "get_cash_and_obligations", "check_margin",
                   "check_stock_and_price", "get_vendor_restock_options", "request_payment_approval",
                   "prepare_purchase_order", "list_approval_requests", "post_draft_to_board"},
    "facilities": {"get_ticket_with_links", "get_cash_and_obligations", "list_approval_requests",
                   "read_board", "post_draft_to_board"},
    "customer_service": {"get_ticket_with_links", "check_stock_and_price", "read_board",
                         "post_draft_to_board"},
}
# Never given to an agent: only the human (Approve button / approve.py) and reset call these.
# Agents can prepare payments and purchase orders, but only the human's approval moves money.
HUMAN_ONLY_TOOLS = {"record_human_approval", "reset_database_to_original"}
# Tools whose author_agent argument is filled in from the run, not by the model.
AUTHOR_TOOLS = {"request_payment_approval", "prepare_purchase_order", "post_draft_to_board",
                "update_ticket_status"}

assert not any(HUMAN_ONLY_TOOLS & tools for tools in AGENT_TOOLS.values())


async def _stamp_author(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict[str, Any]):
    """Write tools learn which agent is calling from the run itself, so an agent can't pose as another.

    Each call is also logged as it happens, so the board can show progress mid-run.
    """
    if name in AUTHOR_TOOLS:
        args = {**args, "author_agent": ctx.deps.agent_name}
    # A draft always belongs to the ticket being worked, even if the model leaves ticket_id out
    # (in the Problem 9 run, draft 9 was saved without one and the boss couldn't find it).
    if name == "post_draft_to_board" and args.get("ticket_id") is None and ctx.deps.ticket_id is not None:
        args = {**args, "ticket_id": ctx.deps.ticket_id}
    result = await call_tool(name, args)
    ctx.deps.audit.log("tool_called", agent=ctx.deps.agent_name, ticket_id=ctx.deps.ticket_id,
                       tool=name, args=args, result=result)
    return result


def _hide_author_param(ctx: RunContext[TeamDeps], tool_defs: list[ToolDefinition]) -> list[ToolDefinition]:
    out = []
    for td in tool_defs:
        schema = td.parameters_json_schema
        if "author_agent" in schema.get("properties", {}):
            schema = {**schema,
                      "properties": {k: v for k, v in schema["properties"].items() if k != "author_agent"},
                      "required": [r for r in schema.get("required", []) if r != "author_agent"]}
            td = replace(td, parameters_json_schema=schema)
        out.append(td)
    return out


def load_mcp_config() -> dict:
    """Read HW5/.mcp.json. Its paths are relative to HW5/ (so it works on any machine);
    resolve them here, and launch the server with this same Python so it has the same packages."""
    config = json.loads((HW5 / ".mcp.json").read_text())
    for server in config["mcpServers"].values():
        server["command"] = sys.executable
        server["args"] = [str(HW5 / a) if a.endswith(".py") and not Path(a).is_absolute() else a
                          for a in server.get("args", [])]
    return config


def make_shop_mcp() -> MCPToolset:
    config = load_mcp_config()
    return MCPToolset(Client(config), id="campus-customs", process_tool_call=_stamp_author, max_retries=1)


shop_mcp = make_shop_mcp()


def tools_for(agent_name: AgentName):
    allowed = AGENT_TOOLS[agent_name]
    return shop_mcp.filtered(lambda ctx, td: td.name in allowed).prepared(_hide_author_param)


# ---------------------------------------------------------------------------
# The five agents
# ---------------------------------------------------------------------------

def _agent(name: AgentName, output_type) -> Agent[TeamDeps, Any]:
    return Agent(
        None,  # model is supplied per run by run_agent(): always gpt-5.6-luna
        name=f"{name}_agent",
        deps_type=TeamDeps,
        output_type=output_type,
        instructions=(PROMPTS / f"{name}.md").read_text(),
        toolsets=[tools_for(name)],
        model_settings=MODEL_SETTINGS,
        retries=1,
    )


boss_agent = _agent("boss", BossDecision)
inventory_agent = _agent("inventory", SpecialistReport)
accounting_agent = _agent("accounting", SpecialistReport)
facilities_agent = _agent("facilities", SpecialistReport)
customer_service_agent = _agent("customer_service", SpecialistReport)

TEAM: dict[AgentName, Agent[TeamDeps, Any]] = {
    "boss": boss_agent,
    "inventory": inventory_agent,
    "accounting": accounting_agent,
    "facilities": facilities_agent,
    "customer_service": customer_service_agent,
}


# ---------------------------------------------------------------------------
# Agent loop + audit
# ---------------------------------------------------------------------------

def _tool_activity(messages) -> list[dict]:
    calls, results = [], {}
    for msg in messages:
        for part in msg.parts:
            if isinstance(part, ToolCallPart) and not part.tool_name.startswith("final_result"):
                calls.append({"call_id": part.tool_call_id, "tool": part.tool_name,
                              "args": part.args_as_dict()})
            elif isinstance(part, ToolReturnPart):
                results[part.tool_call_id] = part.content
            elif isinstance(part, RetryPromptPart) and part.tool_name:
                results[part.tool_call_id] = {"retry_prompt": part.content}
    for c in calls:
        c["result"] = results.get(c["call_id"])
    return calls


def _log_step(deps: TeamDeps, name: AgentName, response) -> None:
    """Log one model response as it happens: any reasoning/text, and the tools it chose to call."""
    thoughts = [p.content for p in response.parts
                if isinstance(p, (ThinkingPart, TextPart)) and p.content and p.content.strip()]
    requests = [{"tool": p.tool_name, "args": p.args_as_dict()} for p in response.parts
                if isinstance(p, ToolCallPart)]
    deps.audit.log("agent_step", agent=name, ticket_id=deps.ticket_id, thoughts=thoughts,
                   tool_requests=requests)


async def run_agent(name: AgentName, task: str, deps: TeamDeps, usage: RunUsage | None = None):
    """Run one agent on one task and append the run to the audit trail.

    Returns the typed output. Budget overruns propagate so the whole ticket stops.
    """
    deps.audit.log("agent_started", agent=name, ticket_id=deps.ticket_id, chain=deps.chain, task=task)
    try:
        async with TEAM[name].iter(task, deps=deps, model=get_model(), usage=usage,
                                   usage_limits=TICKET_USAGE_LIMITS) as agent_run:
            async for node in agent_run:
                if Agent.is_call_tools_node(node):
                    _log_step(deps, name, node.model_response)
        result = agent_run.result
    except UsageLimitExceeded as e:
        deps.audit.log("agent_stopped_budget", agent=name, ticket_id=deps.ticket_id, error=str(e))
        raise
    except UnexpectedModelBehavior as e:
        deps.audit.log("agent_failed", agent=name, ticket_id=deps.ticket_id, error=str(e))
        raise
    u = result.usage
    deps.audit.log("agent_finished", agent=name, ticket_id=deps.ticket_id, chain=deps.chain,
                   model=MODEL_NAME, tool_calls=_tool_activity(result.all_messages()),
                   output=result.output.model_dump(),
                   ticket_usage_so_far={"requests": u.requests, "input_tokens": u.input_tokens,
                                        "output_tokens": u.output_tokens})
    return result.output


async def _delegate(ctx: RunContext[TeamDeps], target: AgentName, task: str) -> str:
    if target == ctx.deps.agent_name or target in ctx.deps.chain:
        return f"Refused: {target} is already working on this request higher up the chain."
    if ctx.deps.depth >= MAX_DELEGATION_DEPTH:
        return "Refused: delegation depth limit reached. Answer with what you have."
    try:
        report = await run_agent(target, task, ctx.deps.child(target), usage=ctx.usage)
    except UnexpectedModelBehavior as e:
        return f"{target} agent failed: {e}"
    return report.model_dump_json()


# Boss -> specialists

@boss_agent.tool
async def ask_inventory_agent(ctx: RunContext[TeamDeps], task: str) -> str:
    """Delegate a stock / shortfall / restock-vendor question to the inventory agent."""
    return await _delegate(ctx, "inventory", task)


@boss_agent.tool
async def ask_accounting_agent(ctx: RunContext[TeamDeps], task: str) -> str:
    """Delegate cash, invoice, margin, payment-request, purchase-order, or approved-payment work to accounting."""
    return await _delegate(ctx, "accounting", task)


@boss_agent.tool
async def ask_facilities_agent(ctx: RunContext[TeamDeps], task: str) -> str:
    """Delegate lease, rent-notice, or shop-space work to the facilities agent."""
    return await _delegate(ctx, "facilities", task)


@boss_agent.tool
async def ask_customer_service_agent(ctx: RunContext[TeamDeps], task: str) -> str:
    """Have customer service draft a customer message on the board (never sent). Include the decided price/outcome."""
    return await _delegate(ctx, "customer_service", task)


# Specialist <-> specialist

async def consult_teammate(ctx: RunContext[TeamDeps], teammate: SpecialistName, question: str) -> str:
    """Ask another specialist (inventory, accounting, facilities, customer_service) a specific question."""
    return await _delegate(ctx, teammate, question)


for _specialist in (inventory_agent, accounting_agent, facilities_agent, customer_service_agent):
    _specialist.tool(consult_teammate)
