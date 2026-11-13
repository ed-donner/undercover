"""Application composition and local service lifecycle."""

import os
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from agent.main import run as run_agent
from agent.queue import run_queue
from backend.execution import Runner
from backend.harness import Harness
from backend.routes import agent_runs, claims, documents, records
from backend.store import Store
from backend.workflow import Workflow


def create_app(
    database_path: Path | None = None,
    runner: Runner | None = run_agent,
    queue_runner: Runner | None = run_queue,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.store.initialize()
        Workflow(application.state.store).recover()
        Harness(application.state.store).recover()
        application.state.executor = ThreadPoolExecutor(max_workers=4)
        try:
            yield
        finally:
            application.state.executor.shutdown(wait=True)

    application = FastAPI(title="UnderCover", lifespan=lifespan)
    application.state.store = Store(
        database_path or Path(os.getenv("DATABASE_PATH", "undercover.db"))
    )
    application.state.runner = runner
    application.state.queue_runner = queue_runner
    for module in (records, claims, agent_runs, documents):
        application.include_router(module.router, prefix="/api")
    return application


app = create_app()
