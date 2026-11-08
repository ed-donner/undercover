"""SQLite storage for Shoppie's support requests and agent runs."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "customer_orders.json"
MAX_ATTEMPTS = 2
STEP_MESSAGES = {
    "started": "The Shoppie Agent started reviewing this request.",
    "reading_request": "The agent retrieved the customer request and order details.",
    "checking_policy": "The agent checked the applicable Shoppie policy.",
    "preparing_recommendation": (
        "The agent prepared a recommendation for support review."
    ),
    "error": "This attempt failed; the request is back in the queue to be tried again.",
    "left_for_support": (
        "The agent could not complete its review after two attempts; "
        "support review is needed."
    ),
}
AGENT_STAGES = {"reading_request", "checking_policy"}
TodoStatus = Literal["to_do", "in_progress", "done", "left_for_support"]
FailureResult = Literal["waiting", "left_for_support"]


def now() -> str:
    """Return the current UTC time as ISO text."""
    return datetime.now(UTC).isoformat()


class Store:
    """Read and update support requests and agent runs in SQLite."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def connect(self) -> sqlite3.Connection:
        """Open a connection to the request database."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        """Create the tables, seed source records once and recover stopped work."""
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
                    recommendation_json TEXT,
                    review_json TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0
                )"""
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(support_requests)")
            }
            if "attempts" not in columns:
                connection.execute(
                    "ALTER TABLE support_requests "
                    "ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0"
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
            connection.execute(
                """CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    cap INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    summary TEXT
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS run_todos (
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    position INTEGER NOT NULL,
                    request_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    PRIMARY KEY (run_id, request_id)
                )"""
            )
            for customer in source["customers"]:
                for order in customer["orders"]:
                    safe_order = self.safe_order(order)
                    for request in order["requests"]:
                        safe_request = self.safe_request(request)
                        connection.execute(
                            """INSERT OR IGNORE INTO support_requests (
                                request_id, order_id, customer_id, customer_name,
                                request_type, created_at, source_status, queue_status,
                                request_json, order_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'waiting', ?, ?)""",
                            (
                                request["request_id"],
                                order["order_id"],
                                customer["customer_id"],
                                customer["name"],
                                request["type"],
                                request["created_at"],
                                request["status"],
                                json.dumps(safe_request),
                                json.dumps(safe_order),
                            ),
                        )
                        connection.execute(
                            "UPDATE support_requests SET request_json = ?, "
                            "order_json = ? WHERE request_id = ?",
                            (
                                json.dumps(safe_request),
                                json.dumps(safe_order),
                                request["request_id"],
                            ),
                        )
            connection.execute(
                "UPDATE support_requests SET queue_status = 'waiting' "
                "WHERE queue_status = 'in_progress'"
            )
            connection.execute(
                "UPDATE runs SET status = 'failed', finished_at = ?, "
                "summary = 'The run stopped when the service restarted.' "
                "WHERE status = 'running'",
                (now(),),
            )

    def reseed(self) -> None:
        """Delete the database and rebuild it from the source records."""
        self.database_path.unlink(missing_ok=True)
        self.initialize()

    @staticmethod
    def safe_request(request: dict[str, Any]) -> dict[str, Any]:
        """Select the customer-provided request fields."""
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
            "fulfillment_events": order["fulfillment_events"],
            "shipment": order.get("shipment"),
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
                          request_type, created_at, queue_status, recommendation_json,
                          review_json, attempts
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
                "attempts": row["attempts"],
                "recommendation": self.decode(row["recommendation_json"]),
                "review": self.decode(row["review_json"]),
            }
            for row in rows
        ]

    def list_waiting(self) -> list[dict[str, str]]:
        """Return the id, type and creation time of each waiting request."""
        with closing(self.connect()) as connection, connection:
            rows = connection.execute(
                """SELECT request_id, request_type, created_at FROM support_requests
                   WHERE queue_status = 'waiting' ORDER BY created_at, request_id"""
            ).fetchall()
        return [
            {
                "request_id": row["request_id"],
                "type": row["request_type"],
                "created_at": row["created_at"],
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
            "status": row["queue_status"],
            "attempts": row["attempts"],
            "recommendation": self.decode(row["recommendation_json"]),
            "review": self.decode(row["review_json"]),
            "steps": [dict(step) for step in step_rows],
        }

    def start_request(self, request_id: str) -> int | None:
        """Move a waiting request into progress and return its attempt number."""
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                """UPDATE support_requests SET queue_status = 'in_progress'
                   WHERE request_id = ? AND queue_status = 'waiting'""",
                (request_id,),
            )
            if cursor.rowcount != 1:
                return None
            attempts = connection.execute(
                "SELECT attempts FROM support_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()["attempts"]
            if attempts == 0:
                connection.execute(
                    "DELETE FROM request_steps WHERE request_id = ?", (request_id,)
                )
            attempt = attempts + 1
            self._insert_step(
                connection,
                request_id,
                "started",
                f"{STEP_MESSAGES['started']} Attempt {attempt} of {MAX_ATTEMPTS}.",
            )
        return attempt

    def is_in_progress(self, request_id: str) -> bool:
        """Report whether the agent is working on a request."""
        with closing(self.connect()) as connection, connection:
            row = connection.execute(
                "SELECT queue_status FROM support_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        return row is not None and row["queue_status"] == "in_progress"

    def add_step(self, request_id: str, stage: str, message: str = "") -> bool:
        """Record a progress step while a request is running."""
        with closing(self.connect()) as connection, connection:
            status = connection.execute(
                "SELECT queue_status FROM support_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if status is None or status["queue_status"] != "in_progress":
                return False
            self._insert_step(connection, request_id, stage, message)
        return True

    def save_recommendation(
        self, request_id: str, recommendation: dict[str, Any]
    ) -> bool:
        """Persist an agent recommendation and await support review."""
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                """UPDATE support_requests SET recommendation_json = ?,
                       queue_status = 'waiting_for_agent_review'
                   WHERE request_id = ? AND queue_status = 'in_progress'
                     AND recommendation_json IS NULL""",
                (json.dumps(recommendation), request_id),
            )
            if cursor.rowcount != 1:
                return False
            self._insert_step(connection, request_id, "preparing_recommendation")
        return True

    def fail_request(self, request_id: str) -> FailureResult | None:
        """Count a failed attempt: back to the queue once, then left for support."""
        with closing(self.connect()) as connection, connection:
            row = connection.execute(
                """SELECT attempts FROM support_requests
                   WHERE request_id = ? AND queue_status = 'in_progress'""",
                (request_id,),
            ).fetchone()
            if row is None:
                return None
            attempts = row["attempts"] + 1
            exhausted = attempts >= MAX_ATTEMPTS
            connection.execute(
                "UPDATE support_requests SET attempts = ?, queue_status = ?, "
                "recommendation_json = NULL WHERE request_id = ?",
                (
                    attempts,
                    "waiting_for_agent_review" if exhausted else "waiting",
                    request_id,
                ),
            )
            self._insert_step(
                connection, request_id, "left_for_support" if exhausted else "error"
            )
        return "left_for_support" if exhausted else "waiting"

    def record_review(self, request_id: str, review: dict[str, Any]) -> bool:
        """Store a support-agent decision without executing an order action."""
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                """UPDATE support_requests SET
                       review_json = ?, queue_status = 'decided'
                   WHERE request_id = ?
                     AND queue_status = 'waiting_for_agent_review'
                     AND review_json IS NULL""",
                (json.dumps(review), request_id),
            )
        return cursor.rowcount == 1

    def create_run(self, cap: int) -> str | None:
        """Start a run record unless another run is still running."""
        run_id = f"RUN-{uuid4().hex[:8].upper()}"
        with closing(self.connect()) as connection, connection:
            running = connection.execute(
                "SELECT 1 FROM runs WHERE status = 'running'"
            ).fetchone()
            if running:
                return None
            connection.execute(
                "INSERT INTO runs (run_id, cap, status, started_at) "
                "VALUES (?, ?, 'running', ?)",
                (run_id, cap, now()),
            )
        return run_id

    def finish_run(self, run_id: str, status: str, summary: str) -> None:
        """Close a run with its summary."""
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "UPDATE runs SET status = ?, summary = ?, finished_at = ? "
                "WHERE run_id = ?",
                (status, summary, now(), run_id),
            )

    def is_running(self, run_id: str) -> bool:
        """Report whether a run is still running."""
        with closing(self.connect()) as connection, connection:
            row = connection.execute(
                "SELECT status FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return row is not None and row["status"] == "running"

    def current_run(self) -> dict[str, Any] | None:
        """Return the latest run with its to-do list."""
        with closing(self.connect()) as connection, connection:
            run = connection.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            if run is None:
                return None
            todos = connection.execute(
                """SELECT request_id, title, status FROM run_todos
                   WHERE run_id = ? ORDER BY position""",
                (run["run_id"],),
            ).fetchall()
        return {**dict(run), "todos": [dict(todo) for todo in todos]}

    def write_todos(self, run_id: str, todos: list[dict[str, str]]) -> None:
        """Replace a run's to-do list."""
        with closing(self.connect()) as connection, connection:
            connection.execute("DELETE FROM run_todos WHERE run_id = ?", (run_id,))
            connection.executemany(
                """INSERT INTO run_todos (run_id, position, request_id, title, status)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (run_id, index, todo["request_id"], todo["title"], todo["status"])
                    for index, todo in enumerate(todos)
                ],
            )

    def update_todo(self, run_id: str, request_id: str, status: TodoStatus) -> None:
        """Set one to-do item's status, adding the item if the plan missed it."""
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE run_todos SET status = ? WHERE run_id = ? AND request_id = ?",
                (status, run_id, request_id),
            )
            if cursor.rowcount == 0:
                connection.execute(
                    """INSERT INTO run_todos
                           (run_id, position, request_id, title, status)
                       SELECT ?, COALESCE(MAX(position), -1) + 1, ?, ?, ?
                       FROM run_todos WHERE run_id = ?""",
                    (run_id, request_id, f"Work {request_id}", status, run_id),
                )

    @staticmethod
    def _insert_step(
        connection: sqlite3.Connection, request_id: str, stage: str, message: str = ""
    ) -> None:
        connection.execute(
            """INSERT INTO request_steps (request_id, stage, message, created_at)
               VALUES (?, ?, ?, ?)""",
            (request_id, stage, message or STEP_MESSAGES[stage], now()),
        )

    @staticmethod
    def decode(value: str | None) -> Any:
        """Decode stored JSON when a value exists."""
        return json.loads(value) if value else None
