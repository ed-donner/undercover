"""Read-only business records and backend-owned instructions."""

from fastapi import APIRouter, HTTPException

from backend.dependencies import Database
from backend.instructions import CLAIM_INSTRUCTIONS, INSTRUCTIONS, QUEUE_INSTRUCTIONS
from backend.models import (
    Company,
    Customer,
    Handler,
    PlanDetails,
    Policy,
    QueueEntry,
    TextDocument,
    Wording,
)

router = APIRouter()


@router.get("/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@router.get("/claims", operation_id="list_claims")
def list_claims(db: Database) -> list[QueueEntry]:
    """List the claims queue."""
    return [QueueEntry.model_validate(row) for row in db.queue()]


@router.get("/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, db: Database) -> Policy:
    """Read a customer's policy."""
    return Policy.model_validate(db.get("policies", policy_id))


@router.get("/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str, db: Database) -> Customer:
    """Read a customer and their claim history."""
    return Customer.model_validate(db.get("customers", customer_id))


@router.get("/plans/{name}", operation_id="get_plan")
def get_plan(name: str, db: Database) -> PlanDetails:
    """Read a plan's benefits and available add-ons."""
    return PlanDetails.model_validate(db.plan(name))


@router.get("/handlers", operation_id="list_handlers")
def list_handlers(db: Database) -> list[Handler]:
    """List the claims handlers."""
    return [Handler.model_validate(row) for row in db.records("handlers")]


@router.get("/company", operation_id="get_company")
def get_company(db: Database) -> Company:
    """Read the pilot's company settings."""
    return Company.model_validate(db.get("company", "company"))


@router.get("/wording", operation_id="get_wording")
def get_wording(db: Database) -> Wording:
    """Read the policy wording and version."""
    return Wording.model_validate(db.get("wording", "wording"))


@router.get("/instructions", operation_id="get_instructions")
def get_instructions() -> TextDocument:
    """Read the agent's instructions."""
    return TextDocument(text=INSTRUCTIONS)


@router.get("/instructions/{role}", operation_id="get_role_instructions")
def role_instructions(role: str) -> TextDocument:
    """Read the backend-owned instructions for the queue agent or claim helper."""
    instructions = {"queue": QUEUE_INSTRUCTIONS, "claim": CLAIM_INSTRUCTIONS}
    if role not in instructions:
        raise HTTPException(404, "Instruction set not found")
    return TextDocument(text=instructions[role])
