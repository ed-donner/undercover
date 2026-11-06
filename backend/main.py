"""The UnderCover backend."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection, Row
from typing import Annotated, Any, Literal, Self

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from backend import documents
from backend.db import DATA, path, transaction
from backend.documents import Document
from backend.seed import seed

INSTRUCTIONS = Path(__file__).parent / "instructions"
MOST_ATTEMPTS = 2
WORKFLOW_COLUMNS = (
    "status",
    "decision",
    "payout",
    "reason",
    "policy_section",
    "decided_at",
    "signed_off_by",
    "signed_off_at",
    "paid_amount",
    "paid_at",
    "attempts",
)
QUEUE_FIELDS = (
    "claim_id",
    "claim_type",
    "summary",
    "submitted_on",
    "amount_claimed",
    "status",
    "decision",
    "payout",
    "paid_amount",
    "attempts",
)
RECORD_QUERIES = {
    "policy": "SELECT record FROM policies WHERE policy_id = ?",
    "customer": "SELECT record FROM customers WHERE customer_id = ?",
    "handler": "SELECT record FROM handlers WHERE handler_id = ?",
}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Seed the database when the backend starts without one."""
    if not path().exists():
        seed()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


class Step(BaseModel):
    """One step the agent took on a claim."""

    thread_id: str
    kind: Literal["tool_call", "tool_result", "reply", "reminder", "failure"]
    name: str
    content: str


class Decision(BaseModel):
    """The agent's decision on a claim."""

    decision: Literal["approve", "decline", "refer"]
    payout: Annotated[float, Field(ge=0)]
    reason: Annotated[str, Field(min_length=1)]
    policy_section: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def payout_fits_the_decision(self) -> Self:
        """Check that an approval pays something, and a decline or referral nothing."""
        if (self.decision == "approve") != (self.payout > 0):
            raise ValueError(
                "An approval needs a payout above $0, and a decline or referral $0."
            )
        return self


class Payment(BaseModel):
    """A payment on an approved claim."""

    amount: Annotated[float, Field(gt=0)]


class Todo(BaseModel):
    """One item on the agent's to-do list for a run."""

    content: Annotated[str, Field(min_length=1)]
    status: Literal["to_do", "in_progress", "done", "left_for_handler"]


class TodoList(BaseModel):
    """The agent's whole to-do list for a run."""

    todos: list[Todo]


class Summary(BaseModel):
    """The agent's summary of a run for the handlers."""

    summary: Annotated[str, Field(min_length=1)]


class SignOff(BaseModel):
    """A handler's sign-off on a payout over the approval limit."""

    handler_id: str


def reference(name: str) -> Any:
    """Read one of the reference documents in data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def approval_limit() -> float:
    """Return the largest payout the agent can pay without a handler's sign-off."""
    return reference("company.json")["payout_approval_limit"]


def money(amount: float) -> str:
    """Show an amount in US dollars, such as $1,250.00."""
    return f"${amount:,.2f}"


def now() -> str:
    """Return the time now, in UTC."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def claim_from(row: Row) -> dict[str, Any]:
    """Combine a claim's record with where it stands."""
    return {**json.loads(row["record"]), **{key: row[key] for key in WORKFLOW_COLUMNS}}


def queue_entry(row: Row) -> dict[str, Any]:
    """Summarize a claim for the queue."""
    claim = claim_from(row)
    return {
        **{key: claim[key] for key in QUEUE_FIELDS},
        "customer_name": row["customer_name"],
    }


def find_claim(db: Connection, claim_id: str) -> dict[str, Any]:
    """Return a claim, or 404 if there's no such claim."""
    row = db.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"There is no claim {claim_id}.")
    return claim_from(row)


def refusal(db: Connection, claim_id: str, action: str) -> HTTPException:
    """Explain why a claim can't take the action asked of it, or 404."""
    claim = find_claim(db, claim_id)
    standing = (
        "left for a handler"
        if claim["status"] == "left_for_handler"
        else claim["status"].replace("_", " ")
    )
    if claim["decision"]:
        standing += f" with the decision to {claim['decision']}"
    return HTTPException(409, f"Claim {claim_id} can't {action}: it is {standing}.")


