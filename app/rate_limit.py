from __future__ import annotations

import time
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_seconds: int


def _hour_bucket(now: float | None = None) -> int:
    now = now if now is not None else time.time()
    return int(now // 3600)


async def check_rate_limit_signup_ip(
    *,
    redis: Redis | None,
    ip: str,
    max_per_hour: int = 3,
) -> RateLimitResult:
    """
    Enforces a per-IP rolling 1-hour bucket limit using Redis:
      key = signup:{ip}:{hourBucket}
      INCR
      EXPIRE 3600 (set when first created)
    """
    reset_seconds = 3600
    if not redis:
        # Dev fallback: no Redis configured, allow everything.
        # This should not happen in production - Redis connection failure should fail fast.
        import logging
        logging.warning("Rate limiting disabled: Redis not available")
        return RateLimitResult(allowed=True, remaining=max_per_hour, reset_seconds=reset_seconds)

    bucket = _hour_bucket()
    key = f"signup:{ip}:{bucket}"

    try:
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        count, ttl = await pipe.execute()

        # If key is new, TTL can be -1; set expiry.
        if ttl in (-1, -2):
            await redis.expire(key, reset_seconds)
            ttl = reset_seconds

        remaining = max(0, max_per_hour - int(count))
        allowed = int(count) <= max_per_hour
        reset_in = int(ttl) if int(ttl) > 0 else reset_seconds

        return RateLimitResult(allowed=allowed, remaining=remaining, reset_seconds=reset_in)
    except Exception as e:
        # If Redis operation fails, log and allow (fail open for availability)
        # In production, you might want to fail closed instead
        import logging
        logging.error(f"Rate limit check failed for {ip}: {e}", exc_info=True)
        return RateLimitResult(allowed=True, remaining=max_per_hour, reset_seconds=reset_seconds)


