"""The UnderCover backend."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request

from backend.instructions import INSTRUCTIONS
from backend.models import (
    Claim,
    Company,
    Customer,
    Handler,
    PlanDetails,
    Policy,
    QueueEntry,
    TextDocument,
    Wording,
)
from backend.store import Store


def store(request: Request) -> Store:
    return request.app.state.store


Database = Annotated[Store, Depends(store)]


def create_app(database_path: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.store.initialize()
        yield

    application = FastAPI(title="UnderCover", lifespan=lifespan)
    application.state.store = Store(
        database_path or Path(os.getenv("DATABASE_PATH", "undercover.db"))
    )
    application.include_router(router)
    return application


router = APIRouter(prefix="/api")


@router.get("/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@router.get("/claims", operation_id="list_claims")
def list_claims(db: Database) -> list[QueueEntry]:
    """List the claims queue."""
    return [QueueEntry.model_validate(row) for row in db.queue()]


@router.get("/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, db: Database) -> Claim:
    """Read a complete claim."""
    return Claim.model_validate(db.claim(claim_id))


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


app = create_app()
