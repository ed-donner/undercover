import json

import httpx
import pytest

from agent.api import BackendAPI


@pytest.mark.parametrize(
    ("operation", "method", "path", "body"),
    [
        (
            lambda api: api.claim("claim/one ?"),
            "GET",
            "/api/claims/claim%2Fone%20%3F",
            None,
        ),
        (
            lambda api: api.read_section("claim/one", "attempt", "manual", 4),
            "POST",
            "/api/claims/claim%2Fone/reads",
            {"run_id": "attempt", "document_id": "manual", "section": 4},
        ),
        (
            lambda api: api.write_todos(
                "run/one", [{"claim_id": "claim", "state": "todo"}]
            ),
            "PUT",
            "/api/agent-runs/run%2Fone/tasks",
            {"tasks": [{"claim_id": "claim", "state": "todo"}]},
        ),
        (
            lambda api: api.record_decision(
                "claim", "trusted-attempt", {"run_id": "untrusted", "outcome": "refer"}
            ),
            "POST",
            "/api/claims/claim/decision",
            {"run_id": "trusted-attempt", "outcome": "refer"},
        ),
        (
            lambda api: api.finish_run("run/one"),
            "POST",
            "/api/agent-runs/run%2Fone/finish",
            {"error": None},
        ),
    ],
)
def test_named_operations_encode_identifiers_and_send_contracts(
    operation, method, path, body
):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(
        base_url="http://test", transport=httpx.MockTransport(handler)
    ) as client:
        assert operation(BackendAPI(client)) == {"ok": True}
    assert len(seen) == 1
    request = seen[0]
    assert request.method == method
    assert request.url.raw_path.decode() == path
    assert (json.loads(request.content) if request.content else None) == body


@pytest.mark.parametrize("status", [409, 422, 503])
def test_payment_conflicts_are_results_but_other_errors_propagate(status):
    def handler(request):
        return httpx.Response(status, json={"detail": "Payment rejected"})

    with httpx.Client(
        base_url="http://test", transport=httpx.MockTransport(handler)
    ) as client:
        api = BackendAPI(client)
        if status == 409:
            assert api.pay("claim", "attempt", "1.00") == {
                "paid": False,
                "reason": "Payment rejected",
            }
        else:
            with pytest.raises(httpx.HTTPStatusError) as error:
                api.pay("claim", "attempt", "1.00")
            assert error.value.response.status_code == status
