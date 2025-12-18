from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from redis.asyncio import Redis

from app.config import settings
from app.rate_limit import check_rate_limit_signup_ip
from app.security import generate_api_key, hash_api_key
from app.supabase_stub import store_api_key_hash, upsert_email_normalized

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """
    Best-effort IP extraction:
    - Use first value of X-Forwarded-For if present (assumes trusted proxy sets it)
    - Else fall back to request.client.host
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # xff format: "client, proxy1, proxy2"
        first = xff.split(",")[0].strip()
        if first:
            return first
    ip = request.client.host if request.client else "unknown"
    # Normalize localhost variants
    if ip in ("127.0.0.1", "::1", "localhost"):
        return "127.0.0.1"
    return ip


def normalize_email(email: str) -> str:
    return email.strip().lower()


class GenerateKeyRequest(BaseModel):
    email: EmailStr


class GenerateKeyResponse(BaseModel):
    api_key: str = Field(..., description="API key to show once to the user")


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis: Redis | None = None
    if settings.redis_url:
        try:
            redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
            await redis.ping()
            logger.info(f"Connected to Redis at {settings.redis_url}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis at {settings.redis_url}: {e}")
            if redis:
                await redis.aclose()
            redis = None
            
            # Try localhost as fallback
            try:
                logger.info("Attempting to connect to Redis at localhost...")
                redis = Redis.from_url("redis://localhost:6379/0", decode_responses=True, socket_connect_timeout=2)
                await redis.ping()
                logger.info("Connected to Redis at localhost:6379")
            except Exception as e2:
                logger.warning(f"Failed to connect to Redis at localhost: {e2}")
                if redis:
                    await redis.aclose()
                redis = None
                logger.warning("Rate limiting will be DISABLED - Redis not available")

    app.state.redis = redis
    try:
        yield
    finally:
        if redis:
            await redis.aclose()


app = FastAPI(lifespan=lifespan)


@app.post("/api/generate_key_v0", response_model=GenerateKeyResponse)
async def generate_key_v0(payload: GenerateKeyRequest, request: Request) -> GenerateKeyResponse:
    ip = get_client_ip(request)
    redis: Redis | None = getattr(request.app.state, "redis", None)
    
    # Debug logging
    logger.debug(f"Rate limit check for IP: {ip}, Redis available: {redis is not None}")

    rl = await check_rate_limit_signup_ip(redis=redis, ip=ip, max_per_hour=3)
    
    # Debug logging
    logger.debug(f"Rate limit result: allowed={rl.allowed}, remaining={rl.remaining}, count would be {3 - rl.remaining}")
    
    if not rl.allowed:
        # 429 Too Many Requests
        raise HTTPException(
            status_code=429,
            detail={
                "message": "rate_limited",
                "remaining": rl.remaining,
                "reset_seconds": rl.reset_seconds,
            },
        )

    email_normalized = normalize_email(str(payload.email))
    api_key = generate_api_key(prefix="ck_")
    api_key_h = hash_api_key(api_key=api_key, pepper=settings.api_key_pepper)

    # Side effects (Supabase placeholders for now)
    await asyncio.gather(
        upsert_email_normalized(email_normalized=email_normalized),
        store_api_key_hash(email_normalized=email_normalized, api_key_hash=api_key_h),
    )

    return GenerateKeyResponse(api_key=api_key)


