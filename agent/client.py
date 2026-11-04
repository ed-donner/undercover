"""Calls to the UnderCover backend, the agent's only way to claims and instructions."""

from typing import Any

import httpx

BACKEND_URL = "http://localhost:8000"


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, body: dict | None = None) -> Any:
    """Call the backend. A refusal comes back as an error the agent can read.

    Network errors and server errors raise, so the caller can recover.
    """
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_client_error:
        return {"error": response.status_code, "detail": str(response.json()["detail"])}
    response.raise_for_status()
    return response.json()
