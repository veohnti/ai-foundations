"""Data types shared by the Campus Customs agent team.

Agent outputs are typed so every run can be checked and written to the
audit trail in the same shape. `TeamDeps` is what each agent run carries:
who it is, which ticket it is on, how deep in the delegation chain it is,
and where to log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
SpecialistName = Literal["inventory", "accounting", "facilities", "customer_service"]
TicketStatus = Literal["open", "in_progress", "waiting_on_approval", "waiting_on_vendor", "resolved"]


class Fact(BaseModel):
    """One fact the agent relied on, tied to the MCP tool that returned it."""

    source_tool: str = Field(description="MCP tool name that returned this fact")
    detail: str = Field(description="The fact, with the exact numbers/dates/ids from the tool output")


class SpecialistReport(BaseModel):
    """What inventory, accounting, facilities, and customer service hand back."""

    agent: SpecialistName
    ticket_id: int | None = None
    summary: str = Field(description="2-4 sentences answering the task you were given")
    facts: list[Fact] = Field(default_factory=list)
    actions_taken: list[str] = Field(
        default_factory=list, description="Write tools you called and their result (incl. refusals)")
    approval_ids: list[int] = Field(
        default_factory=list, description="Approval request ids created or acted on")
    board_draft_ids: list[int] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    recommendation: str = Field(description="What you recommend the boss decide")


class BossDecision(BaseModel):
    """The boss's final call on one ticket."""

    ticket_id: int
    ticket_type: str
    delegated_to: list[SpecialistName] = Field(default_factory=list)
    facts_relied_on: list[Fact] = Field(default_factory=list)
    final_decision: str = Field(description="The decision, in plain words, with amounts and dates")
    new_status: TicketStatus
    pending_human_approvals: list[int] = Field(
        default_factory=list, description="Approval ids waiting on the human")
    board_draft_ids: list[int] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


@dataclass
class TeamDeps:
    """Per-run context. A child copy is made for every delegation."""

    agent_name: AgentName
    run_id: str
    ticket_id: int | None
    audit: "AuditTrail"  # noqa: F821 - defined in audit.py
    chain: list[str] = field(default_factory=list)  # agents above this one, boss first

    @property
    def depth(self) -> int:
        return len(self.chain)

    def child(self, agent_name: AgentName) -> "TeamDeps":
        return TeamDeps(agent_name=agent_name, run_id=self.run_id, ticket_id=self.ticket_id,
                        audit=self.audit, chain=[*self.chain, self.agent_name])


# ---------------------------------------------------------------------------
# API bodies (backend/main.py)
# ---------------------------------------------------------------------------

class ApprovalDecisionIn(BaseModel):
    """Body for the Approve / Deny buttons. approver defaults to the shop's human approver."""

    approver: str | None = None
    note: str = ""
