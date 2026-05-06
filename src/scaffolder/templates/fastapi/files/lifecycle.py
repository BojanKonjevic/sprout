from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # [zenit: lifespan_startup]
    yield
    # [zenit: lifespan_shutdown]
    await engine.dispose()