def find_record(db: Connection, kind: str, record_id: str) -> dict[str, Any]:
    """Return a policy, customer or handler, or 404 if there's no such record."""
    row = db.execute(RECORD_QUERIES[kind], (record_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"There is no {kind} {record_id}.")
    return json.loads(row["record"])


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims() -> list[dict[str, Any]]:
    """List the claims in the queue, with where each one stands."""
    with transaction() as db:
        rows = db.execute(
            "SELECT claims.*, json_extract(customers.record, '$.name') AS customer_name"
            " FROM claims JOIN customers"
            " ON customers.customer_id = json_extract(claims.record, '$.customer_id')"
            " ORDER BY claim_id"
        ).fetchall()
    return [queue_entry(row) for row in rows]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> dict[str, Any]:
    """Get a claim in full, with the decision, sign-off and payment."""
    with transaction() as db:
        return find_claim(db, claim_id)


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str) -> dict[str, Any]:
    """Get a policy, with its plan's limits and the details of its add-ons."""
    with transaction() as db:
        policy = find_record(db, "policy", policy_id)
    plans = reference("plans.json")
    return {
        **policy,
        "plan_details": next(
            plan for plan in plans["plans"] if plan["plan"] == policy["plan"]
        ),
        "add_on_details": [
            add_on
            for add_on in plans["add_ons"]
            if add_on["add_on"] in policy["add_ons"]
        ],
    }


