"""Approach 1: one structured-output call per claim."""

import time
from typing import Any

from claims_compare.prompts import ClaimDecision, claim_prompt, system_prompt


def decide_single(client: Any, model: str, claim: dict, policy: dict, wording: str) -> dict:
    start = time.time()
    response = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt(wording)},
            {"role": "user", "content": claim_prompt(claim, policy)},
        ],
        response_format=ClaimDecision,
        extra_body={"provider": {"require_parameters": True}},
    )
    answer = response.choices[0].message.parsed
    return {
        "claim_id": claim["claim_id"],
        "decision": answer.decision,
        "payout": answer.payout,
        "calls": 1,
        "seconds": round(time.time() - start, 1),
    }
