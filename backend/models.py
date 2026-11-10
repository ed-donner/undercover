"""API records and monetary values."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PlainSerializer

Money = Annotated[
    Decimal,
    Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False),
    PlainSerializer(float, return_type=float, when_used="json"),
]
QueueStatus = Literal["waiting", "in_progress", "waiting_for_sign_off", "decided"]


class Company(BaseModel):
    name: str
    currency: str
    payout_approval_limit: Money
    policy_wording_version: str


class Item(BaseModel):
    description: str
    category: str
    amount: Money


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
    amount_claimed: Money
    documents: list[Document]
    status: QueueStatus


class QueueEntry(BaseModel):
    claim_id: str
    customer_name: str
    claim_type: str
    summary: str
    amount_claimed: Money
    status: QueueStatus


class Trip(BaseModel):
    destination: str
    departs_on: str
    returns_on: str
    trip_cost: Money


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


class PreviousClaim(BaseModel):
    claim_id: str
    filed_on: str
    incident_date: str
    claim_type: str
    summary: str
    outcome: str
    amount_paid: Money


class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    phone: str
    date_of_birth: str
    address: dict[str, str]
    customer_since: str
    previous_claims: list[PreviousClaim]


class Plan(BaseModel):
    plan: str
    name: str
    trip_cancellation_max: Money
    trip_delay_waiting_hours: int
    trip_delay_max: Money
    baggage_delay_waiting_hours: int
    baggage_delay_max: Money
    baggage_max: Money
    per_item_limit: Money
    passport_max: Money
    emergency_medical_max: Money
    deductible: Money


class AddOn(BaseModel):
    add_on: str
    name: str
    effect: str


class PlanDetails(BaseModel):
    plan: Plan
    add_ons: list[AddOn]
    deductible_applies_to: list[str]
    electronics_per_item_limit: Money


class Handler(BaseModel):
    handler_id: str
    name: str
    role: str
    email: str
    can_approve_over_limit: bool


class TextDocument(BaseModel):
    text: str


class Wording(TextDocument):
    version: str
