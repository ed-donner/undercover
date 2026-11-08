import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.main import app
from backend.refunds import Line, work_out_refund


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "refunds.sqlite3"))
    monkeypatch.setattr(main, "run_in_background", lambda *args: None)
    with TestClient(app) as test_client:
        yield test_client


def test_refund_rules_cover_whole_order_partial_damage_pickup_fee_and_missing_item(
    client,
):
    client.post("/api/requests/REQ-7004/start")
    whole_cancel = client.post(
        "/api/requests/REQ-7004/refund",
        json={
            "reason": "cancellation",
            "lines": [{"item_id": "ITM-10004-1", "quantity": 1}],
        },
    )
    client.post("/api/requests/REQ-7002/start")
    damaged_mug = client.post(
        "/api/requests/REQ-7002/refund",
        json={
            "reason": "damaged_or_defective",
            "lines": [{"item_id": "NP-HOM-008", "quantity": 1}],
        },
    )
    client.post("/api/requests/REQ-7003/start")
    change_of_mind = client.post(
        "/api/requests/REQ-7003/refund",
        json={
            "reason": "change_of_mind",
            "lines": [{"item_id": "ITM-10003-1", "quantity": 1}],
        },
    )
    client.post("/api/requests/REQ-7007/start")
    missing_bread = client.post(
        "/api/requests/REQ-7007/refund",
        json={
            "reason": "missing_item",
            "lines": [{"item_id": "ITM-10007-1", "quantity": 1}],
        },
    )
    steps = client.get("/api/requests/REQ-7002").json()["steps"]

    assert whole_cancel.status_code == 200
    assert whole_cancel.json() == {
        "calculation": [
            {"step": "Leafy greens bundle (x1)", "amount": 129.0},
            {"step": "Delivery fee refund", "amount": 49.0},
        ],
        "refund": 178.0,
        "needs_sign_off": True,
    }
    assert damaged_mug.json() == {
        "calculation": [{"step": "Ceramic travel mug, 450 ml (x1)", "amount": 90.0}],
        "refund": 90.0,
        "needs_sign_off": True,
    }
    assert change_of_mind.json() == {
        "calculation": [
            {"step": "Glass storage jar set (x1)", "amount": 699.0},
            {"step": "Less return pickup or handling fee", "amount": -75.0},
        ],
        "refund": 624.0,
        "needs_sign_off": True,
    }
    assert missing_bread.json() == {
        "calculation": [{"step": "Wholegrain bread loaf (x1)", "amount": 99.0}],
        "refund": 99.0,
        "needs_sign_off": True,
    }
    assert steps[-1]["stage"] == "calculated_refund"
    assert steps[-1]["message"] == "Calculated eligible refund of ₹90.00."


def test_refund_recalculates_free_delivery_threshold_and_floors_at_zero():
    order = {
        "subtotal": 548,
        "delivery_fee": 0,
        "items": [
            {
                "item_id": "ITM-1",
                "sku": "SKU-1",
                "name": "Umbrella",
                "quantity": 1,
                "unit_price": 349,
                "line_total": 349,
            },
            {
                "item_id": "ITM-2",
                "sku": "SKU-2",
                "name": "Pouches",
                "quantity": 1,
                "unit_price": 199,
                "line_total": 199,
            },
        ],
    }
    partial_cancel = work_out_refund(
        order, "cancellation", [Line(item_id="ITM-1", quantity=1)]
    )
    small_order = {
        "subtotal": 50,
        "delivery_fee": 49,
        "items": [
            {
                "item_id": "ITM-3",
                "sku": "SKU-3",
                "name": "Clip",
                "quantity": 1,
                "unit_price": 50,
                "line_total": 50,
            }
        ],
    }
    floored = work_out_refund(
        small_order, "change_of_mind", [Line(item_id="ITM-3", quantity=1)]
    )

    assert partial_cancel["refund"] == 300.0
    assert partial_cancel["calculation"][-1] == {
        "step": "Less standard delivery fee after partial cancellation",
        "amount": -49.0,
    }
    assert floored["refund"] == 0.0
    assert floored["calculation"][-1] == {
        "step": "Nothing is left to refund",
        "amount": 25.0,
    }


def test_refund_endpoint_guards_missing_idle_and_unknown_items(client):
    missing = client.post(
        "/api/requests/REQ-0000/refund",
        json={
            "reason": "cancellation",
            "lines": [{"item_id": "ITM-10001-1", "quantity": 1}],
        },
    )
    idle = client.post(
        "/api/requests/REQ-7001/refund",
        json={
            "reason": "cancellation",
            "lines": [{"item_id": "ITM-10001-1", "quantity": 1}],
        },
    )
    client.post("/api/requests/REQ-7001/start")
    unknown_item = client.post(
        "/api/requests/REQ-7001/refund",
        json={
            "reason": "cancellation",
            "lines": [{"item_id": "ITM-NOPE", "quantity": 1}],
        },
    )

    assert missing.status_code == 404
    assert idle.status_code == 409
    assert unknown_item.status_code == 422
    assert "Unknown order item: ITM-NOPE" in unknown_item.json()["detail"]
