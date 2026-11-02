"""Compare 100+ OpenRouter models on UnderCover claims.

This runner keeps the answer key out of every model prompt. It supports a
direct structured-answer protocol and a tool-using agent protocol. Use
``--dry-run`` (the default) to inspect the selected catalog without making
model calls.

Examples:

    uv run python community_contributions/aparnamantha/week2day1_model_sweep.py \
        --dry-run
    uv run python community_contributions/aparnamantha/week2day1_model_sweep.py \
        --run --mode direct --claims 5
    uv run python community_contributions/aparnamantha/week2day1_model_sweep.py \
        --run --mode both --claims 5

The full 100-model sweep can exceed OpenRouter's free-account daily request
limit. Start with one or five claims and increase it only after checking cost
and rate limits.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1"
MAX_RETRIES = 2


@dataclass(frozen=True)
class ModelInfo:
    model_id: str
    prompt_price: float
    completion_price: float

    @property
    def is_free(self) -> bool:
        return self.prompt_price == 0 and self.completion_price == 0

    @property
    def blended_price(self) -> float:
        return self.prompt_price + self.completion_price


def load_json(name: str) -> Any:
    """Load a repository data file."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def money(value: Any) -> float:
    """Convert OpenRouter's decimal price strings to dollars per token."""
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError):
        return float("inf")
    return parsed if parsed >= 0 else float("inf")


async def fetch_models(api_key: str) -> list[ModelInfo]:
    """Fetch models that currently expose pricing from OpenRouter."""
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(OPENROUTER_MODELS_URL, headers=headers)
        response.raise_for_status()
    models: list[ModelInfo] = []
    for raw in response.json().get("data", []):
        pricing = raw.get("pricing") or {}
        prompt_price = money(pricing.get("prompt"))
        completion_price = money(pricing.get("completion"))
        if (
            raw.get("id")
            and prompt_price != float("inf")
            and completion_price != float("inf")
        ):
            models.append(ModelInfo(raw["id"], prompt_price, completion_price))
    return sorted(
        models,
        key=lambda model: (not model.is_free, model.blended_price, model.model_id),
    )


def select_models(
    models: list[ModelInfo],
    count: int,
    max_prompt_price: float,
    max_completion_price: float,
) -> list[ModelInfo]:
    """Select free models first, then models below the configured price caps."""
    selected = [
        model
        for model in models
        if model.is_free
        or (
            model.prompt_price <= max_prompt_price / 1_000_000
            and model.completion_price <= max_completion_price / 1_000_000
        )
    ]
    if len(selected) < count:
        raise RuntimeError(
            f"Only {len(selected)} models meet the price caps; {count} are required. "
            "Raise --max-prompt-price/--max-completion-price or lower --models."
        )
    return selected[:count]


def make_prompt(claim: dict[str, Any], policy: dict[str, Any], wording: str) -> str:
    """Build the complete context for a direct model comparison."""
    return (
        "# Policy record\n\n"
        f"{json.dumps(policy, indent=2)}\n\n"
        "# Claim\n\n"
        f"{json.dumps(claim, indent=2)}\n\n"
        "# Policy wording\n\n"
        f"{wording}\n\n"
        "Return JSON with exactly these keys: decision (approve, decline, or refer), "
        "payout (number), reason (string), and reference (string)."
    )


def extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from a model response."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("Model did not return a JSON object") from None
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Model JSON response was not an object")
    return value


def claim_is_right(response: dict[str, Any], label: dict[str, Any]) -> bool:
    """Apply the course comparison rule to one model response."""
    decision = str(response.get("decision", "")).lower()
    try:
        payout = float(response.get("payout", 0))
    except (TypeError, ValueError):
        return False
    return decision == label["decision"] and abs(payout - float(label["payout"])) <= 1


def agent_tools(policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Return tools for the tool-using agent protocol."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_policy",
                "description": "Retrieve the customer's policy record before deciding.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "record_decision",
                "description": "Record the final claim decision and payout.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "decision": {
                            "type": "string",
                            "enum": ["approve", "decline", "refer"],
                        },
                        "payout": {"type": "number"},
                        "reason": {"type": "string"},
                        "reference": {"type": "string"},
                    },
                    "required": ["decision", "payout", "reason", "reference"],
                    "additionalProperties": False,
                },
            },
        },
    ]


