import redis
from .config import settings

r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

def get_cached(key: str) -> str | None:
    return r.get(f"cache:{key}")

def set_cached(key: str, value: str, ttl_seconds: int) -> None:
    r.setex(f"cache:{key}", ttl_seconds, value)
