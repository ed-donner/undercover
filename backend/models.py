"""The shapes of UnderCover's records in the API."""

from typing import Literal

from pydantic import BaseModel

Status = Literal["waiting", "in_progress", "awaiting_signoff", "decided"]
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


class Decision(BaseModel):
    decision: DecisionKind
    payout: float
    calculation: str
    reasons: str
    policy_section: str
    decided_at: str


class Payment(BaseModel):
    amount: float
    paid_at: str


class SignOff(BaseModel):
    handler_id: str
    handler_name: str
    signed_at: str


class ClaimSummary(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str
    customer_name: str
    claim_type: str
    submitted_on: str
    summary: str
    amount_claimed: float
    status: Status


class Claim(ClaimSummary):
    incident_date: str
    incident_location: str
    story: str
    items: list[Item]
    documents: list[Document]
    decision: Decision | None
    payment: Payment | None
    sign_off: SignOff | None


class Trip(BaseModel):
    destination: str
    departs_on: str
    returns_on: str
    trip_cost: float


class Plan(BaseModel):
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


class AddOn(BaseModel):
    add_on: str
    name: str
    effect: str
    electronics_per_item_limit: float | None = None


class Policy(BaseModel):
    policy_id: str
    customer_id: str
    plan: str
    add_ons: list[str]
    purchased_on: str
    sold_through: str
    trip: Trip
    travelers: list[str]
    status: str
    plan_details: Plan
    add_on_details: list[AddOn]
    deductible_applies_to: list[str]


class Address(BaseModel):
    street: str
    city: str
    state: str
    zip: str


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
    address: Address
    customer_since: str
    previous_claims: list[PreviousClaim]


class Handler(BaseModel):
    handler_id: str
    name: str
    role: str
    can_approve_over_limit: bool


class Text(BaseModel):
    text: str


class Step(BaseModel):
    step_id: int
    kind: StepKind
    content: str
    created_at: str


class StepRequest(BaseModel):
    kind: StepKind
    content: str


class DecisionRequest(BaseModel):
    decision: DecisionKind
    payout: float
    calculation: str
    reasons: str
    policy_section: str


class PaymentRequest(BaseModel):
    amount: float


class SignOffRequest(BaseModel):
    handler_id: str
