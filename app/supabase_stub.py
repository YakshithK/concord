from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def upsert_email_normalized(*, email_normalized: str) -> None:
    """
    Placeholder for Supabase upsert to an emails table.
    Replace with a real Supabase client call.
    """
    logger.info("SUPABASE_STUB upsert_email_normalized: %s", email_normalized)


async def store_api_key_hash(*, email_normalized: str, api_key_hash: str) -> None:
    """
    Placeholder for Supabase insert to a keys table.
    Replace with a real Supabase client call.
    """
    logger.info(
        "SUPABASE_STUB store_api_key_hash: email=%s hash=%s",
        email_normalized,
        api_key_hash,
    )


