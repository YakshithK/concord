import hashlib
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from .models import ApiKey
from .db import get_db

def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def require_proxy_key(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    raw = authorization.split(" ", 1)[1].strip()
    h = hash_key(raw)

    key = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == h, ApiKey.revoked_at.is_(None))
        .first()
    )
    if not key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return str(key.workspace_id)
