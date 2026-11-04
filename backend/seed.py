"""Reset the database from the business data. Run with `uv run -m backend.seed`."""

import json

from backend.db import TABLES, connect, load_json

RECORDS = [
    ("claims", "claim_id", "claims.json"),
    ("policies", "policy_id", "policies.json"),
    ("customers", "customer_id", "customers.json"),
]


def seed() -> int:
    """Empty the database and load the claims, policies and customers."""
    with connect() as conn:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table}")  # noqa: S608
        conn.execute("DELETE FROM sqlite_sequence")
        for table, key, file in RECORDS:
            for record in load_json(file):
                conn.execute(
                    f"INSERT INTO {table} ({key}, data) VALUES (?, ?)",  # noqa: S608
                    (record[key], json.dumps(record)),
                )
        return conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]


if __name__ == "__main__":
    print(f"Seeded {seed()} claims, all waiting.")  # noqa: T201
