import json, re, hashlib

def normalize_messages(messages: list[dict]) -> list[dict]:
    norm = []
    for m in messages:
        role = m.get("role", "").strip()
        content = m.get("content", "")
        if isinstance(content, str):
            content = re.sub(r"\s+", " ", content).strip()
        norm.append({"role": role, "content": content})
    return norm

def canonical_payload(payload: dict) -> dict:
    # keep only fields that influence output (v0)
    keep = {
        "messages": normalize_messages(payload.get("messages", [])),
        "temperature": payload.get("temperature", 0),
        "top_p": payload.get("top_p", 1),
        "max_tokens": payload.get("max_tokens", None),
    }
    return keep

def request_fingerprint(payload: dict, policy_version: str, model_used: str) -> str:
    canon = canonical_payload(payload)
    canon["policy_version"] = policy_version
    canon["model_used"] = model_used
    s = json.dumps(canon, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def rough_token_estimate(payload: dict) -> int:
    # rough: 4 chars ~ 1 token
    text = ""
    for m in payload.get("messages", []):
        c = m.get("content", "")
        if isinstance(c, str):
            text += c
    return max(1, len(text) // 4)
