from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache
from uuid import uuid4

import structlog
from fastapi import HTTPException, Request, status
from redis import Redis

from app.common.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


@lru_cache(maxsize=1)
def redis_client() -> Redis:
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
    )


def rate_limit(scope: str, limit: int, window_seconds: int):
    def dependency(request: Request) -> None:
        client_key = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
        key = f"rate:{scope}:{client_key.split(',')[0].strip()}"
        try:
            pipe = redis_client().pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds, nx=True)
            count, _ = pipe.execute()
            if int(count) > limit:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
        except HTTPException:
            raise
        except Exception as exc:
            # Emergency and intake remain available when Redis is degraded; durable DB writes still apply.
            logger.warning("rate_limiter_unavailable", error_type=type(exc).__name__, scope=scope)

    return dependency


@contextmanager
def distributed_lock(name: str, ttl_seconds: int = 300) -> Generator[bool, None, None]:
    token = str(uuid4())
    key = f"lock:{name}"
    acquired = False
    try:
        acquired = bool(redis_client().set(key, token, nx=True, ex=ttl_seconds))
        yield acquired
    except Exception as exc:
        logger.warning("redis_lock_unavailable", error_type=type(exc).__name__, lock=name)
        yield True
    finally:
        if acquired:
            try:
                redis_client().eval(
                    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
                    1,
                    key,
                    token,
                )
            except Exception:
                pass


def set_job_progress(job_id: str, percent: int, message: str) -> None:
    try:
        redis_client().hset(f"job:{job_id}", mapping={"percent": percent, "message": message})
        redis_client().expire(f"job:{job_id}", 3600)
    except Exception as exc:
        logger.warning("progress_store_unavailable", error_type=type(exc).__name__, job_id=job_id)
