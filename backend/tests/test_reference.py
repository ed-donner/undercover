import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend import money, reference
from backend.errors import NotFound

DATA = Path(__file__).resolve().parents[2] / "data"


def from_file(name):
    return money.convert(json.loads((DATA / name).read_text(), parse_float=Decimal))


@pytest.fixture(autouse=True)
def fresh_database(client):
    """Each test reads from a new database."""


def test_policies_and_customers_match_their_files():
    for record in from_file("policies.json"):
        assert reference.policy(record["policy_id"]) == record
    for record in from_file("customers.json"):
        assert reference.customer(record["customer_id"]) == record


def test_handlers_match_their_file():
    assert reference.handlers() == from_file("handlers.json")
    marcus = reference.handler("HND-02")
    assert marcus
    assert marcus["name"] == "Marcus Oyelaran"
    assert reference.handler("HND-99") is None


def test_plans_and_add_ons_match_their_file():
    file = from_file("plans.json")
    for plan in file["plans"]:
        assert reference.plan(plan["plan"]) == plan
    for add_on in file["add_ons"]:
        assert reference.add_on(add_on["add_on"]) == add_on
    assert sorted(reference.deductible_benefits()) == sorted(
        file["deductible_applies_to"]
    )


def test_company_settings_match_their_file():
    for key, value in from_file("company.json").items():
        assert reference.company_setting(key) == value
    assert reference.company_setting("payout_approval_limit") == Decimal("1000.00")


def test_sections_come_in_the_order_of_the_document():
    headings = list(reference.sections("policy_wording"))
    text = (DATA / "policy_wording.md").read_text()
    in_file = [
        line.removeprefix("## ").strip()
        for line in text.splitlines()
        if line.startswith("## ")
    ]
    assert headings == in_file
    assert "Trip Delay" in " ".join(
        headings + list(reference.sections("claims_manual"))
    )
    assert reference.section("policy_wording", headings[0])


@pytest.mark.parametrize(
    "lookup",
    [
        lambda: reference.policy("POL-9999"),
        lambda: reference.customer("CUS-9999"),
        lambda: reference.plan("gold"),
        lambda: reference.add_on("jetpack"),
        lambda: reference.company_setting("nothing"),
        lambda: reference.sections("diary"),
        lambda: reference.section("policy_wording", "Nothing"),
    ],
)
def test_a_missing_record_raises_not_found(lookup):
    with pytest.raises(NotFound):
        lookup()
