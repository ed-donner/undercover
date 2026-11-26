"""FastAPI dependency bindings, shared by domain routers."""

from typing import Annotated

from fastapi import Depends, Request

from backend.store import Store


def store(request: Request) -> Store:
    return request.app.state.store


Database = Annotated[Store, Depends(store)]
