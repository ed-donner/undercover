"""The UnderCover backend's request and response shapes."""

from typing import Literal

from pydantic import BaseModel

Decision = Literal["approve", "decline", "refer"]
Status = Literal["waiting", "in_progress", "waiting_for_sign_off", "decided"]


class ClaimItem(BaseModel):
    description: str
    category: str
    amount: float


class ClaimDocument(BaseModel):
    name: str
    type: str
    content: str


class PlanLimits(BaseModel):
    plan: str
    name: str
    trip_cancellation_max: float
    trip_delay_waiting_hours: float
    trip_delay_max: float
    baggage_delay_waiting_hours: float
    baggage_delay_max: float
    baggage_max: float
    per_item_limit: float
    passport_max: float
    emergency_medical_max: float
    deductible: float


class Policy(BaseModel):
    policy_id: str
    customer_id: str
    plan: str
    add_ons: list[str]
    purchased_on: str
    sold_through: str
    trip: dict[str, str | float]
    travelers: list[str]
    status: str
    plan_limits: PlanLimits


class PreviousClaim(BaseModel):
    claim_id: str
    filed_on: str
    incident_date: str
    claim_type: str
    summary: str
    outcome: str
    amount_paid: float


class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    phone: str
    date_of_birth: str
    address: dict[str, str]
    customer_since: str
    previous_claims: list[PreviousClaim]


class ClaimSummary(BaseModel):
    claim_id: str
    claim_type: str
    summary: str
    submitted_on: str
    amount_claimed: float
    status: Status
    decision: Decision | None
    payout: float | None


class Claim(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str
    claim_type: str
    submitted_on: str
    incident_date: str
    incident_location: str
    summary: str
    story: str
    items: list[ClaimItem]
    amount_claimed: float
    documents: list[ClaimDocument]
    status: Status
    decision: Decision | None
    payout: float | None
    reason: str | None
    reference: str | None
    signed_off_by: str | None
    paid_amount: float | None
    customer: Customer
    policy: Policy


class Handler(BaseModel):
    handler_id: str
    name: str
    role: str
    email: str
    can_approve_over_limit: bool


class ClaimEvent(BaseModel):
    operation_id: str
    message: str
    created_at: str


class PolicyWording(BaseModel):
    content: str


class AgentInstructions(BaseModel):
    content: str


class DecideClaimRequest(BaseModel):
    decision: Decision
    payout: float
    reason: str
    reference: str


class PayClaimRequest(BaseModel):
    amount: float


class SignOffRequest(BaseModel):
    handler_id: str


class PaymentResult(BaseModel):
    paid: bool
    status: Status


class RunClaimResult(BaseModel):
    reply: str
