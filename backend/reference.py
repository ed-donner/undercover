"""UnderCover's records: plans, policies, customers, handlers, settings, documents."""

from typing import Any

from sqlalchemy import Column, Table, select

from backend import db, money, tables
from backend.errors import NotFound


def _one(table: Table, key: Column[Any], value: str) -> dict[str, Any]:
    """Return the row of a table whose key column has this value, or raise NotFound."""
    with db.connection() as conn:
        row = conn.execute(select(table).where(key == value)).one_or_none()
    if row is None:
        raise NotFound(f"No {table.name} record {value}")
    return dict(row._mapping)


def company_setting(key: str) -> Any:
    """Return a company setting, with any money in it as `Decimal` dollars."""
    value = _one(tables.settings, tables.settings.c.key, key)["value"]
    return money.convert({key: value})[key]


def plan(name: str) -> dict[str, Any]:
    """Return a plan with its limits as `Decimal` dollars."""
    return money.dollar_fields(_one(tables.plans, tables.plans.c.plan, name))


def add_on(name: str) -> dict[str, Any]:
    """Return an add-on, with only the fields it has."""
    row = money.dollar_fields(_one(tables.add_ons, tables.add_ons.c.add_on, name))
    return {key: value for key, value in row.items() if value is not None}


def deductible_benefits() -> list[str]:
    """List the benefits the plan's deductible applies to."""
    with db.connection() as conn:
        rows = conn.execute(select(tables.deductible_benefits.c.benefit))
        return [benefit for (benefit,) in rows]


def policy(policy_id: str) -> dict[str, Any]:
    """Return a policy."""
    return _one(tables.policies, tables.policies.c.policy_id, policy_id)


def customer(customer_id: str) -> dict[str, Any]:
    """Return a customer, with their previous claims."""
    return _one(tables.customers, tables.customers.c.customer_id, customer_id)


def handlers() -> list[dict[str, Any]]:
    """List every claims handler."""
    with db.connection() as conn:
        rows = conn.execute(
            select(tables.handlers).order_by(tables.handlers.c.handler_id)
        )
        return [dict(row._mapping) for row in rows]


def handler(handler_id: str) -> dict[str, Any] | None:
    """Return the handler with this id, or None."""
    return next((h for h in handlers() if h["handler_id"] == handler_id), None)


def sections(document: str) -> dict[str, str]:
    """Return a document's sections by heading, in order, or raise NotFound."""
    with db.connection() as conn:
        rows = conn.execute(
            select(tables.document_sections.c.heading, tables.document_sections.c.text)
            .where(tables.document_sections.c.document == document)
            .order_by(tables.document_sections.c.position)
        )
        found = {heading: text for heading, text in rows}
    if not found:
        raise NotFound(f"No document {document}")
    return found


def section(document: str, heading: str) -> str:
    """Return one section's text, or raise NotFound."""
    found = sections(document)
    if heading not in found:
        raise NotFound(f"No section {heading}")
    return found[heading]
