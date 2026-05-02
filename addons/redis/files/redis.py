"""Redis connection helper.

Usage:
    from .redis import get_redis

    @app.get("/example")
    async def example(redis: Redis = Depends(get_redis)) -> dict:
        await redis.set("key", "value", ex=60)
        value = await redis.get("key")
        return {"value": value}
"""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from redis.asyncio import Redis

from .settings import settings

_pool: aioredis.ConnectionPool | None = None


def _get_pool() -> aioredis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _pool


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency that yields a Redis client from the shared pool."""
    async with aioredis.Redis(connection_pool=_get_pool()) as client:
        yield client


async def close_redis() -> None:
    """Call this from your lifespan shutdown to cleanly drain the pool."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
