from decimal import Decimal

from agent import agents, api


def test_decide_claim_reads_then_decides(backend, script):
    llm = script(
        ("get_claim", {}),
        ("list_sections", {"document": "policy_wording"}),
        ("read_section", {"document": "policy_wording", "heading": "3. Trip Delay"}),
        ("list_sections", {"document": "claims_manual"}),
        ("read_section", {"document": "claims_manual", "heading": "9. Repeat claims"}),
        (
            "decide_claim",
            {
                "decision": "approve",
                "payout": "420.00",
                "reason": "Routine trip delay with receipts.",
                "policy_reference": "Section 3",
            },
        ),
        "Approved the claim for $420.00.",
    )

    assert agents.decide_claim("CLM-1001", llm) == "Approved the claim for $420.00."

    claim = api.get_claim("CLM-1001")
    assert claim["status"] == "decided"
    assert claim["decision"] == "approve"
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert [step["text"] for step in steps] == [
        "Read the claim, its policy and the customer's claim history",
        "Read policy wording section: 3. Trip Delay",
        "Read claims manual section: 9. Repeat claims",
        "Decided: approve for $420.00",
    ]


def test_run_queue_works_only_the_capped_claims(monkeypatch, backend, script):
    def fake_decide(claim_id):
        api.decide_claim(
            claim_id, "approve", Decimal("100.00"), "Stubbed.", "Section 1"
        )
        return f"Approved {claim_id}."

    monkeypatch.setattr(agents, "decide_claim", fake_decide)
    first, second, other = (c["claim_id"] for c in api.list_claims()[:3])
    llm = script(
        ("get_to_do", {}),
        ("work_claim", {"claim_id": first}),
        ("work_claim", {"claim_id": second}),
        ("finish_run", {"summary": "Worked 2 claims."}),
        "Done. Worked 2 claims.",
    )

    assert agents.run_queue(cap=2, llm=llm) == "Done. Worked 2 claims."

    run = api.get_current_run()
    assert run["summary"] == "Worked 2 claims."
    assert run["finished_on"] is not None
    assert {i["claim_id"] for i in run["items"]} == {first, second}
    assert all(i["status"] == "done" for i in run["items"])
    statuses = {c["claim_id"]: c["status"] for c in api.list_claims()}
    assert statuses[first] == statuses[second] == "decided"
    assert statuses[other] == "waiting"


def test_finish_run_is_refused_while_a_claim_is_outstanding(monkeypatch, script):
    monkeypatch.setattr(
        agents, "decide_claim", lambda claim_id: f"Approved {claim_id}."
    )
    first = api.list_claims()[0]["claim_id"]
    llm = script(
        ("finish_run", {"summary": "Too early."}),
        ("work_claim", {"claim_id": first}),
        ("finish_run", {"summary": "Worked it."}),
        "Done.",
    )

    agents.run_queue(cap=1, llm=llm)

    run = api.get_current_run()
    assert run["summary"] == "Worked it."
    assert run["items"][0]["attempts"] == 1


def test_payout_comes_from_the_payout_tool(backend, script):
    line = {"description": "Hotel", "amount": "900.00", "kind": "hotel", "nights": 2}
    llm = script(
        ("get_claim", {}),
        (
            "calculate_payout",
            {
                "policy_id": "POL-2001",
                "benefit": "trip_delay",
                "lines": [line],
                "paid_by_others": "0.00",
            },
        ),
        (
            "decide_claim",
            {
                "decision": "approve",
                "payout": "700.00",
                "reason": "Hotel limited to two nights.",
                "policy_reference": "Section 10",
            },
        ),
        "Approved.",
    )

    agents.decide_claim("CLM-1001", llm)

    assert api.get_claim("CLM-1001")["payout"] == "700.00"
    assert (
        api.calculate_payout("POL-2001", "trip_delay", [api.Line(**line)], Decimal(0))[
            "payout"
        ]
        == "700.00"
    )
