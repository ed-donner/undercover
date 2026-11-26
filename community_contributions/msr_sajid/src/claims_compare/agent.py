"""Approach 2: an agent. A model with two tools in a loop, until it records a decision."""

import json
import time
from typing import Any

from claims_compare.prompts import claim_prompt, system_prompt

TOOLS = [
    {"type": "function", "function": {
        "name": "get_policy",
        "description": "Look up a customer's policy record by policy id.",
        "parameters": {"type": "object", "properties": {"policy_id": {"type": "string"}},
                       "required": ["policy_id"]}}},
    {"type": "function", "function": {
        "name": "record_decision",
        "description": "Record the final decision on a claim. payout is US dollars, 0 for decline or refer.",
        "parameters": {"type": "object", "properties": {
            "claim_id": {"type": "string"},
            "decision": {"type": "string", "enum": ["approve", "decline", "refer"]},
            "payout": {"type": "number"},
            "rationale": {"type": "string"}},
            "required": ["claim_id", "decision", "payout", "rationale"]}}},
]


def decide_with_agent(client: Any, model: str, claim: dict, policies: dict, wording: str,
                      max_steps: int = 6) -> dict:
    start = time.time()
    recorded: dict = {}

    def run_tool(name: str, arguments: dict) -> str:
        if name == "get_policy":
            policy = policies.get(arguments.get("policy_id"))
            return json.dumps(policy) if policy else "There is no such policy"
        if name == "record_decision":
            recorded.update(arguments)
            return f"Recorded {arguments.get('decision')} on {arguments.get('claim_id')}"
        return f"Unknown tool {name}"

    messages: list[Any] = [
        {"role": "system", "content": system_prompt(wording, with_tools=True)},
        {"role": "user", "content": claim_prompt(claim)},
    ]
    calls = 0
    for _ in range(max_steps):
        message = client.chat.completions.create(
            model=model, messages=messages, tools=TOOLS).choices[0].message
        calls += 1
        if not message.tool_calls:
            break
        messages.append(message)
        for call in message.tool_calls:
            try:
                output = run_tool(call.function.name, json.loads(call.function.arguments))
            except Exception as error:  # noqa: BLE001 - tell the model what went wrong
                output = f"The tool call failed: {error}"
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
        if recorded:  # the decision is saved; skip the closing chat message
            break
    return {
        "claim_id": claim["claim_id"],
        "decision": recorded.get("decision", "nothing recorded"),
        "payout": float(recorded.get("payout", 0.0)),
        "calls": calls,
        "seconds": round(time.time() - start, 1),
    }
