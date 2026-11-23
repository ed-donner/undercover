"""The shapes the API sends and receives."""

from typing import Literal

from pydantic import BaseModel

ClaimState = Literal["waiting", "in progress", "waiting for sign-off", "decided"]
DecisionKind = Literal["approve", "decline", "refer"]
StepKind = Literal["tool_call", "tool_result", "message", "error"]


class Item(BaseModel):
    description: str
    category: str
    amount: float


class Document(BaseModel):
    name: str
    type: str
    content: str


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
    items: list[Item]
    amount_claimed: float
    documents: list[Document]


class Trip(BaseModel):
    destination: str
    departs_on: str
    returns_on: str
    trip_cost: float


class Policy(BaseModel):
    policy_id: str
    plan: str
    add_ons: list[str]
    purchased_on: str
    sold_through: str
    trip: Trip
    travelers: list[str]


class PlanLimits(BaseModel):
    plan: str
    name: str
    trip_cancellation_max: float
    trip_delay_waiting_hours: int
    trip_delay_max: float
    baggage_delay_waiting_hours: int
    baggage_delay_max: float
    baggage_max: float
    per_item_limit: float
    passport_max: float
    emergency_medical_max: float
    deductible: float


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
    customer_since: str
    previous_claims: list[PreviousClaim]


class ClaimContext(BaseModel):
    claim: Claim
    policy: Policy
    plan: PlanLimits
    customer: Customer


class DecisionIn(BaseModel):
    decision: DecisionKind
    payout: float
    explanation: str
    policy_section: str


class DecisionRecord(BaseModel):
    decision: DecisionKind
    payout: float
    explanation: str
    policy_section: str
    decided_at: str


class PaymentIn(BaseModel):
    amount: float


class SignOffIn(BaseModel):
    handler_id: str


class Payment(BaseModel):
    amount: float
    signed_off_by: str | None
    paid_at: str


class StepIn(BaseModel):
    kind: StepKind
    text: str


class Step(BaseModel):
    id: int
    kind: StepKind
    text: str
    created_at: str


class ClaimDetail(ClaimContext):
    state: ClaimState
    decision: DecisionRecord | None
    payment: Payment | None


class ClaimSummary(BaseModel):
    claim_id: str
    customer_name: str
    claim_type: str
    summary: str
    submitted_on: str
    amount_claimed: float
    state: ClaimState
    decision: DecisionKind | None
    payout: float | None


class Handler(BaseModel):
    handler_id: str
    name: str
    role: str
    can_approve_over_limit: bool


class PolicyWording(BaseModel):
    text: str


class Instructions(BaseModel):
    text: str


class RunStatus(BaseModel):
    active: bool
    claim_id: str | None
