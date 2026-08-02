"""Health check endpoint.

Not versioned under /api/v1 — this is an infrastructure probe, not a product
API. Verifies the dependencies Phase 0 stands up: Postgres and Redis.
"""

from fastapi import APIRouter
from redis.asyncio import Redis

from instamart_engine.core.config import get_settings
from instamart_engine.core.database import check_database_connection

router = APIRouter(tags=["health"])


async def _check_redis() -> bool:
    settings = get_settings()
    client: Redis = Redis.from_url(settings.REDIS_URL)
    try:
        return bool(await client.ping())
    except Exception:  # noqa: BLE001 - health check must not raise
        return False
    finally:
        await client.aclose()


@router.get("/health")
async def health() -> dict:
    db_ok = await check_database_connection()
    redis_ok = await _check_redis()
    status = "ok" if (db_ok and redis_ok) else "degraded"
    return {
        "status": status,
        "checks": {
            "database": "ok" if db_ok else "unavailable",
            "redis": "ok" if redis_ok else "unavailable",
        },
    }
