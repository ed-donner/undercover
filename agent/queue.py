"""The Shoppie Agent's queue agent: plans a run and hands each request to a subagent."""

import threading
from collections.abc import Callable
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.runtime import Runtime

from agent import main
from agent.instructions import QUEUE_INSTRUCTIONS
from agent.models import TodoItem

MAX_RETURNS = 3
TODO_FOR_WORK = {
    "done": "done",
    "waiting": "to_do",
    "left_for_support": "left_for_support",
}


class MissedRequestCheck(AgentMiddleware):
    """Send the queue agent back when it finishes with work left within its cap."""

    def __init__(self, missed: Callable[[], list[str]]) -> None:
        super().__init__()
        self.missed = missed
        self.returns = 0

    @hook_config(can_jump_to=["model"])
    def after_agent(
        self, state: AgentState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        """Return to the model while a waiting request within the cap is unworked."""
        missed = self.missed()
        if not missed:
            return None
        self.returns += 1
        if self.returns > MAX_RETURNS:
            raise RuntimeError(f"The run left requests unworked: {', '.join(missed)}")
        reminder = (
            "Before you finish: these waiting requests are within the run's cap and "
            f"have not been worked to an end: {', '.join(missed)}. Work them, then "
            "finish with your summary."
        )
        return {"messages": [HumanMessage(reminder)], "jump_to": "model"}


def run_queue(
    run_id: str,
    cap: int,
    llm: BaseChatModel | None = None,
    request_model: Callable[[], BaseChatModel] | None = None,
) -> str:
    """Work the waiting queue up to the cap and return the run's summary."""
    worked: set[str] = set()
    lock = threading.Lock()

    def waiting_ids() -> list[str]:
        with main.backend() as client:
            response = client.get("/api/requests/waiting")
        response.raise_for_status()
        return [item["request_id"] for item in response.json()]

    def missed() -> list[str]:
        return [
            request_id
            for request_id in waiting_ids()
            if request_id in worked or len(worked) < cap
        ]

    def set_todo(request_id: str, status: str) -> None:
        with main.backend() as client:
            client.post(
                f"/api/runs/{run_id}/todos/{request_id}", json={"status": status}
            ).raise_for_status()

    @tool
    def list_waiting_requests() -> str:
        """List the id, type and creation time of each waiting request."""
        with main.backend() as client:
            response = client.get("/api/requests/waiting")
        response.raise_for_status()
        return f"Run cap: {cap} requests, {len(worked)} worked so far.\n{response.text}"

    @tool
    def write_todos(todos: list[TodoItem]) -> str:
        """Replace the run's to-do list, in the order you will work the requests."""
        with main.backend() as client:
            client.put(
                f"/api/runs/{run_id}/todos",
                json={"todos": [todo.model_dump() for todo in todos]},
            ).raise_for_status()
        return f"Recorded {len(todos)} to-do items."

    @tool
    def work_request(request_id: str) -> str:
        """Hand one waiting request to a helper that works it and reports back."""
        if request_id not in waiting_ids():
            return f"{request_id}: not a waiting request, so not worked."
        with lock:
            if request_id not in worked and len(worked) >= cap:
                return (
                    f"{request_id}: refused, the run has reached its cap of "
                    f"{cap} requests."
                )
            worked.add(request_id)
        try:
            set_todo(request_id, "in_progress")
            result = main.work_request(
                request_id, request_model() if request_model else None
            )
            set_todo(request_id, TODO_FOR_WORK.get(result["status"], "done"))
        except Exception as error:
            return f"{request_id}: could not be worked ({type(error).__name__})."
        return result["line"]

    agent = create_agent(
        llm or main.model(),
        tools=[list_waiting_requests, write_todos, work_request],
        system_prompt=QUEUE_INSTRUCTIONS,
        middleware=[*main.retry_middleware(), MissedRequestCheck(missed)],
    )
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"Work the support queue. This run's cap is {cap}.",
                }
            ]
        },
        config={
            "configurable": {"thread_id": f"queue-{run_id}"},
            "recursion_limit": 200,
        },
    )
    return result["messages"][-1].text
