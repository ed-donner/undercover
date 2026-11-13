"""Transactional scope, cap and completion guards for the queue agent."""

import json
import sqlite3
from uuid import uuid4

from fastapi import HTTPException

from backend.harness_models import AgentRun, Completion, NamedStart, Start, Task, Todo
from backend.run_state import now, require
from backend.store import Store


def parent_row(connection: sqlite3.Connection, run_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Agent run not found")
    return row


def task_rows(connection: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT * FROM todos WHERE parent_run_id = ? ORDER BY position", (run_id,)
    ).fetchall()


def eligible(connection: sqlite3.Connection) -> set[str]:
    return {
        row["id"]
        for row in connection.execute(
            "SELECT id FROM claims WHERE status = 'waiting' AND needs_handler = 0 "
            "AND NOT EXISTS (SELECT 1 FROM decisions WHERE claim_id = claims.id)"
        )
    }


def sync_tasks(connection: sqlite3.Connection, run_id: str) -> None:
    for task in task_rows(connection, run_id):
        if not task["admitted"]:
            continue
        claim = connection.execute(
            "SELECT c.*, d.outcome, p.claim_id AS paid FROM claims c "
            "LEFT JOIN decisions d ON d.claim_id = c.id "
            "LEFT JOIN payments p ON p.claim_id = c.id WHERE c.id = ?",
            (task["claim_id"],),
        ).fetchone()
        state, reason = task_result(claim)
        connection.execute(
            "UPDATE todos SET state = ?, reason = ? WHERE task_id = ?",
            (state, reason, task["task_id"]),
        )


def task_result(claim: sqlite3.Row) -> tuple[str, str]:
    if claim["needs_handler"]:
        return "needs_handler", claim["handler_reason"]
    if claim["status"] == "in_progress":
        return "in_progress", "Working claim"
    if claim["status"] == "waiting_for_sign_off":
        return "needs_handler", "Approved; waiting for handler sign-off"
    if claim["outcome"] in ("refer", "decline"):
        return (
            ("needs_handler", "Referred for business review")
            if claim["outcome"] == "refer"
            else ("done", "Decision recorded")
        )
    if claim["outcome"] == "approve" and not claim["paid"]:
        return "needs_handler", "Approved; simulated payment unresolved"
    return (
        ("done", "Decision recorded")
        if claim["outcome"]
        else ("todo", "Retry after first failed attempt")
    )


class Harness:
    def __init__(self, store: Store):
        self.store = store

    def create(self, request: Start) -> AgentRun:
        if isinstance(request, NamedStart):
            self.store.claim(request.claim_id)
        run_id = str(uuid4())
        with self.store.transaction() as connection:
            require(
                not connection.execute(
                    "SELECT 1 FROM agent_runs WHERE status = 'running'"
                ).fetchone(),
                "Another agent run is active",
            )
            scope = sorted(eligible(connection))
            cap = len(scope)
            if isinstance(request, NamedStart):
                require(request.claim_id in scope, "Claim is not eligible")
                scope, cap = [request.claim_id], 1
            elif request.max_claims is not None:
                cap = min(request.max_claims, cap)
            connection.execute(
                "INSERT INTO agent_runs "
                "(run_id, thread_id, mode, scope, max_claims, status, started_at) "
                "VALUES (?, ?, ?, ?, ?, 'running', ?)",
                (run_id, str(uuid4()), request.mode, json.dumps(scope), cap, now()),
            )
        return self.get(run_id)

    def get(self, run_id: str) -> AgentRun:
        with self.store.connect() as connection:
            row = dict(parent_row(connection, run_id))
            row["scope"] = json.loads(row["scope"])
            row["tasks"] = [
                Todo.model_validate(dict(t)) for t in task_rows(connection, run_id)
            ]
        return AgentRun.model_validate(row)

    def history(self) -> list[AgentRun]:
        with self.store.connect() as connection:
            ids = connection.execute(
                "SELECT run_id FROM agent_runs ORDER BY started_at DESC"
            ).fetchall()
        return [self.get(row["run_id"]) for row in ids]

    def plan(self, run_id: str, tasks: list[Task]) -> AgentRun:
        ids = [task.claim_id for task in tasks]
        with self.store.transaction() as connection:
            run = parent_row(connection, run_id)
            require(run["status"] == "running", "Agent run is no longer active")
            require(len(ids) == len(set(ids)), "Duplicate task")
            require(len(ids) <= run["max_claims"], "Plan exceeds claim cap")
            require(
                set(ids) <= set(json.loads(run["scope"])), "Claim is outside run scope"
            )
            sync_tasks(connection, run_id)
            previous = {t["claim_id"]: t for t in task_rows(connection, run_id)}
            admitted = {key for key, value in previous.items() if value["admitted"]}
            require(admitted <= set(ids), "Cannot remove admitted work")
            for position, task in enumerate(tasks):
                old = previous.get(task.claim_id)
                expected = old["state"] if old else "todo"
                require(task.state == expected, "Task state must match recorded work")
                connection.execute(
                    "INSERT INTO todos "
                    "(task_id, parent_run_id, claim_id, position, state) "
                    "VALUES (?, ?, ?, ?, ?) ON CONFLICT(parent_run_id, claim_id) "
                    "DO UPDATE SET position = excluded.position",
                    (str(uuid4()), run_id, task.claim_id, position, task.state),
                )
            for key in set(previous) - set(ids):
                connection.execute(
                    "DELETE FROM todos WHERE parent_run_id = ? AND claim_id = ?",
                    (run_id, key),
                )
            connection.execute(
                "UPDATE agent_runs SET checked = 0 WHERE run_id = ?", (run_id,)
            )
        return self.get(run_id)

    @staticmethod
    def admit(connection: sqlite3.Connection, run_id: str, claim_id: str) -> None:
        run = parent_row(connection, run_id)
        require(run["status"] == "running", "Agent run is no longer active")
        tasks = task_rows(connection, run_id)
        task = next((t for t in tasks if t["claim_id"] == claim_id), None)
        if task is None:
            raise HTTPException(409, "Plan this claim before delegation")
        require(claim_id in json.loads(run["scope"]), "Claim is outside run scope")
        require(
            not connection.execute(
                "SELECT 1 FROM runs WHERE status = 'running'"
            ).fetchone(),
            "Another claim attempt is active",
        )
        used = sum(t["admitted"] for t in tasks)
        require(task["admitted"] or used < run["max_claims"], "Claim cap reached")
        require(claim_id in eligible(connection), "Claim is not eligible")
        connection.execute(
            "UPDATE todos SET admitted = 1, state = 'in_progress', "
            "reason = 'Working claim' "
            "WHERE parent_run_id = ? AND claim_id = ?",
            (run_id, claim_id),
        )
        connection.execute(
            "UPDATE agent_runs SET checked = 0 WHERE run_id = ?", (run_id,)
        )

    @staticmethod
    def completion(connection: sqlite3.Connection, run_id: str) -> Completion:
        run = parent_row(connection, run_id)
        sync_tasks(connection, run_id)
        tasks = task_rows(connection, run_id)
        admitted = {t["claim_id"] for t in tasks if t["admitted"]}
        missing = {
            t["claim_id"] for t in tasks if t["state"] in ("todo", "in_progress")
        }
        if len(admitted) < run["max_claims"]:
            missing |= (set(json.loads(run["scope"])) & eligible(connection)) - admitted
        active = connection.execute(
            "SELECT claim_id FROM runs WHERE parent_run_id = ? AND status = 'running'",
            (run_id,),
        ).fetchall()
        missing |= {row["claim_id"] for row in active}
        done = sum(t["state"] == "done" for t in tasks)
        handler = sum(t["state"] == "needs_handler" for t in tasks)
        summary = (
            f"{len(admitted)} claims worked: {done} done, {handler} left for a handler."
        )
        return Completion(ready=not missing, missing=sorted(missing), summary=summary)

    def check(self, run_id: str) -> Completion:
        with self.store.transaction() as connection:
            require(
                parent_row(connection, run_id)["status"] == "running",
                "Run is not active",
            )
            result = self.completion(connection, run_id)
            connection.execute(
                "UPDATE agent_runs SET checked = ? WHERE run_id = ?",
                (result.ready, run_id),
            )
        return result

    def finish(self, run_id: str, error: str | None) -> AgentRun:
        with self.store.transaction() as connection:
            row = parent_row(connection, run_id)
            require(row["status"] == "running", "Run is no longer active")
            result = self.completion(connection, run_id)
            if error is None:
                require(
                    bool(row["checked"]) and result.ready,
                    "Completion check found missed work",
                )
            require(
                not connection.execute(
                    "SELECT 1 FROM runs WHERE parent_run_id = ? AND status = 'running'",
                    (run_id,),
                ).fetchone(),
                "Finish active claim attempts first",
            )
            connection.execute(
                "UPDATE agent_runs SET status = ?, finished_at = ?, "
                "summary = ?, error = ? "
                "WHERE run_id = ?",
                (
                    "failed" if error else "completed",
                    now(),
                    result.summary,
                    error,
                    run_id,
                ),
            )
        return self.get(run_id)

    def recover(self) -> None:
        for run in self.history():
            if run.status == "running":
                self.finish(run.run_id, "Run interrupted by backend restart.")
