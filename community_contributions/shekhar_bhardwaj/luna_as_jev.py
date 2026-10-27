import json
import os
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

INSTRUCTIONS = """You are a claims handler at UnderCover Travel Insurance.
Decide the claim you are given, using the policy wording below and the
customer's policy record.

Choose one decision:
- approve: the wording covers the claim and the required documents are
  attached. Work out the payout using section 10.
- decline: the wording does not cover the claim.
- refer: a colleague needs to look at it, because a required document is
  missing, or the story and the documents disagree, or the wording does not
  settle the question.
"""


# loading openrouter keys
load_dotenv(override=True)
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

if openrouter_api_key:
    print("OpenRouter API key found")
else:
    print("No OpenRouter API key found. Add OPENROUTER_API_KEY to the .env file")

openrouter = OpenAI(
    base_url=OPENROUTER_BASE_URL, api_key=openrouter_api_key, timeout=120, max_retries=5
)


# loading data
DATA = Path(__file__).resolve().parents[2] / "data"


def load(name):
    """Read one of the JSON seed files."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def get_sample_data(tiny=False, held_out=False):
    """Return a list of claims, and the handlers' decisions on them keyed by claim id.

    held_out=True gives the twenty-five held-out claims in place of the queue.
    tiny=True keeps the five claims marked for the tiny version of either set.
    """
    claims = load("evals/held_out_claims.json" if held_out else "claims.json")
    decisions = load(
        "evals/held_out_decisions.json" if held_out else "evals/decisions.json"
    )
    if tiny:
        chosen = {decision["claim_id"] for decision in decisions if decision["tiny"]}
        claims = [claim for claim in claims if claim["claim_id"] in chosen]
        decisions = [decision for decision in decisions if decision["tiny"]]
    labels = {decision["claim_id"]: decision for decision in decisions}
    return claims, labels


TINY = False

claims, labels = get_sample_data(tiny=TINY)
policies = {policy["policy_id"]: policy for policy in load("policies.json")}
policy_wording = (DATA / "policy_wording.md").read_text(encoding="utf-8")


class ConfidenceScores(BaseModel):
    approve: float = Field(
        ge=0, le=1, description="Confidence that the claim should be approved"
    )
    decline: float = Field(
        ge=0, le=1, description="Confidence that the claim should be declined"
    )
    refer: float = Field(
        ge=0, le=1, description="Confidence that the claim should be referred"
    )


class ClaimDecision(BaseModel):
    decision: Literal["approve", "decline", "refer"]
    confidence: ConfidenceScores


SYSTEM_PROMPT = f"""{INSTRUCTIONS}
{policy_wording}
"""


def make_user_prompt(claim):
    """The customer's policy record and the claim, as JSON."""
    policy = policies[claim["policy_id"]]
    return f"""# Policy record

{json.dumps(policy, indent=2)}

# Claim

{json.dumps(claim, indent=2)}
"""


def make_messages(claim):
    """Build the messages for one claim: the task and the wording, then the
    policy record and the claim."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": make_user_prompt(claim)},
    ]


def decide(claim, model, effort):
    """Ask one model to decide one claim."""
    start = time.time()
    response = openrouter.chat.completions.parse(
        model=model,
        messages=make_messages(claim),
        response_format=ClaimDecision,
        reasoning_effort=effort,
        extra_body={"provider": {"require_parameters": True}},
    )
    answer = response.choices[0].message.parsed
    print(answer)
    return {
        "model": model,
        "effort": effort,
        "technique": "LLM",
        "claim_id": claim["claim_id"],
        "decision": answer.decision,
        "confidence": answer.confidence.model_dump(),
        "cost": response.usage.cost,
        "seconds": round(time.time() - start, 1),
    }


def is_right(answer, label):
    """True when the decision matches the handler's."""
    return answer["decision"] == label["decision"]


def run(model, effort, claims, labels):
    """Run the model on the claims and compare against the labels."""
    results = []
    for claim in claims:
        answer = decide(claim, model, effort)
        label = labels[claim["claim_id"]]
        results.append(
            {
                **answer,
                "difficulty": label["difficulty"],
                "right": is_right(answer, label),
            }
        )
    right = sum(result["right"] for result in results)
    cost = sum(result["cost"] for result in results)
    seconds = sum(result["seconds"] for result in results)
    print(
        f"{model} at {effort}: {right} of {len(results)} right "
        f"for ${cost:.4f} in {seconds:.0f} seconds"
    )
    return results


luna_low = run("openai/gpt-6-luna", "low", claims, labels)

# How it looked...
# decision='approve' confidence=ConfidenceScores(approve=0.98, decline=0.01, refer=0.01)
# decision='refer' confidence=ConfidenceScores(approve=0.01, decline=0.01, refer=0.98)
# decision='refer' confidence=ConfidenceScores(approve=0.01, decline=0.01, refer=0.98)
# decision='approve' confidence=ConfidenceScores(approve=0.99, decline=0.005, refer=0.005)
# decision='refer' confidence=ConfidenceScores(approve=0.03, decline=0.01, refer=0.96)
# openai/gpt-6-luna at low: 19 of 25 right for $0.0047 in 74 seconds
