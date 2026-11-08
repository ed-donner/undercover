"""SQLite storage for Shoppie's support requests."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "customer_orders.json"
STEP_MESSAGES = {
    "started": "The Shoppie Agent started reviewing this request.",
    "reading_request": "The agent retrieved the customer request and order details.",
    "checking_policy": "The agent checked the applicable Shoppie policy.",
    "preparing_recommendation": (
        "The agent prepared a recommendation for support review."
    ),
    "error": "The agent could not complete its review; support review is needed.",
}


class Store:
    """Read and update support request records in SQLite."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def connect(self) -> sqlite3.Connection:
        """Open a connection to the request database."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        """Create the request table and seed source records once."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        source = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        with closing(self.connect()) as connection, connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS support_requests (
                    request_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    customer_id TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    request_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    source_status TEXT NOT NULL,
                    queue_status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    order_json TEXT NOT NULL,
                    action_result_json TEXT,
                    recommendation_json TEXT,
                    review_json TEXT
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS request_steps (
                    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL REFERENCES support_requests(request_id),
                    stage TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            for customer in source["customers"]:
                for order in customer["orders"]:
                    safe_order = self.safe_order(order)
                    for request in order["requests"]:
                        source_status = request["status"]
                        queue_status = (
                            "decided" if source_status == "completed" else "waiting"
                        )
                        safe_request = self.safe_request(request)
                        connection.execute(
                            """INSERT OR IGNORE INTO support_requests (
                                request_id, order_id, customer_id, customer_name,
                                request_type, created_at, source_status, queue_status,
                                request_json, order_json, action_result_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                request["request_id"],
                                order["order_id"],
                                customer["customer_id"],
                                customer["name"],
                                request["type"],
                                request["created_at"],
                                source_status,
                                queue_status,
                                json.dumps(safe_request),
                                json.dumps(safe_order),
                                json.dumps(request["action_result"])
                                if request["action_result"]
                                else None,
                            ),
                        )
                        existing = connection.execute(
                            "SELECT request_json FROM support_requests "
                            "WHERE request_id = ?",
                            (request["request_id"],),
                        ).fetchone()
                        stored_request = json.loads(existing["request_json"])
                        stored_request["evidence"] = request["evidence"]
                        connection.execute(
                            "UPDATE support_requests SET request_json = ? "
                            "WHERE request_id = ?",
                            (json.dumps(stored_request), request["request_id"]),
                        )

    @staticmethod
    def safe_request(request: dict[str, Any]) -> dict[str, Any]:
        """Select customer-provided request fields and recorded action results."""
        return {
            "request_id": request["request_id"],
            "type": request["type"],
            "created_at": request["created_at"],
            "customer_message": request["customer_message"],
            "requested_scope": request["requested_scope"],
            "evidence": request["evidence"],
        }

    @staticmethod
    def safe_order(order: dict[str, Any]) -> dict[str, Any]:
        """Select order fields needed to review a customer request."""
        return {
            "order_id": order["order_id"],
            "placed_at": order["placed_at"],
            "fulfillment_status": order["fulfillment_status"],
            "payment_status": order["payment_status"],
            "payment_method": order["payment_method"],
            "delivery_window": order.get("delivery_window"),
            "delivered_at": order.get("delivered_at"),
            "items": order["items"],
            "subtotal": order["subtotal"],
            "delivery_fee": order["delivery_fee"],
            "total": order["total"],
        }

    def list_requests(self) -> list[dict[str, Any]]:
        """Return queue summaries ordered by creation time."""
        with closing(self.connect()) as connection, connection:
            rows = connection.execute(
                """SELECT request_id, order_id, customer_id, customer_name,
                          request_type, created_at, queue_status, recommendation_json
                   FROM support_requests ORDER BY created_at, request_id"""
            ).fetchall()
        return [
            {
                "request_id": row["request_id"],
                "order_id": row["order_id"],
                "customer_id": row["customer_id"],
                "customer_name": row["customer_name"],
                "type": row["request_type"],
                "created_at": row["created_at"],
                "status": row["queue_status"],
                "recommendation": self.decode(row["recommendation_json"]),
            }
            for row in rows
        ]

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        """Return a request, safe customer/order details, and its progress."""
        with closing(self.connect()) as connection, connection:
            row = connection.execute(
                "SELECT * FROM support_requests WHERE request_id = ?", (request_id,)
            ).fetchone()
            if row is None:
                return None
            history_rows = connection.execute(
                """SELECT request_id, request_type, created_at, request_json,
                          action_result_json
                   FROM support_requests WHERE customer_id = ? AND request_id != ?
                   ORDER BY created_at""",
                (row["customer_id"], request_id),
            ).fetchall()
            step_rows = connection.execute(
                """SELECT stage, message, created_at FROM request_steps
                   WHERE request_id = ? ORDER BY step_id""",
                (request_id,),
            ).fetchall()
        return {
            "request": json.loads(row["request_json"]),
            "customer": {
                "customer_id": row["customer_id"],
                "name": row["customer_name"],
            },
            "order": json.loads(row["order_json"]),
            "history": [
                {
                    "request": json.loads(history["request_json"]),
                    "action_result": self.decode(history["action_result_json"]),
                }
                for history in history_rows
            ],
            "status": row["queue_status"],
            "action_result": self.decode(row["action_result_json"]),
            "recommendation": self.decode(row["recommendation_json"]),
            "review": self.decode(row["review_json"]),
            "steps": [dict(step) for step in step_rows],
        }

    def start_run(self, request_id: str) -> bool:
        """Move an eligible request into progress and reset its prior run."""
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                """UPDATE support_requests SET queue_status = 'in_progress',
                       recommendation_json = NULL, review_json = NULL
                   WHERE request_id = ? AND queue_status IN (
                       'waiting', 'waiting_for_agent_review'
                   )""",
                (request_id,),
            )
            if cursor.rowcount != 1:
                return False
            connection.execute(
                "DELETE FROM request_steps WHERE request_id = ?", (request_id,)
            )
            self._insert_step(connection, request_id, "started")
        return True

    def add_step(self, request_id: str, stage: str) -> bool:
        """Record a fixed progress message while a request is running."""
        if stage not in STEP_MESSAGES or stage in {"started", "error"}:
            return False
        with closing(self.connect()) as connection, connection:
            status = connection.execute(
                "SELECT queue_status FROM support_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if status is None or status["queue_status"] != "in_progress":
                return False
            self._insert_step(connection, request_id, stage)
        return True

    def save_recommendation(
        self, request_id: str, recommendation: dict[str, Any]
    ) -> bool:
        """Persist an agent recommendation and await support review."""
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                """UPDATE support_requests SET recommendation_json = ?,
                       queue_status = 'waiting_for_agent_review'
                   WHERE request_id = ? AND queue_status = 'in_progress'""",
                (json.dumps(recommendation), request_id),
            )
            if cursor.rowcount != 1:
                return False
            self._insert_step(connection, request_id, "preparing_recommendation")
        return True

    def fail_run(self, request_id: str) -> bool:
        """Keep failed agent work in the support review queue."""
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                """UPDATE support_requests SET
                       queue_status = 'waiting_for_agent_review',
                       recommendation_json = NULL
                   WHERE request_id = ? AND queue_status = 'in_progress'""",
                (request_id,),
            )
            if cursor.rowcount == 1:
                self._insert_step(connection, request_id, "error")
        return cursor.rowcount == 1

    def record_review(self, request_id: str, review: dict[str, Any]) -> bool:
        """Store a support-agent decision without executing an order action."""
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                """UPDATE support_requests SET
                       review_json = ?, queue_status = 'decided'
                   WHERE request_id = ?
                     AND queue_status = 'waiting_for_agent_review'""",
                (json.dumps(review), request_id),
            )
        return cursor.rowcount == 1

    @staticmethod
    def _insert_step(
        connection: sqlite3.Connection, request_id: str, stage: str
    ) -> None:
        connection.execute(
            """INSERT INTO request_steps (request_id, stage, message, created_at)
               VALUES (?, ?, ?, ?)""",
            (request_id, stage, STEP_MESSAGES[stage], datetime.now(UTC).isoformat()),
        )

    @staticmethod
    def decode(value: str | None) -> Any:
        """Decode stored JSON when a value exists."""
        return json.loads(value) if value else None
