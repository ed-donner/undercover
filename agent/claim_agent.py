"""The claim agent: a fresh agent that decides one claim."""

from typing import Literal

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, ToolCall, ToolMessage
from langchain_core.tools import tool

from agent import harness
from agent.harness import failure, reply, request

RESULT_LIMIT = 400
CALL_LIMIT = 30
OUTCOMES = {"decline": "declined", "refer": "referred"}
DOCUMENTS = {"wording": "Policy wording", "manual": "Claims manual"}


def text_of(path: str) -> str:
    response = request("GET", path)
    return response.json()["text"] if response.is_success else failure(response)


@tool
def get_claim(claim_id: str) -> str:
    """Get a claim: the story, items, documents and where it stands."""
    return reply("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> str:
    """Get a policy: the plan, add-ons, trip dates and travelers."""
    return reply("GET", f"/api/policies/{policy_id}")


@tool
def get_customer(customer_id: str) -> str:
    """Get a customer's name and claim history."""
    return reply("GET", f"/api/customers/{customer_id}")


@tool
def list_sections(document: Literal["wording", "manual"]) -> str:
    """List the numbered sections of the policy wording or of the claims manual."""
    response = request("GET", f"/api/documents/{document}/sections")
    if not response.is_success:
        return failure(response)
    return "\n".join(f"{s['number']}. {s['title']}" for s in response.json())


@tool
def read_section(document: Literal["wording", "manual"], section: int) -> str:
    """Read one numbered section of the policy wording or of the claims manual."""
    return text_of(f"/api/documents/{document}/sections/{section}")


@tool
def record_decision(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    explanation: str,
    policy_section: str,
) -> str:
    """Record the decision on a claim.

    The payout is 0 unless approving. The explanation is two or three sentences,
    and the policy section names the part of the wording that settles it.
    """
    body = {
        "decision": decision,
        "payout": payout,
        "explanation": explanation,
        "policy_section": policy_section,
    }
    return reply("POST", f"/api/claims/{claim_id}/decision", body)


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim of $1,000 or less the amount of its payout."""
    return reply("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})


TOOLS = [
    get_claim,
    get_policy,
    get_customer,
    list_sections,
    read_section,
    record_decision,
    pay_claim,
]


def add_step(claim_id: str, kind: str, text: str) -> None:
    request("POST", f"/api/claims/{claim_id}/steps", {"kind": kind, "text": text})


def read_text(call: ToolCall, result: str) -> str | None:
    """Describe a section the agent read, such as 'Claims manual, 9. Repeat claims'."""
    if call["name"] != "read_section" or result.startswith("Error"):
        return None
    heading = result.splitlines()[0].lstrip("# ")
    return f"{DOCUMENTS[call['args']['document']]}, {heading}"


def recorder(claim_id: str):
    """Return a function that adds what each message shows the agent doing."""
    calls: dict[str, ToolCall] = {}

    def record(message: AnyMessage) -> None:
        if isinstance(message, ToolMessage):
            add_step(
                claim_id,
                "tool_result",
                f"{message.name}: {message.text[:RESULT_LIMIT]}",
            )
            read = read_text(calls[message.tool_call_id], message.text)
            if read:
                add_step(claim_id, "read", read)
        elif isinstance(message, AIMessage):
            for call in message.tool_calls:
                calls[call["id"] or ""] = call
                add_step(claim_id, "tool_call", f"{call['name']}({call['args']})")
            if message.text:
                add_step(claim_id, "message", message.text)

    return record


def claim_run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run a fresh agent on one claim that is in progress and return its reply."""
    instructions = request("GET", "/api/instructions").json()["claim"]
    agent = create_agent(
        llm or harness.model(),
        tools=TOOLS,
        system_prompt=instructions,
        middleware=harness.middleware(CALL_LIMIT),
    )
    try:
        return harness.stream(agent, f"Claim {claim_id}", thread_id, recorder(claim_id))
    except Exception as error:
        add_step(claim_id, "error", f"{type(error).__name__}: {error}")
        raise


def report(claim_id: str, problem: str | None = None) -> str:
    """Say in one line where a claim stands, from the backend's record."""
    claim = request("GET", f"/api/claims/{claim_id}").json()
    status, decision = claim["status"], claim["decision"]
    if status == "waiting_for_sign_off":
        return f"{claim_id}: approved ${decision['payout']:,.2f}, waiting for sign-off."
    if status == "decided" and decision["decision"] == "approve":
        paid = "paid" if claim["payment"] else "not paid"
        return f"{claim_id}: approved ${decision['payout']:,.2f}, {paid}."
    if status == "decided":
        return f"{claim_id}: {OUTCOMES[decision['decision']]}."
    if status == "needs_handler":
        return f"{claim_id}: failed twice ({problem}), left for a handler."
    return f"{claim_id}: failed ({problem}), back in the queue."


def work(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the claim agent on a claim in progress and always leave it in a good state.

    A claim that fails before a decision goes back in the queue, or to a handler on
    the second failure. A decided claim is never reset; an approved payout of $1,000
    or less that was left unpaid is paid.
    """
    problem = None
    try:
        claim_run(claim_id, thread_id, llm)
    except Exception as error:
        problem = f"{type(error).__name__}: {error}"
    claim = request("GET", f"/api/claims/{claim_id}").json()
    if claim["status"] == "in_progress":
        problem = problem or "the agent finished without a decision"
        request("POST", f"/api/claims/{claim_id}/fail", {"reason": problem})
    elif claim["status"] == "decided" and claim["decision"]["decision"] == "approve":
        if not claim["payment"]:
            payout = claim["decision"]["payout"]
            request("POST", f"/api/claims/{claim_id}/payment", {"amount": payout})
    return report(claim_id, problem)
