"""Database connection management."""

import asyncpg
from asyncpg import Pool

from .config import Settings, get_settings

_pool: Pool | None = None


async def get_pool() -> Pool:
    """Get or create the database connection pool."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    return _pool


async def close_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def check_connection(pool: Pool) -> bool:
    """Check if database connection is alive."""
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False
