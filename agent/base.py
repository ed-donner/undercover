"""The backend client and the model."""

import os

import httpx
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, body: dict | None = None) -> str:
    """Call the backend and return the JSON text, rule refusals included."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.status_code >= 500:  # noqa: PLR2004
        response.raise_for_status()
    return response.text


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or DeepSeek V4.1 Flash by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
        max_retries=3,
        timeout=120,
    )
