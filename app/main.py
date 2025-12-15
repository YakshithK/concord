import json, time, uuid, secrets
from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import text

from .config import settings
from .db import get_db
from .auth import require_proxy_key, hash_key
from .routing import load_config, choose_route
from .normalize import rough_token_estimate, request_fingerprint
from .cache import get_cached, set_cached
from .budget import get_month_spend, add_month_spend
from .providers import call_openai, call_anthropic_from_openai_payload
from .schemas import CreateWorkspace, CreateKeyResponse, StatsResponse

app = FastAPI(title="LLM Cost Proxy", version="0.1.0")
CFG = load_config()

# Rough static cost estimates (V0). Update later with real provider pricing tables.
COST_PER_1K_TOKENS_USD = {
    "gpt-4o": 0.005,       # placeholder
    "gpt-4o-mini": 0.0005, # placeholder
    "claude-3-5-haiku": 0.0005, # placeholder
}

def est_cost(model: str, est_tokens: int) -> float:
    per_1k = COST_PER_1K_TOKENS_USD.get(model, 0.001)
    return (est_tokens / 1000.0) * per_1k

def require_admin(authorization: str | None = Header(default=None)):
    if not authorization or authorization != f"Bearer {settings.ADMIN_KEY}":
        raise HTTPException(status_code=401, detail="Admin auth required")

@app.get("/_health")
def health():
    return {"ok": True}

