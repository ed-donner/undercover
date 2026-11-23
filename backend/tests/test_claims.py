def test_list_claims(client):
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert claims[0]["claim_id"] == "CLM-1001"
    assert claims[0]["customer_name"] == "Maya Patel"
    assert {claim["state"] for claim in claims} == {"waiting"}


def test_get_claim(client):
    detail = client.get("/api/claims/CLM-1001").json()
    assert detail["claim"]["amount_claimed"] == 420.0
    assert len(detail["claim"]["items"]) == 3
    assert detail["policy"]["plan"] == "premium"
    assert detail["plan"]["deductible"] == 50.0
    assert detail["state"] == "waiting"


def test_context_leaves_out_contact_details(client):
    response = client.get("/api/claims/CLM-1001/context")
    text = response.text
    for private in ("email", "phone", "date_of_birth", "address"):
        assert private not in text
    customer = response.json()["customer"]
    assert customer["name"] == "Maya Patel"
    assert customer["previous_claims"][0]["claim_id"] == "CLM-0412"


def test_unknown_claim_is_not_found(client):
    assert client.get("/api/claims/CLM-0000").status_code == 404
    assert client.get("/api/claims/CLM-0000/context").status_code == 404


def test_policy_wording(client):
    text = client.get("/api/policy-wording").json()["text"]
    assert text.startswith("# UnderCover Travel Insurance: Policy Wording")


def test_handlers(client):
    handlers = client.get("/api/handlers").json()
    assert [handler["handler_id"] for handler in handlers] == [
        "HND-01",
        "HND-02",
        "HND-03",
    ]


def test_every_operation_has_an_id_and_no_optional_input(client):
    schema = client.get("/openapi.json").json()
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            assert operation.get("operationId"), f"{method} {path}"
            assert operation.get("summary") or operation.get("description")
            for parameter in operation.get("parameters", []):
                assert parameter["required"], f"{method} {path}"
