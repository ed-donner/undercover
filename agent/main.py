"""The UnderCover Agent."""

import json
import os
from typing import Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
MAX_RESULT_STEP = 600


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, **kwargs) -> str:
    """Call the backend and return its answer as text, with a refusal in words."""
    with backend() as client:
        response = client.request(method, path, **kwargs)
    if response.is_error:
        return f"Refused: {response.json()['detail']}"
    return response.text


@tool
def get_claim_context(claim_id: str) -> str:
    """Get a claim with its policy, plan limits and the customer's claim history."""
    return call("GET", f"/api/claims/{claim_id}/context")


@tool
def get_policy_wording() -> str:
    """Get the text of the policy wording, the contract that decides every claim."""
    return json.loads(call("GET", "/api/policy-wording"))["text"]


@tool
def record_decision(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    explanation: str,
    policy_section: str,
) -> str:
    """Record the decision on a claim. The payout is zero unless you approve."""
    body = {
        "decision": decision,
        "payout": payout,
        "explanation": explanation,
        "policy_section": policy_section,
    }
    return call("POST", f"/api/claims/{claim_id}/decision", json=body)


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim its payout. A payout over the limit waits for sign-off."""
    return call("POST", f"/api/claims/{claim_id}/payment", json={"amount": amount})


TOOLS = [get_claim_context, get_policy_wording, record_decision, pay_claim]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def instructions() -> str:
    """Fetch the agent's instructions from the backend."""
    return json.loads(call("GET", "/api/instructions"))["text"]


def record_step(claim_id: str, kind: str, text: str):
    """Tell the backend about one step of the work."""
    call("POST", f"/api/claims/{claim_id}/steps", json={"kind": kind, "text": text})


def record_message(claim_id: str, message: BaseMessage) -> str:
    """Record a message as steps, and return its text if it ends the work."""
    if isinstance(message, ToolMessage):
        text = message.text
        if len(text) > MAX_RESULT_STEP:
            text = text[:MAX_RESULT_STEP] + " ..."
        record_step(claim_id, "tool_result", text)
    elif isinstance(message, AIMessage):
        if message.text:
            record_step(claim_id, "message", message.text)
        for tool_call in message.tool_calls:
            args = json.dumps(tool_call["args"])
            record_step(claim_id, "tool_call", f"{tool_call['name']}({args})")
        if not message.tool_calls:
            return message.text
    return ""


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim, recording its steps, and return its final reply."""
    agent = create_agent(llm or model(), tools=TOOLS, system_prompt=instructions())
    reply = ""
    for update in agent.stream(
        {"messages": [{"role": "user", "content": f"Claim {claim_id}"}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    ):
        for state in update.values():
            for message in state["messages"]:
                reply = record_message(claim_id, message) or reply
    return reply
