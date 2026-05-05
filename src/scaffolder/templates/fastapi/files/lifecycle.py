from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # [jumpstart: lifespan_startup]
    yield
    # [jumpstart: lifespan_shutdown]
    await engine.dispose()