@app.post("/_admin/workspaces")
def create_workspace(body: CreateWorkspace, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    ws_id = str(uuid.uuid4())
    db.execute(text(
        "INSERT INTO workspaces (id, name, monthly_budget_usd, action_on_exceed) VALUES (:id,:n,:b,:a)"
    ), {"id": ws_id, "n": body.name, "b": body.monthly_budget_usd, "a": body.action_on_exceed})
    db.commit()
    return {"workspace_id": ws_id}

@app.post("/_admin/keys/{workspace_id}", response_model=CreateKeyResponse)
def create_key(workspace_id: str, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    raw = "pk_" + secrets.token_urlsafe(24)
    h = hash_key(raw)
    key_id = str(uuid.uuid4())
    db.execute(text(
        "INSERT INTO api_keys (id, workspace_id, key_hash) VALUES (:id,:ws,:h)"
    ), {"id": key_id, "ws": workspace_id, "h": h})
    db.commit()
    return CreateKeyResponse(api_key=raw)

@app.post("/v1/chat/completions")
async def chat_completions(
    payload: dict,
    workspace_id: str = Depends(require_proxy_key),
    db: Session = Depends(get_db),
):

    est_tokens_in = rough_token_estimate(payload)
    model_requested = payload.get("model", "unknown")

    decision = choose_route(CFG, est_tokens_in)
    model_used = decision.model
    provider = decision.provider
    policy_version = CFG.policy_version

    # Cache (only for temp=0 in V0 to avoid wrong outputs)
    cache_enabled = bool(CFG.defaults.get("cache", {}).get("enabled", True))
    ttl = int(CFG.defaults.get("cache", {}).get("ttl_seconds", 86400))
    temperature = payload.get("temperature", 0)

    cache_status = "BYPASS"
    cache_key = None

    if cache_enabled and (temperature == 0):
        cache_key = request_fingerprint(payload, policy_version, model_used)
        cached = get_cached(cache_key)
        if cached:
            cache_status = "HIT"
            data = json.loads(cached)
            return data
        cache_status = "MISS"

    # Budget guard
    budget_cfg = CFG.defaults.get("budgets", {})
    budget = float(budget_cfg.get("monthly_usd", 200))
    action = budget_cfg.get("action_on_exceed", "downgrade")
    current_spend = get_month_spend(workspace_id)

    est_call_cost = est_cost(model_used, est_tokens_in)
    if (current_spend + est_call_cost) > budget:
        if action == "block":
            # log blocked request
            db.execute(text("""
              INSERT INTO requests (id, workspace_id, provider, model_requested, model_used, route_name, cache_status,
                est_input_tokens, est_cost_usd, latency_ms, outcome, request_hash, policy_version)
              VALUES (:id,:ws,:p,:mr,:mu,:rn,:cs,:tin,:ec,:lat,:out,:rh,:pv)
            """), {
                "id": str(uuid.uuid4()), "ws": workspace_id,
                "p": provider, "mr": model_requested, "mu": model_used, "rn": decision.route_name,
                "cs": cache_status, "tin": est_tokens_in, "ec": est_call_cost, "lat": 0,
                "out": "blocked", "rh": (cache_key or "na"), "pv": policy_version
            })
            db.commit()
            raise HTTPException(status_code=402, detail="Budget exceeded")
        else:
            # downgrade to cheapest known model (V0)
            model_used = "gpt-4o-mini"
            provider = "openai"

    # Execute with retries + fallback
    retries = CFG.defaults.get("retries", {})
    max_attempts = int(retries.get("max_attempts", 2))
    backoffs = retries.get("backoff_ms", [200, 800])

    outcome = "ok"
    latency_ms = 0
    resp_json = None
    used_fallback = False

    for attempt in range(max_attempts + 1):
        try:
            if provider == "openai":
                resp_json, latency_ms = await call_openai(payload, model_used)
            else:
                resp_json, latency_ms = await call_anthropic_from_openai_payload(payload, model_used)
            break
        except Exception:
            if attempt < max_attempts:
                outcome = "retried"
                time.sleep(int(backoffs[min(attempt, len(backoffs)-1)]) / 1000.0)
                continue
            # fallback
            fb = CFG.fallback or {}
            fb_provider = fb.get("provider")
            fb_model = fb.get("model")
            if fb_provider and fb_model:
                used_fallback = True
                outcome = "fallback"
                if fb_provider == "openai":
                    resp_json, latency_ms = await call_openai(payload, fb_model)
                    model_used = fb_model
                    provider = "openai"
                else:
                    resp_json, latency_ms = await call_anthropic_from_openai_payload(payload, fb_model)
                    model_used = fb_model
                    provider = "anthropic"
            else:
                outcome = "error"
                raise

    # Accounting (OpenAI-style usage)
    usage = resp_json.get("usage", {}) if isinstance(resp_json, dict) else {}
    actual_in = usage.get("prompt_tokens")
    actual_out = usage.get("completion_tokens")
    actual_total = usage.get("total_tokens")
    actual_cost = est_cost(model_used, int(actual_total or est_tokens_in))

    # Spend + cache set + db log
    add_month_spend(workspace_id, float(actual_cost))

    req_id = str(uuid.uuid4())
    req_hash = cache_key or request_fingerprint(payload, policy_version, model_used)

    db.execute(text("""
      INSERT INTO requests (id, workspace_id, provider, model_requested, model_used, route_name, cache_status,
        est_input_tokens, actual_input_tokens, actual_output_tokens, est_cost_usd, actual_cost_usd,
        latency_ms, outcome, request_hash, policy_version)
      VALUES (:id,:ws,:p,:mr,:mu,:rn,:cs,:tin,:ain,:aout,:ec,:ac,:lat,:out,:rh,:pv)
    """), {
        "id": req_id, "ws": workspace_id, "p": provider,
        "mr": model_requested, "mu": model_used, "rn": decision.route_name,
        "cs": cache_status, "tin": est_tokens_in,
        "ain": actual_in, "aout": actual_out,
        "ec": est_call_cost, "ac": actual_cost,
        "lat": latency_ms, "out": outcome,
        "rh": req_hash, "pv": policy_version
    })
    db.commit()

    if cache_enabled and (temperature == 0) and cache_status == "MISS" and resp_json is not None:
        set_cached(req_hash, json.dumps(resp_json), ttl)

    # Add trust headers (FastAPI needs Response object to set headers; skip in V0 or implement later)
    return resp_json

@app.get("/_stats/today", response_model=StatsResponse)
def stats_today(db: Session = Depends(get_db), workspace_id: str = Depends(lambda db=Depends(get_db): None)):
    # V0: simple global stats; you can add auth filtering later
    q = db.execute(text("""
      SELECT
        COUNT(*) AS n,
        COALESCE(SUM(actual_cost_usd),0) AS cost
      FROM requests
      WHERE ts >= NOW() - INTERVAL '24 hours'
    """)).mappings().first()
    n = int(q["n"])
    cost = float(q["cost"])
    # placeholder for "would have cost" until you compute based on model_requested
    would = cost * 1.25
    savings = max(0.0, would - cost)
    pct = (savings / would * 100.0) if would > 0 else 0.0
    return StatsResponse(
        requests_today=n,
        cost_today_usd=cost,
        would_have_cost_usd=would,
        savings_usd=savings,
        savings_pct=pct
    )
