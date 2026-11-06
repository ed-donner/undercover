"""The Shoppie Agent."""

import os

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
SYSTEM_PROMPT = """You are the Shoppie Agent, an assistant for customer support.
Use only order details and policies provided by the system when evaluating requests.
Recommend an outcome and cite the relevant policy. A support agent confirms decisions.
Do not claim an action happened unless the system confirms it.
Ask for missing information or refer issues needing judgment to a support agent.
If the needed order or policy information is unavailable, say so instead of guessing."""


def backend() -> httpx.Client:
    """Return a client for the Shoppie backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=10)


@tool
def check_backend() -> str:
    """Check whether the Shoppie backend is running."""
    with backend() as client:
        response = client.get("/api/health")
    response.raise_for_status()
    return response.json()["status"]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def run(request_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one support request and return its final reply."""
    agent = create_agent(
        llm or model(), tools=[check_backend], system_prompt=SYSTEM_PROMPT
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Support request {request_id}"}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].text
