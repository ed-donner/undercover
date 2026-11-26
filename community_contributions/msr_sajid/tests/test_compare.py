import json
from types import SimpleNamespace

from claims_compare.agent import decide_with_agent
from claims_compare.data import load_claims, load_labels, load_policies, load_wording
from claims_compare.prompts import ClaimDecision, claim_prompt
from claims_compare.scoring import is_right, summarize
from claims_compare.single import decide_single

CLAIM = {"claim_id": "C-001", "policy_id": "P-1"}


def tool_reply(name, args, call_id="t1"):
    call = SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(args)))
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[call]))])


def text_reply(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=None))])


class FakeClient:
    def __init__(self, replies=(), parsed=None):
        self._replies = iter(replies)
        completions = SimpleNamespace(create=lambda **_: next(self._replies), parse=lambda **_: parsed)
        self.chat = SimpleNamespace(completions=completions)


def test_data_is_consistent():
    claims, labels, policies = load_claims(), load_labels(), load_policies()
    assert {c["claim_id"] for c in claims} == set(labels)
    assert all(c["policy_id"] in policies for c in claims)
    assert "Per-item limit" in load_wording()


def test_scoring_allows_a_dollar_of_slack():
    label = {"decision": "approve", "payout": 250.0}
    assert is_right({"decision": "approve", "payout": 249.5}, label)
    assert not is_right({"decision": "approve", "payout": 300.0}, label)
    assert not is_right({"decision": "refer", "payout": 250.0}, label)


def test_single_call_returns_the_parsed_decision():
    parsed = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        parsed=ClaimDecision(rationale="r", decision="approve", payout=250)))])
    out = decide_single(FakeClient(parsed=parsed), "m", CLAIM, {}, "wording")
    assert (out["decision"], out["payout"], out["calls"]) == ("approve", 250, 1)


def test_agent_looks_up_policy_then_records():
    record = {"claim_id": "C-001", "decision": "approve", "payout": 250, "rationale": "r"}
    client = FakeClient([tool_reply("get_policy", {"policy_id": "P-1"}),
                         tool_reply("record_decision", record, "t2")])
    out = decide_with_agent(client, "m", CLAIM, load_policies(), "wording")
    assert (out["decision"], out["payout"], out["calls"]) == ("approve", 250.0, 2)


def test_agent_that_never_records_counts_as_nothing_recorded():
    out = decide_with_agent(FakeClient([text_reply("I give up")]), "m", CLAIM, {}, "w")
    assert out["decision"] == "nothing recorded"


def test_agent_survives_a_bad_tool_call():
    bad = SimpleNamespace(id="t1", function=SimpleNamespace(name="get_policy", arguments="not json"))
    first = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[bad]))])
    out = decide_with_agent(FakeClient([first, text_reply("done")]), "m", CLAIM, {}, "w")
    assert out["calls"] == 2


def test_summary_counts_right_answers():
    labels = {"C-001": {"decision": "approve", "payout": 250.0}}
    results = [{"claim_id": "C-001", "decision": "approve", "payout": 250.0, "calls": 2, "seconds": 3.0}]
    assert summarize("agent", results, labels)["accuracy"] == "1 / 1"


def test_policy_record_only_goes_in_the_single_prompt():
    assert "Policy record" in claim_prompt(CLAIM, {"policy_id": "P-1"})
    assert "Policy record" not in claim_prompt(CLAIM)
