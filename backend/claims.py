"""Reading claims, policies, customers and handlers from the database."""

import json
import sqlite3

from backend.models import (
    ClaimDetail,
    ClaimSummary,
    Customer,
    Decision,
    Handler,
    Payment,
    Policy,
    SignOff,
)


def summaries(db: sqlite3.Connection) -> list[ClaimSummary]:
    rows = db.execute(
        """
        SELECT c.claim_id, cu.name AS customer_name, c.claim_type, c.summary,
               c.amount_claimed, c.submitted_on, c.status,
               d.decision, d.payout
        FROM claims c
        JOIN customers cu ON cu.customer_id = c.customer_id
        LEFT JOIN decisions d ON d.claim_id = c.claim_id
        ORDER BY c.claim_id
        """
    ).fetchall()
    return [ClaimSummary(**row) for row in rows]


def one_decision(db: sqlite3.Connection, claim_id: str) -> Decision | None:
    row = db.execute(
        "SELECT * FROM decisions WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    return Decision(**row) if row else None


def one_payment(db: sqlite3.Connection, claim_id: str) -> Payment | None:
    row = db.execute(
        "SELECT * FROM payments WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    return Payment(**row) if row else None


def one_sign_off(db: sqlite3.Connection, claim_id: str) -> SignOff | None:
    row = db.execute(
        """
        SELECT s.handler_id, s.signed_at, h.data
        FROM sign_offs s JOIN handlers h ON h.handler_id = s.handler_id
        WHERE s.claim_id = ?
        """,
        (claim_id,),
    ).fetchone()
    if row is None:
        return None
    return SignOff(
        handler_id=row["handler_id"],
        handler_name=json.loads(row["data"])["name"],
        signed_at=row["signed_at"],
    )


def claim_detail(db: sqlite3.Connection, claim_id: str) -> ClaimDetail | None:
    row = db.execute(
        """
        SELECT c.status, c.data, cu.name AS customer_name
        FROM claims c JOIN customers cu ON cu.customer_id = c.customer_id
        WHERE c.claim_id = ?
        """,
        (claim_id,),
    ).fetchone()
    if row is None:
        return None
    return ClaimDetail.model_validate(
        {
            **json.loads(row["data"]),
            "status": row["status"],
            "customer_name": row["customer_name"],
            "decision": one_decision(db, claim_id),
            "payment": one_payment(db, claim_id),
            "sign_off": one_sign_off(db, claim_id),
        }
    )


def policy(db: sqlite3.Connection, policy_id: str) -> Policy | None:
    row = db.execute(
        "SELECT data FROM policies WHERE policy_id = ?", (policy_id,)
    ).fetchone()
    return Policy.model_validate_json(row["data"]) if row else None


def customer(db: sqlite3.Connection, customer_id: str) -> Customer | None:
    row = db.execute(
        "SELECT data FROM customers WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    return Customer.model_validate_json(row["data"]) if row else None


def handlers(db: sqlite3.Connection) -> list[Handler]:
    rows = db.execute("SELECT data FROM handlers ORDER BY handler_id").fetchall()
    return [Handler.model_validate_json(row["data"]) for row in rows]
