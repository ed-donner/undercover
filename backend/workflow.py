"""Transactional decision, sign-off and simulated payment rules."""

import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from backend.activity import LABELS, Activity
from backend.models import (
    ActivityEvent,
    Claim,
    Decision,
    DecisionInput,
    Payment,
    PaymentInput,
    Run,
    SignOff,
    SignOffInput,
)
from backend.store import Store


def now() -> str:
    return datetime.now(UTC).isoformat()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HTTPException(409, message)


class Workflow:
    def __init__(self, store: Store):
        self.store = store

    def detail(self, claim_id: str) -> Claim:
        claim = Claim.model_validate(self.store.claim(claim_id))
        with self.store.connect() as connection:
            decision = connection.execute(
                "SELECT * FROM decisions WHERE claim_id = ?", (claim_id,)
            ).fetchone()
            sign_off = connection.execute(
                "SELECT * FROM sign_offs WHERE claim_id = ?", (claim_id,)
            ).fetchone()
            payment = connection.execute(
                "SELECT * FROM payments WHERE claim_id = ?", (claim_id,)
            ).fetchone()
        if decision:
            claim.decision = Decision(
                run_id=decision["run_id"],
                outcome=decision["outcome"],
                payout=Decimal(decision["payout_cents"]) / 100,
                calculation=decision["calculation"],
                explanation=decision["explanation"],
                policy_sections=json.loads(decision["policy_sections"]),
                recorded_at=decision["recorded_at"],
            )
        if sign_off:
            claim.sign_off = SignOff(
                handler_id=sign_off["handler_id"], signed_at=sign_off["signed_at"]
            )
        if payment:
            claim.payment = Payment(
                amount=Decimal(payment["amount_cents"]) / 100,
                paid_at=payment["paid_at"],
            )
        return claim

    def start(self, claim_id: str) -> Run:
        self.store.claim(claim_id)
        run = Run(
            run_id=str(uuid4()),
            claim_id=claim_id,
            thread_id=str(uuid4()),
            status="running",
            started_at=now(),
            finished_at=None,
            error=None,
        )
        with self.store.transaction() as connection:
            changed = connection.execute(
                "UPDATE claims SET status = 'in_progress' "
                "WHERE id = ? AND status = 'waiting'",
                (claim_id,),
            ).rowcount
            require(changed == 1, "Claim is not waiting")
            connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                tuple(run.model_dump().values()),
            )
            self._event(connection, run.run_id, "run_started")
        return run

    def runs(self, claim_id: str) -> list[Run]:
        self.store.claim(claim_id)
        with self.store.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runs WHERE claim_id = ? ORDER BY started_at", (claim_id,)
            ).fetchall()
        return [Run.model_validate(dict(row)) for row in rows]

    def decide(self, claim_id: str, decision: DecisionInput) -> Claim:
        self.store.claim(claim_id)
        limit = Decimal(
            str(self.store.get("company", "company")["payout_approval_limit"])
        )
        status = "waiting_for_sign_off" if decision.payout > limit else "decided"
        with self.store.transaction() as connection:
            run = connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (decision.run_id,)
            ).fetchone()
            require(
                run is not None
                and run["claim_id"] == claim_id
                and run["status"] == "running",
                "Decision must belong to this claim's active run",
            )
            require(
                connection.execute(
                    "SELECT status FROM claims WHERE id = ?", (claim_id,)
                ).fetchone()["status"]
                == "in_progress",
                "Claim already has a decision",
            )
            connection.execute(
                "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    claim_id,
                    decision.run_id,
                    decision.outcome,
                    int(decision.payout * 100),
                    decision.calculation,
                    decision.explanation,
                    json.dumps(decision.policy_sections),
                    now(),
                ),
            )
            connection.execute(
                "UPDATE claims SET status = ? WHERE id = ?", (status, claim_id)
            )
            self._event(connection, decision.run_id, "decision_recorded")
        return self.detail(claim_id)

    def sign_off(self, claim_id: str, sign_off: SignOffInput) -> Claim:
        self.store.claim(claim_id)
        handler = self.store.get("handlers", sign_off.handler_id)
        require(handler["can_approve_over_limit"], "Handler cannot sign off")
        with self.store.transaction() as connection:
            changed = connection.execute(
                "UPDATE claims SET status = 'decided' "
                "WHERE id = ? AND status = 'waiting_for_sign_off'",
                (claim_id,),
            ).rowcount
            require(changed == 1, "Claim is not waiting for sign-off")
            connection.execute(
                "INSERT INTO sign_offs VALUES (?, ?, ?)",
                (claim_id, sign_off.handler_id, now()),
            )
            decision = connection.execute(
                "SELECT run_id FROM decisions WHERE claim_id = ?", (claim_id,)
            ).fetchone()
            self._event(connection, decision["run_id"], "sign_off_recorded")
        return self.detail(claim_id)

    def pay(self, claim_id: str, payment: PaymentInput) -> Claim:
        self.store.claim(claim_id)
        limit = Decimal(
            str(self.store.get("company", "company")["payout_approval_limit"])
        )
        with self.store.transaction() as connection:
            decision = connection.execute(
                "SELECT * FROM decisions WHERE claim_id = ?", (claim_id,)
            ).fetchone()
            self._check_payment(connection, claim_id, decision, payment)
            signed = connection.execute(
                "SELECT 1 FROM sign_offs WHERE claim_id = ?", (claim_id,)
            ).fetchone()
            require(
                payment.amount <= limit or signed is not None,
                "Handler sign-off required before payment",
            )
            connection.execute(
                "INSERT INTO payments VALUES (?, ?, ?)",
                (claim_id, int(payment.amount * 100), now()),
            )
            self._event(connection, decision["run_id"], "payment_recorded")
        return self.detail(claim_id)

    def payment_blocked(self, claim_id: str) -> None:
        with self.store.transaction() as connection:
            run = connection.execute(
                "SELECT run_id FROM runs WHERE claim_id = ? ORDER BY started_at DESC",
                (claim_id,),
            ).fetchone()
            if run:
                self._event(connection, run["run_id"], "payment_blocked")

    @staticmethod
    def _event(connection: sqlite3.Connection, run_id: str, kind: str) -> None:
        connection.execute(
            "INSERT INTO events (run_id, kind, label, created_at) VALUES (?, ?, ?, ?)",
            (run_id, kind, LABELS[kind], now()),
        )

    def event(self, run_id: str, activity: Activity) -> None:
        with self.store.transaction() as connection:
            run = connection.execute(
                "SELECT status FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise HTTPException(404, "Run not found")
            require(run["status"] == "running", "Run is no longer active")
            self._event(connection, run_id, activity)

    def events(self, claim_id: str) -> list[ActivityEvent]:
        self.store.claim(claim_id)
        with self.store.connect() as connection:
            rows = connection.execute(
                "SELECT events.* FROM events JOIN runs USING (run_id) "
                "WHERE runs.claim_id = ? ORDER BY sequence",
                (claim_id,),
            ).fetchall()
        return [ActivityEvent.model_validate(dict(row)) for row in rows]

    def finish(self, run_id: str, error: str | None) -> None:
        with self.store.transaction() as connection:
            run = connection.execute(
                "SELECT * FROM runs WHERE run_id = ? AND status = 'running'", (run_id,)
            ).fetchone()
            if run is None:
                return
            decision = connection.execute(
                "SELECT 1 FROM decisions WHERE claim_id = ?", (run["claim_id"],)
            ).fetchone()
            if decision is None:
                error = error or "Agent finished without recording a decision."
                connection.execute(
                    "UPDATE claims SET status = 'waiting' WHERE id = ?",
                    (run["claim_id"],),
                )
            status = "failed" if error else "completed"
            connection.execute(
                "UPDATE runs SET status = ?, finished_at = ?, error = ? "
                "WHERE run_id = ?",
                (status, now(), error, run_id),
            )
            self._event(connection, run_id, f"run_{status}")

    def recover(self) -> None:
        with self.store.connect() as connection:
            runs = connection.execute(
                "SELECT run_id FROM runs WHERE status = 'running'"
            ).fetchall()
        for run in runs:
            self.finish(run["run_id"], "Run interrupted by backend restart.")

    @staticmethod
    def _check_payment(connection, claim_id, decision, payment: PaymentInput) -> None:
        require(decision is not None, "Record a decision before payment")
        require(decision["outcome"] == "approve", "Only approved claims can be paid")
        require(
            int(payment.amount * 100) == decision["payout_cents"],
            "Payment must equal the approved payout",
        )
        paid = connection.execute(
            "SELECT 1 FROM payments WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        require(paid is None, "Claim has already been paid")
