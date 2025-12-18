from __future__ import annotations

import hashlib
import secrets


def generate_api_key(*, prefix: str = "ck_") -> str:
    # token_urlsafe already uses cryptographically secure randomness.
    return f"{prefix}{secrets.token_urlsafe(32)}"


def hash_api_key(*, api_key: str, pepper: str) -> str:
    # Store only the hash (hex); pepper should be an env var.
    h = hashlib.sha256()
    h.update((pepper + api_key).encode("utf-8"))
    return h.hexdigest()


