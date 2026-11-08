import pytest

from backend import payouts

POLICY = "POL-2001"


def line(description, amount, kind="item", quantity=1, **extra):
    return {
        "description": description,
        "amount": amount,
        "kind": kind,
        "quantity": quantity,
        "nights": 0,
        "hours": 0,
        **extra,
    }


def payout(client, benefit, lines, paid_by_others="0.00", policy_id=POLICY):
    response = client.post(
        "/api/payouts",
        json={
            "policy_id": policy_id,
            "benefit": benefit,
            "lines": lines,
            "paid_by_others": paid_by_others,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_baggage_applies_limit_others_and_deductible(client):
    result = payout(
        client,
        "baggage",
        [line("Suitcase", "239.99"), line("T-shirts", "74.97", quantity=3)],
        paid_by_others="100.00",
    )
    assert isinstance(result["payout"], str)
    assert result["payout"].count(".") == 1
    assert [s["step"] for s in result["calculation"]][-2:] == [
        "Less what others have paid or refunded",
        "Less the deductible",
    ]
    assert result["needs_sign_off"] is False


def test_cash_is_capped_at_100(client):
    result = payout(client, "passport", [line("Cash", "400.00", kind="cash")])
    assert result["calculation"][0]["amount"] == "100.00"


def test_hotel_and_meals_have_their_own_limits(client):
    lines = [
        line("Hotel", "900.00", kind="hotel", nights=2),
        line("Meals", "500.00", kind="meals_without_receipts", hours=30),
    ]
    steps = payout(client, "trip_delay", lines)["calculation"]
    assert steps[0]["step"].endswith("limited to $700.00")
    assert steps[1]["step"].endswith("limited to $70.00")


def test_nothing_left_pays_zero(client):
    result = payout(client, "baggage", [line("Scarf", "50.00")], "500.00")
    assert result["payout"] == "0.00"


def test_over_the_maximum_is_capped(client):
    result = payout(
        client, "baggage_delay", [line("Clothes", "9000.00", kind="expense")]
    )
    assert result["calculation"][-1]["step"].startswith("Less the amount over")


@pytest.mark.parametrize(
    ("amount", "expected"), [("1000.00", False), ("1000.01", True)]
)
def test_sign_off_limit_comes_from_the_settings(amount, expected):
    assert payouts.needs_sign_off(payouts.money.dollars(amount)) is expected
