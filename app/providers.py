import httpx, time
from .config import settings

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

async def call_openai(payload: dict, model: str) -> tuple[dict, int]:
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
    p = dict(payload)
    p["model"] = model
    t0 = time.time()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(OPENAI_URL, json=p, headers=headers)
    latency_ms = int((time.time() - t0) * 1000)
    resp.raise_for_status()
    return resp.json(), latency_ms

async def call_anthropic_from_openai_payload(payload: dict, model: str) -> tuple[dict, int]:
    # V0 fallback: extremely minimal translation (user-only)
    # If your app uses complex system prompts, you’ll refine this later.
    messages = payload.get("messages", [])
    user_text = "\n".join([m.get("content","") for m in messages if m.get("role") == "user"])

    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    p = {
        "model": model,
        "max_tokens": payload.get("max_tokens", 512) or 512,
        "messages": [{"role": "user", "content": user_text}],
    }
    t0 = time.time()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(ANTHROPIC_URL, json=p, headers=headers)
    latency_ms = int((time.time() - t0) * 1000)
    resp.raise_for_status()
    data = resp.json()
    # Convert to OpenAI-ish shape for app compatibility
    out_text = ""
    if data.get("content") and isinstance(data["content"], list):
        out_text = "".join([c.get("text","") for c in data["content"] if c.get("type") == "text"])
    return {
        "id": data.get("id", "anthropic-fallback"),
        "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": out_text}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": data.get("usage", {}).get("input_tokens"),
            "completion_tokens": data.get("usage", {}).get("output_tokens"),
            "total_tokens": (data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0)),
        },
    }, latency_ms
