"""Additive local schema changes preserve the pilot's financial history."""

import sqlite3


def add_column(connection: sqlite3.Connection, table: str, definition: str) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if definition.split(maxsplit=1)[0] not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def migrate(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS agent_runs (
            run_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL UNIQUE,
            mode TEXT NOT NULL, scope TEXT NOT NULL, max_claims INTEGER NOT NULL,
            status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
            summary TEXT NOT NULL DEFAULT '', error TEXT,
            checked INTEGER NOT NULL DEFAULT 0
        );
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_agent
            ON agent_runs(status) WHERE status = 'running';
        CREATE TABLE IF NOT EXISTS todos (
            task_id TEXT PRIMARY KEY,
            parent_run_id TEXT NOT NULL REFERENCES agent_runs(run_id),
            claim_id TEXT NOT NULL REFERENCES claims(id), position INTEGER NOT NULL,
            state TEXT NOT NULL, admitted INTEGER NOT NULL DEFAULT 0,
            reason TEXT NOT NULL DEFAULT '', UNIQUE(parent_run_id, claim_id)
        );
        CREATE TABLE IF NOT EXISTS document_sections (
            document_id TEXT NOT NULL, version TEXT NOT NULL, section INTEGER NOT NULL,
            title TEXT NOT NULL, text TEXT NOT NULL,
            PRIMARY KEY(document_id, section)
        );
        CREATE TABLE IF NOT EXISTS document_reads (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL REFERENCES runs(run_id),
            claim_id TEXT NOT NULL REFERENCES claims(id),
            document_id TEXT NOT NULL, version TEXT NOT NULL, section INTEGER NOT NULL,
            title TEXT NOT NULL, text TEXT NOT NULL, read_at TEXT NOT NULL
        );
    """)
    add_column(connection, "runs", "parent_run_id TEXT REFERENCES agent_runs(run_id)")
    add_column(connection, "runs", "deadline TEXT")
    add_column(connection, "claims", "failures INTEGER NOT NULL DEFAULT 0")
    add_column(connection, "claims", "needs_handler INTEGER NOT NULL DEFAULT 0")
    add_column(connection, "claims", "handler_reason TEXT NOT NULL DEFAULT ''")
    add_column(connection, "decisions", "manual_version TEXT")
    add_column(connection, "decisions", "manual_sections TEXT NOT NULL DEFAULT '[]'")
