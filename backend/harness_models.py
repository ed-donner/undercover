"""Required-input contracts for queue runs and their visible tasks."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueueStart(Input):
    mode: Literal["queue"]
    max_claims: Annotated[int, Field(strict=True, gt=0)] | None


class NamedStart(Input):
    mode: Literal["claim"]
    claim_id: str


Start = Annotated[QueueStart | NamedStart, Field(discriminator="mode")]
TaskState = Literal["todo", "in_progress", "done", "needs_handler"]


class Task(Input):
    claim_id: str
    state: TaskState


class PlanInput(Input):
    tasks: list[Task]


class AttemptInput(Input):
    parent_run_id: str


class FinishInput(Input):
    error: Literal["Agent could not finish."] | None


class Todo(Task):
    task_id: str
    parent_run_id: str
    position: int
    admitted: bool
    reason: str


class AgentRun(BaseModel):
    run_id: str
    thread_id: str
    mode: Literal["queue", "claim"]
    scope: list[str]
    max_claims: int
    status: Literal["running", "completed", "failed"]
    started_at: str
    finished_at: str | None
    summary: str
    error: str | None
    checked: bool
    tasks: list[Todo]


class Completion(BaseModel):
    ready: bool
    missing: list[str]
    summary: str
