"""Data types for the Campus Customs agent team.

Every agent returns one of these Pydantic models (its output_type), so a
hand-off between agents is always structured JSON, not an essay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = (
    "boss", "inventory", "accounting", "facilities", "customer_service",
)


# ---------- shared pieces ----------

class Fact(BaseModel):
    """One number or fact, with the table it came from."""
    label: str = Field(description="What this is, e.g. 'on_hand CC-HOOD-NAVY M'.")
    value: str = Field(description="The value exactly as the tool returned it.")
    source: str = Field(description="Table(s) or MCP tool it came from.")


class PaymentRequest(BaseModel):
    """A payment prepared for a human. Agents never release it themselves."""
    payee: str
    amount: float = Field(ge=0)
    reference_kind: Literal["invoice", "lease", "purchase_order"]
    reference_id: int | None = Field(default=None, description="invoice id or lease id")
    reason: str
    cash_before: float | None = None
    cash_after: float | None = Field(default=None, description="Must be >= 0 or the request is refused.")
    status: Literal["awaiting_human_approval", "refused"] = "awaiting_human_approval"
    refusal_reason: str | None = None


# ---------- one output type per agent ----------

class InventoryReport(BaseModel):
    sku: str | None = None
    name: str | None = None
    size: str | None = None
    on_hand: int | None = None
    qty_needed: int | None = None
    shortfall: int | None = None
    can_fill: bool | None = None
    restock_vendor_id: int | None = None
    restock_vendor_name: str | None = None
    lead_days: int | None = None
    vendor_on_hold: bool | None = None
    hold_reason: str | None = None
    earliest_restock_date: str | None = Field(
        default=None, description="desk.date_today + lead_days, only once any hold is cleared.")
    facts: list[Fact] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list, description="Anything not confirmed by a tool.")
    summary: str


class AccountingReport(BaseModel):
    cash_balance: float | None = None
    cash_as_of: str | None = None
    payment_requests: list[PaymentRequest] = Field(default_factory=list)
    cash_after_all_requests: float | None = None
    discount_requested_pct: float | None = None
    unit_cost: float | None = None
    list_price: float | None = None
    discounted_price: float | None = None
    margin_per_unit: float | None = None
    margin_pct: float | None = None
    max_safe_discount_pct: float | None = None
    facts: list[Fact] = Field(default_factory=list)
    recommendation: str
    unknowns: list[str] = Field(default_factory=list)


class FacilitiesReport(BaseModel):
    lease_id: int | None = None
    space_name: str | None = None
    landlord: str | None = None
    monthly_rent: float | None = None
    next_due: str | None = None
    days_until_due: int | None = None
    urgency: Literal["routine", "urgent", "overdue", "unknown"] = "unknown"
    notice_mismatch: str | None = Field(default=None, description="Any difference between the notice and the lease table.")
    facts: list[Fact] = Field(default_factory=list)
    summary: str
    unknowns: list[str] = Field(default_factory=list)


class CustomerDraft(BaseModel):
    ticket_id: int | None = None
    recipient: str
    subject: str
    body: str = Field(description="80-150 words. Draft only; never sent.")
    facts_used: list[Fact] = Field(default_factory=list)
    left_out: list[str] = Field(default_factory=list, description="Facts not confirmed, so not promised.")
    status: Literal["DRAFT: not sent, awaiting human review"] = "DRAFT: not sent, awaiting human review"


class Assignment(BaseModel):
    agent: AgentName
    task: str


class BossDecision(BaseModel):
    ticket_id: int
    ask_summary: str
    decision: Literal[
        "fulfil", "partial_fulfil", "wait_for_restock",
        "pay_pending_approval", "decline", "escalate_to_human",
    ]
    rationale: str
    assignments: list[Assignment] = Field(default_factory=list, description="Who the Boss handed work to.")
    key_facts: list[Fact] = Field(default_factory=list)
    payments_needing_approval: list[PaymentRequest] = Field(default_factory=list)
    customer_draft: CustomerDraft | None = None
    next_steps: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


OUTPUT_TYPES: dict[AgentName, type[BaseModel]] = {
    "boss": BossDecision,
    "inventory": InventoryReport,
    "accounting": AccountingReport,
    "facilities": FacilitiesReport,
    "customer_service": CustomerDraft,
}


# ---------- run-time dependencies shared by every agent in one run ----------

@dataclass
class RunBudget:
    """Shared across one ticket run so no chain of hand-offs can run away."""
    max_delegations: int = 12
    max_depth: int = 4
    delegations: int = 0
    requests: int = 0        # model calls across every agent in the run
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class TeamDeps:
    """Injected into every agent run (PydanticAI deps)."""
    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    ticket_id: int | None = None
    agent: AgentName = "boss"
    chain: list[AgentName] = field(default_factory=list)  # who called whom, top to bottom
    budget: RunBudget = field(default_factory=RunBudget)
