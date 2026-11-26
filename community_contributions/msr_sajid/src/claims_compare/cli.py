"""Command line entry point: `uv run compare-claims`."""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from claims_compare.agent import decide_with_agent
from claims_compare.data import load_claims, load_labels, load_policies, load_wording
from claims_compare.scoring import is_right, summarize
from claims_compare.single import decide_single

BASE_URL = "https://openrouter.ai/api/v1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Single call versus agent on demo claims.")
    parser.add_argument("--model", default=os.getenv("CLAIMS_MODEL", "openrouter/free"))
    parser.add_argument("--out", type=Path, default=Path("results/last_run.json"))
    args = parser.parse_args(argv)

    load_dotenv(override=True)
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        print("OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key.")
        return 1

    # max_retries=1: every retry counts against OpenRouter's daily free-model limit
    client = OpenAI(base_url=BASE_URL, api_key=key, timeout=120, max_retries=1)
    claims, labels = load_claims(), load_labels()
    policies, wording = load_policies(), load_wording()

    single = [decide_single(client, args.model, c, policies[c["policy_id"]], wording) for c in claims]
    agent = [decide_with_agent(client, args.model, c, policies, wording) for c in claims]

    for row in (summarize("single call", single, labels), summarize("agent", agent, labels)):
        print(row)
    for s, a in zip(single, agent, strict=True):
        label = labels[s["claim_id"]]
        print(s["claim_id"], "expected", label["decision"], label["payout"],
              "| single", s["decision"], s["payout"], is_right(s, label),
              "| agent", a["decision"], a["payout"], is_right(a, label))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"model": args.model, "single": single, "agent": agent}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
