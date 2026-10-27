# Week 2 Day 3 - Rejecting a payout

Let a handler reject a payout at the approval step, with a note that goes back to the agent so it can look at the claim again. Tried on CLM-1011, a lost suitcase where the correct payout is $1,150.

## What I changed

1. **`ClaimState`** has a new field, `approved: bool`.
2. **The `approval` node** reads the handler's answer (`handler`, `approved`, `note`). On an approval it records the handler. On a rejection it adds the note to the conversation as a message.
3. **A new edge, `after_approval`**, goes to `pay` if the payout is approved and back to `agent` if it's rejected.

```python
def approval(state: ClaimState):
    """Wait for a handler to approve or reject a payout over the limit."""
    print(f"{state['claim_id']} needs a handler to approve ${state['payout']:,.2f}")
    answer = interrupt({"claim_id": state["claim_id"], "payout": state["payout"], "rationale": state["rationale"]})
    if answer["approved"]:
        return {"approved": True, "approved_by": answer["handler"]}
    return {"approved": False, "messages": [HumanMessage(answer["note"])]}


def after_approval(state: ClaimState):
    """Pay an approved payout, or send a rejected payout back to the agent."""
    if state["approved"]:
        return "pay"
    return "agent"


builder.add_conditional_edges("approval", after_approval, ["pay", "agent"])
```

## The result on CLM-1011

The agent first came to **$1,370**. It capped the suit at the $300 per-item limit but left the camera and lens at $520, when section 5 counts them as one item.

The handler rejected it with this note:

> The camera body and its lens count as one item under section 5, so the $300 per-item limit applies to them together. Please work out the payout again.

The agent worked the payout out again and came to **$1,150**, which is correct. That's still over the $1,000 limit, so it paused for approval again.

| Step            | Payout | Handler                 |
| --------------- | ------ | ----------------------- |
| First decision  | $1,370 | Rejected, with the note |
| Second decision | $1,150 | Waiting for approval    |
