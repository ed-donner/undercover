"""The starting records: reads `data/` into rows for the tables."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import Table

from backend import money, tables

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOCUMENTS = {"policy_wording": "policy_wording.md", "claims_manual": "claims_manual.md"}


def _load_json(name: str) -> Any:
    text = (DATA_DIR / name).read_text()
    return money.convert(json.loads(text, parse_float=Decimal))


def _sections(text: str) -> list[tuple[str, str]]:
    """Split a Markdown document into its ``##``-headed sections, in order."""
    sections: list[tuple[str, str]] = []
    heading: str | None = None
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if heading is not None:
                sections.append((heading, "\n".join(lines).strip()))
            heading, lines = line.removeprefix("## ").strip(), []
        elif heading is not None:
            lines.append(line)
    if heading is not None:
        sections.append((heading, "\n".join(lines).strip()))
    return sections


def _document_rows() -> list[dict[str, Any]]:
    return [
        {"document": document, "position": position, "heading": heading, "text": text}
        for document, filename in DOCUMENTS.items()
        for position, (heading, text) in enumerate(
            _sections((DATA_DIR / filename).read_text())
        )
    ]


def _claim_row(claim: dict[str, Any]) -> dict[str, Any]:
    row = money.cents_columns({k: v for k, v in claim.items() if k != "status"})
    return {**row, "status": "waiting"}


def records() -> dict[Table, list[dict[str, Any]]]:
    """Return every table's starting rows."""
    plan_data = _load_json("plans.json")
    return {
        tables.settings: [
            {"key": key, "value": value}
            for key, value in _load_json("company.json").items()
        ],
        tables.plans: [money.cents_columns(plan) for plan in plan_data["plans"]],
        tables.add_ons: plan_data["add_ons"],
        tables.deductible_benefits: [
            {"benefit": benefit} for benefit in plan_data["deductible_applies_to"]
        ],
        tables.policies: _load_json("policies.json"),
        tables.customers: _load_json("customers.json"),
        tables.handlers: _load_json("handlers.json"),
        tables.document_sections: _document_rows(),
        tables.claims: [_claim_row(claim) for claim in _load_json("claims.json")],
    }
