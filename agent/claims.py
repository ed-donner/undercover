"""Claim context, write reconciliation and completion postconditions."""

import httpx

from agent.api import BackendAPI
from agent.middleware import transient


def context(api: BackendAPI, claim_id: str) -> dict:
    claim = api.claim(claim_id)
    policy = api.policy(claim["policy_id"])
    return {
        "claim": claim,
        "policy": policy,
        "plan": api.plan(policy["plan"]),
        "customer": api.customer(claim["customer_id"]),
        "company": api.company(),
    }


def decide(api: BackendAPI, claim_id: str, run_id: str, decision: dict) -> dict:
    existing = api.claim(claim_id)
    if existing["decision"] is not None:
        return existing
    try:
        return api.record_decision(claim_id, run_id, decision)
    except (httpx.TransportError, httpx.HTTPStatusError):
        final = api.claim(claim_id)
        if final["decision"] is not None:
            return final
        raise


def payment_attempt(api: BackendAPI, claim_id: str, run_id: str, amount: str) -> dict:
    existing = api.claim(claim_id)
    if existing["payment"] is not None:
        return existing
    try:
        return api.pay(claim_id, run_id, amount)
    except (httpx.TransportError, httpx.HTTPStatusError):
        final = api.claim(claim_id)
        if final["payment"] is not None:
            return final
        raise


def pay(api: BackendAPI, claim_id: str, run_id: str, amount: str) -> dict:
    try:
        return payment_attempt(api, claim_id, run_id, amount)
    except (httpx.TransportError, httpx.HTTPStatusError) as error:
        if not transient(error):
            raise
    return payment_attempt(api, claim_id, run_id, amount)


def active_attempt(api: BackendAPI, claim_id: str, thread_id: str) -> dict:
    attempt = next(
        (
            r
            for r in api.attempts(claim_id)
            if r["thread_id"] == thread_id and r["status"] == "running"
        ),
        None,
    )
    if attempt is None:
        raise RuntimeError("No active run for the supplied claim and thread")
    return attempt


def verify_completion(api: BackendAPI, claim_id: str, run_id: str) -> None:
    final = api.claim(claim_id)
    decision = final["decision"]
    if decision is None:
        raise RuntimeError("Agent finished without recording a decision")
    if (
        decision["outcome"] == "approve"
        and decision["payout"] <= api.company()["payout_approval_limit"]
        and final["payment"] is None
    ):
        pay(api, claim_id, run_id, str(decision["payout"]))
        if api.claim(claim_id)["payment"] is None:
            raise RuntimeError("Agent finished without paying a below-limit approval")
