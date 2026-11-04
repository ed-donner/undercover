"""Reset the database to UnderCover's records in data/: uv run -m backend.seed"""

import json
from typing import Any

from backend.db import DATA, SCHEMA, path, transaction


def load(name: str) -> list[dict[str, Any]]:
    """Read one of the record files in data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def seed() -> dict[str, int]:
    """Replace everything in the database with the records in data/."""
    claims = load("claims.json")
    policies = load("policies.json")
    customers = load("customers.json")
    handlers = load("handlers.json")
    with transaction() as db:
        db.executescript(SCHEMA)
        db.executemany(
            "INSERT INTO claims (claim_id, record, status) VALUES (?, ?, 'waiting')",
            [(claim["claim_id"], json.dumps(claim)) for claim in claims],
        )
        db.executemany(
            "INSERT INTO policies VALUES (?, ?)",
            [(policy["policy_id"], json.dumps(policy)) for policy in policies],
        )
        db.executemany(
            "INSERT INTO customers VALUES (?, ?)",
            [(customer["customer_id"], json.dumps(customer)) for customer in customers],
        )
        db.executemany(
            "INSERT INTO handlers VALUES (?, ?)",
            [(handler["handler_id"], json.dumps(handler)) for handler in handlers],
        )
    return {
        "claims": len(claims),
        "policies": len(policies),
        "customers": len(customers),
        "handlers": len(handlers),
    }


def main() -> None:
    """Seed the database and say what went in."""
    counts = seed()
    print(
        f"Seeded {counts['claims']} claims, {counts['policies']} policies, "
        f"{counts['customers']} customers and {counts['handlers']} handlers "
        f"into {path()}"
    )


if __name__ == "__main__":
    main()