async def call_model(  # noqa: PLR0913, PLR0917
    client: AsyncOpenAI,
    model: ModelInfo,
    claim: dict[str, Any],
    policy: dict[str, Any],
    wording: str,
    mode: str,
) -> tuple[dict[str, Any], int, float]:
    """Run one direct request or one tool-using agent conversation."""
    system = (
        "You are an UnderCover claims handler. Follow the policy wording exactly. "
        "Do not invent facts. Use the available tools and make one final decision.\n\n"
        f"Policy wording:\n{wording}"
    )
    if mode == "direct":
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": make_prompt(claim, policy, wording)},
        ]
    else:
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Claim:\n{json.dumps(claim, indent=2)}\n\n"
                    "Call get_policy, apply the policy wording, then "
                    "call record_decision."
                ),
            },
        ]

    started = time.perf_counter()
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.chat.completions.create(
                model=model.model_id,
                messages=messages,
                tools=None if mode == "direct" else agent_tools(policy),
                tool_choice="auto" if mode == "agent" else None,
                temperature=0,
            )
            usage = int(response.usage.total_tokens) if response.usage else 0
            message = response.choices[0].message
            if mode == "direct":
                return (
                    extract_json(message.content or ""),
                    usage,
                    time.perf_counter() - started,
                )
            for tool_call in message.tool_calls or []:
                if tool_call.function.name == "get_policy":
                    messages.extend(
                        [
                            message.model_dump(exclude_none=True),
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps(policy),
                            },
                        ]
                    )
                elif tool_call.function.name == "record_decision":
                    return (
                        extract_json(tool_call.function.arguments),
                        usage,
                        time.perf_counter() - started,
                    )
            messages.append(message.model_dump(exclude_none=True))
            messages.append(
                {
                    "role": "user",
                    "content": "Use record_decision now with your final answer.",
                }
            )
        except Exception:
            if attempt == MAX_RETRIES:
                raise
            await asyncio.sleep(2**attempt)
    raise RuntimeError("Model call ended without a result")


async def run_sweep(  # noqa: PLR0913, PLR0917
    models: list[ModelInfo],
    claims: list[dict[str, Any]],
    labels: dict[str, dict[str, Any]],
    policies: dict[str, dict[str, Any]],
    wording: str,
    api_key: str,
    mode: str,
    concurrency: int,
) -> list[dict[str, Any]]:
    """Run every selected model over every selected claim."""
    client = AsyncOpenAI(api_key=api_key, base_url=OPENROUTER_CHAT_URL)
    semaphore = asyncio.Semaphore(concurrency)

    async def run_one(
        model: ModelInfo, claim: dict[str, Any], protocol: str
    ) -> dict[str, Any]:
        async with semaphore:
            try:
                response, tokens, seconds = await call_model(
                    client,
                    model,
                    claim,
                    policies[claim["policy_id"]],
                    wording,
                    protocol,
                )
                return {
                    "model": model.model_id,
                    "protocol": protocol,
                    "claim_id": claim["claim_id"],
                    "right": claim_is_right(response, labels[claim["claim_id"]]),
                    "payout": response.get("payout"),
                    "decision": response.get("decision"),
                    "tokens": tokens,
                    "seconds": round(seconds, 3),
                    "error": "",
                }
            except Exception as error:
                return {
                    "model": model.model_id,
                    "protocol": protocol,
                    "claim_id": claim["claim_id"],
                    "right": False,
                    "payout": None,
                    "decision": None,
                    "tokens": 0,
                    "seconds": 0,
                    "error": f"{type(error).__name__}: {error}",
                }

    protocols = ["direct", "agent"] if mode == "both" else [mode]
    jobs = [
        run_one(model, claim, protocol)
        for model in models
        for protocol in protocols
        for claim in claims
    ]
    return await asyncio.gather(*jobs)


def parse_args() -> argparse.Namespace:
    """Parse safe-by-default command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="store_true",
        help="Make model calls; without this, only preview models.",
    )
    parser.add_argument("--mode", choices=["direct", "agent", "both"], default="both")
    parser.add_argument("--models", type=int, default=100)
    parser.add_argument(
        "--claims", type=int, default=1, help="Claims per model; use 0 for all claims."
    )
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--max-prompt-price",
        type=float,
        default=1.0,
        help="USD per million input tokens.",
    )
    parser.add_argument(
        "--max-completion-price",
        type=float,
        default=5.0,
        help="USD per million output tokens.",
    )
    parser.add_argument("--output", type=Path, default=Path("model_sweep_results.json"))
    return parser.parse_args()


async def main() -> None:
    """Run the catalog preview or requested benchmark."""
    args = parse_args()
    load_dotenv(ROOT / ".env", override=True)
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing from .env")

    models = select_models(
        await fetch_models(api_key),
        args.models,
        args.max_prompt_price,
        args.max_completion_price,
    )
    print(
        f"Selected {len(models)} models "
        f"({sum(model.is_free for model in models)} free)."
    )
    for model in models:
        print(
            f"{model.model_id}: ${model.prompt_price * 1_000_000:.3f}/M in, "
            f"${model.completion_price * 1_000_000:.3f}/M out"
        )
    if not args.run:
        print("Preview only. Add --run to call models.")
        return

    claims = load_json("claims.json")
    if args.claims:
        claims = claims[: args.claims]
    labels = {row["claim_id"]: row for row in load_json("evals/decisions.json")}
    policies = {row["policy_id"]: row for row in load_json("policies.json")}
    wording = (DATA / "policy_wording.md").read_text(encoding="utf-8")
    results = await run_sweep(
        models,
        claims,
        labels,
        policies,
        wording,
        api_key,
        args.mode,
        max(1, args.concurrency),
    )
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    correct = sum(row["right"] for row in results)
    print(
        f"Saved {len(results)} rows to {args.output}; "
        f"accuracy {correct}/{len(results)}."
    )


if __name__ == "__main__":
    asyncio.run(main())