@app.get("/api/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str) -> dict[str, Any]:
    """Get a customer, with their claim history."""
    with transaction() as db:
        return find_record(db, "customer", customer_id)


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[dict[str, Any]]:
    """List the claims handlers."""
    with transaction() as db:
        rows = db.execute("SELECT record FROM handlers ORDER BY handler_id").fetchall()
    return [json.loads(row["record"]) for row in rows]


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> dict[str, str]:
    """Get the policy wording that decisions follow."""
    return {
        "version": reference("company.json")["policy_wording_version"],
        "text": (DATA / "policy_wording.md").read_text(encoding="utf-8"),
    }


@app.get("/api/documents/sections", operation_id="list_sections")
def list_sections() -> list[dict[str, Any]]:
    """List the sections of the policy wording and the claims manual."""
    return documents.contents()


@app.get("/api/documents/search", operation_id="search_documents")
def search_documents(
    query: Annotated[str, Query(min_length=1)],
) -> list[dict[str, Any]]:
    """Find the sections of the policy wording and the claims manual on a query."""
    return documents.search(query)


@app.get("/api/documents/{document}/sections/{section}", operation_id="read_section")
def read_section(document: Document, section: int) -> dict[str, Any]:
    """Read one section of the policy wording or the claims manual in full."""
    found = documents.find(document, section)
    if found is None:
        name = document.replace("_", " ")
        raise HTTPException(404, f"There is no section {section} in the {name}.")
    return found


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> dict[str, str]:
    """Get the agent's instructions for running the queue and for working a claim."""
    return {
        agent: (INSTRUCTIONS / f"{agent}.md").read_text(encoding="utf-8")
        for agent in ("queue", "claim")
    }


@app.post("/api/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str) -> dict[str, Any]:
    """Start work on a waiting claim."""
    with transaction() as db:
        cursor = db.execute(
            "UPDATE claims SET status = 'in_progress'"
            " WHERE claim_id = ? AND status = 'waiting'",
            (claim_id,),
        )
        if not cursor.rowcount:
            raise refusal(db, claim_id, "be started")
        return find_claim(db, claim_id)


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str) -> list[dict[str, Any]]:
    """List the steps the agent took on a claim, in order."""
    with transaction() as db:
        find_claim(db, claim_id)
        rows = db.execute(
            "SELECT * FROM steps WHERE claim_id = ? ORDER BY step_id", (claim_id,)
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/claims/{claim_id}/steps", operation_id="add_step")
def add_step(claim_id: str, step: Step) -> dict[str, Any]:
    """Record one step the agent took on a claim."""
    with transaction() as db:
        find_claim(db, claim_id)
        cursor = db.execute(
            "INSERT INTO steps (claim_id, thread_id, kind, name, content, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (claim_id, step.thread_id, step.kind, step.name, step.content, now()),
        )
        row = db.execute(
            "SELECT * FROM steps WHERE step_id = ?", (cursor.lastrowid,)
        ).fetchone()
    return dict(row)


@app.post("/api/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, decision: Decision) -> dict[str, Any]:
    """Record the decision on a claim in progress, which is final."""
    if decision.decision != "approve":
        status = "decided"
    elif decision.payout > approval_limit():
        status = "waiting_for_sign_off"
    else:
        status = "in_progress"
    with transaction() as db:
        cursor = db.execute(
            "UPDATE claims SET status = ?, decision = ?, payout = ?, reason = ?,"
            " policy_section = ?, decided_at = ?"
            " WHERE claim_id = ? AND status = 'in_progress' AND decision IS NULL",
            (
                status,
                decision.decision,
                round(decision.payout, 2),
                decision.reason,
                decision.policy_section,
                now(),
                claim_id,
            ),
        )
        if not cursor.rowcount:
            raise refusal(db, claim_id, "take a decision")
        return find_claim(db, claim_id)


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment) -> dict[str, Any]:
    """Pay an approved claim its payout, if it needs no sign-off."""
    limit = approval_limit()
    with transaction() as db:
        claim = find_claim(db, claim_id)
        payout = claim["payout"]
        if claim["decision"] != "approve":
            message = f"Claim {claim_id} can't be paid: only an approved claim can."
            raise HTTPException(409, message)
        if claim["paid_amount"] is not None:
            message = f"Claim {claim_id} has already been paid {money(payout)}."
            raise HTTPException(409, message)
        if claim["status"] == "left_for_handler":
            raise refusal(db, claim_id, "be paid")
        if round(payment.amount, 2) != payout:
            message = (
                f"Claim {claim_id} can't be paid {money(payment.amount)}:"
                f" the approved payout is {money(payout)}."
            )
            raise HTTPException(409, message)
        if payout > limit:
            message = f"A payout over {money(limit)} waits for a handler's sign-off."
            raise HTTPException(403, message)
        db.execute(
            "UPDATE claims SET status = 'decided', paid_amount = payout, paid_at = ?"
            " WHERE claim_id = ? AND paid_amount IS NULL",
            (now(), claim_id),
        )
        return find_claim(db, claim_id)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off")
def sign_off(claim_id: str, sign_off: SignOff) -> dict[str, Any]:
    """Sign off a payout over the approval limit, which pays it."""
    limit = approval_limit()
    with transaction() as db:
        handler = find_record(db, "handler", sign_off.handler_id)
        if not handler["can_approve_over_limit"]:
            message = f"{handler['name']} can't sign off payouts over {money(limit)}."
            raise HTTPException(403, message)
        moment = now()
        cursor = db.execute(
            "UPDATE claims SET status = 'decided', paid_amount = payout, paid_at = ?,"
            " signed_off_by = ?, signed_off_at = ?"
            " WHERE claim_id = ? AND status = 'waiting_for_sign_off'",
            (moment, sign_off.handler_id, moment, claim_id),
        )
        if not cursor.rowcount:
            raise refusal(db, claim_id, "be signed off")
        return find_claim(db, claim_id)


@app.post("/api/claims/{claim_id}/release", operation_id="release_claim")
def release_claim(claim_id: str) -> dict[str, Any]:
    """Put back a claim after a failed attempt, or leave it for a handler."""
    with transaction() as db:
        cursor = db.execute(
            "UPDATE claims SET attempts = attempts + 1, status = CASE"
            " WHEN decision IS NULL AND attempts + 1 < ? THEN 'waiting'"
            " ELSE 'left_for_handler' END"
            " WHERE claim_id = ? AND status = 'in_progress'",
            (MOST_ATTEMPTS, claim_id),
        )
        if not cursor.rowcount:
            raise refusal(db, claim_id, "be released")
        return find_claim(db, claim_id)


def run_from(row: Row) -> dict[str, Any]:
    """Describe a run with its to-do list."""
    return {**dict(row), "todos": json.loads(row["todos"])}


def find_run(db: Connection, run_id: int) -> dict[str, Any]:
    """Return a run, or 404 if there's no such run."""
    row = db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"There is no run {run_id}.")
    return run_from(row)


def unfinished_run(db: Connection, run_id: int, rowcount: int) -> dict[str, Any]:
    """Return a run just changed, or explain that it had already finished."""
    run = find_run(db, run_id)
    if not rowcount:
        raise HTTPException(409, f"Run {run_id} has finished.")
    return run


@app.post("/api/runs", operation_id="start_run")
def start_run() -> dict[str, Any]:
    """Start a run of the agent on the queue, with an empty to-do list."""
    with transaction() as db:
        cursor = db.execute("INSERT INTO runs (started_at) VALUES (?)", (now(),))
        return find_run(db, cursor.lastrowid or 0)


@app.put("/api/runs/{run_id}/todos", operation_id="update_todos")
def update_todos(run_id: int, todo_list: TodoList) -> dict[str, Any]:
    """Replace the agent's to-do list for a run that hasn't finished."""
    todos = json.dumps([todo.model_dump() for todo in todo_list.todos])
    with transaction() as db:
        cursor = db.execute(
            "UPDATE runs SET todos = ? WHERE run_id = ? AND finished_at IS NULL",
            (todos, run_id),
        )
        return unfinished_run(db, run_id, cursor.rowcount)


@app.post("/api/runs/{run_id}/finish", operation_id="finish_run")
def finish_run(run_id: int, summary: Summary) -> dict[str, Any]:
    """Finish a run with the agent's summary for the handlers."""
    with transaction() as db:
        cursor = db.execute(
            "UPDATE runs SET summary = ?, finished_at = ?"
            " WHERE run_id = ? AND finished_at IS NULL",
            (summary.summary, now(), run_id),
        )
        return unfinished_run(db, run_id, cursor.rowcount)


@app.get("/api/runs/latest", operation_id="get_latest_run")
def get_latest_run() -> dict[str, Any] | None:
    """Get the most recent run, or nothing before the first."""
    with transaction() as db:
        row = db.execute("SELECT * FROM runs ORDER BY run_id DESC LIMIT 1").fetchone()
    return None if row is None else run_from(row)
