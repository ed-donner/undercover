"""Telling the agent's service that a claim has been signed off."""

import logging
import os

import httpx

DEFAULT_AGENT_URL = "http://127.0.0.1:8002"
TIMEOUT_SECONDS = 5

logger = logging.getLogger(__name__)


def notify_sign_off(claim_id: str) -> None:
    """Ask the agent to pick a signed-off claim back up."""
    base_url = os.environ.get("UNDERCOVER_AGENT", DEFAULT_AGENT_URL)
    try:
        httpx.post(f"{base_url}/api/claims/{claim_id}/resume", timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError:
        logger.warning(
            "The agent could not be reached; it will pick up %s on its next run",
            claim_id,
        )
