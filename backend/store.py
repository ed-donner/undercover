"""SQLite records with an explicit seed allowlist."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from backend.models import Company

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MONEY_KEYS = {
    "amount",
    "amount_claimed",
    "amount_paid",
    "trip_cost",
    "deductible",
    "trip_cancellation_max",
    "trip_delay_max",
    "baggage_delay_max",
    "baggage_max",
    "per_item_limit",
    "passport_max",
    "emergency_medical_max",
    "electronics_per_item_limit",
    "payout_approval_limit",
}
SEED_RECORDS = (
    ("claims", "claim_id"),
    ("policies", "policy_id"),
    ("customers", "customer_id"),
    ("handlers", "handler_id"),
)


def money_tree(value: Any, *, storing: bool) -> Any:
    """Store monetary fields as integer cents and decode them exactly."""
    if isinstance(value, list):
        return [money_tree(item, storing=storing) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in MONEY_KEYS:
            result[key] = int(Decimal(str(item)) * 100) if storing else item / 100
        else:
            result[key] = money_tree(item, storing=storing)
    return result


class Store:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS records (
                    kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY (kind, id)
                );
                CREATE TABLE IF NOT EXISTS claims (
                    id TEXT PRIMARY KEY, status TEXT NOT NULL
                );
            """)
        with self.transaction() as connection:
            if connection.execute("SELECT 1 FROM records LIMIT 1").fetchone():
                return
            self._seed(connection)

    def _seed(self, connection: sqlite3.Connection) -> None:
        for kind, key in SEED_RECORDS:
            for record in json.loads((DATA_DIR / f"{kind}.json").read_text()):
                self._insert(connection, kind, record[key], record)
                if kind == "claims":
                    connection.execute(
                        "INSERT INTO claims VALUES (?, 'waiting')", (record[key],)
                    )
        company = Company.model_validate(
            json.loads((DATA_DIR / "company.json").read_text())
        ).model_dump(mode="json")
        self._insert(connection, "company", "company", company)
        plans = json.loads((DATA_DIR / "plans.json").read_text())
        self._insert(connection, "plans", "plans", plans)
        self._insert(
            connection,
            "wording",
            "wording",
            {
                "text": (DATA_DIR / "policy_wording.md").read_text(),
                "version": company["policy_wording_version"],
            },
        )

    @staticmethod
    def _insert(connection: sqlite3.Connection, kind: str, key: str, body: Any) -> None:
        connection.execute(
            "INSERT INTO records VALUES (?, ?, ?)",
            (kind, key, json.dumps(money_tree(body, storing=True))),
        )

    def get(self, kind: str, key: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT body FROM records WHERE kind = ? AND id = ?", (kind, key)
            ).fetchone()
        if row is None:
            raise HTTPException(404, "Record not found")
        return money_tree(json.loads(row["body"]), storing=False)

    def records(self, kind: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT body FROM records WHERE kind = ? ORDER BY id", (kind,)
            ).fetchall()
        return [money_tree(json.loads(row["body"]), storing=False) for row in rows]

    def claim(self, claim_id: str) -> dict[str, Any]:
        claim = self.get("claims", claim_id)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT status FROM claims WHERE id = ?", (claim_id,)
            ).fetchone()
        claim["status"] = row["status"]
        return claim

    def queue(self) -> list[dict[str, Any]]:
        customers = {
            row["customer_id"]: row["name"] for row in self.records("customers")
        }
        return [
            {
                **self.claim(row["claim_id"]),
                "customer_name": customers[row["customer_id"]],
            }
            for row in self.records("claims")
        ]

    def plan(self, name: str) -> dict[str, Any]:
        catalog = self.get("plans", "plans")
        for plan in catalog["plans"]:
            if plan["plan"] == name:
                return {
                    "plan": plan,
                    "add_ons": catalog["add_ons"],
                    "deductible_applies_to": catalog["deductible_applies_to"],
                    "electronics_per_item_limit": catalog["add_ons"][2][
                        "electronics_per_item_limit"
                    ],
                }
        raise HTTPException(404, "Plan not found")
