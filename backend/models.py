"""The shapes of what the API sends and receives."""

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal[
    "waiting", "in_progress", "waiting_for_sign_off", "decided", "needs_handler"
]
Outcome = Literal["approve", "decline", "refer"]


class Item(BaseModel):
    description: str
    category: str
    amount: float


class Document(BaseModel):
    name: str
    type: str
    content: str


class Decision(BaseModel):
    decision: Outcome
    payout: float
    explanation: str
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
    customer_name: str
    claim_type: str
    summary: str
    amount_claimed: float
    submitted_on: str
    status: Status
    decision: Outcome | None
    payout: float | None


class ClaimDetail(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str
    customer_name: str
    claim_type: str
    submitted_on: str
    incident_date: str
    incident_location: str
    summary: str
    story: str
    items: list[Item]
    amount_claimed: float
    documents: list[Document]
    status: Status
    decision: Decision | None
    payment: Payment | None
    sign_off: SignOff | None


class Trip(BaseModel):
    destination: str
    departs_on: str
    returns_on: str
    trip_cost: float


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
    amount_paid: float


class Customer(BaseModel):
    customer_id: str
    name: str
    customer_since: str
    previous_claims: list[PreviousClaim]


class Handler(BaseModel):
    handler_id: str
    name: str
    role: str
    can_approve_over_limit: bool


class Text(BaseModel):
    text: str


class Section(BaseModel):
    number: int
    title: str


class Instructions(BaseModel):
    queue: str
    claim: str


class DecisionRequest(BaseModel):
    decision: Outcome
    payout: float = Field(ge=0)
    explanation: str = Field(min_length=1)
    policy_section: str = Field(min_length=1)


class PaymentRequest(BaseModel):
    amount: float = Field(gt=0)


class SignOffRequest(BaseModel):
    handler_id: str


StepKind = Literal["tool_call", "tool_result", "message", "error", "read"]


class StepRequest(BaseModel):
    kind: StepKind
    text: str


class Step(BaseModel):
    id: int
    kind: StepKind
    text: str
    created_at: str


TodoStatus = Literal["todo", "in_progress", "done", "left_for_handler"]
RunStatus = Literal["running", "finished", "failed"]


class Todo(BaseModel):
    text: str = Field(min_length=1)
    status: TodoStatus


class Run(BaseModel):
    run_id: int
    limit: int
    status: RunStatus
    summary: str
    started_at: str
    finished_at: str | None
    todos: list[Todo]


class StartRunRequest(BaseModel):
    limit: int = Field(ge=1)


class TodosRequest(BaseModel):
    todos: list[Todo]


class FinishRunRequest(BaseModel):
    summary: str
    status: Literal["finished", "failed"]


class FailRequest(BaseModel):
    reason: str = Field(min_length=1)
