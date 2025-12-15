import yaml
from dataclasses import dataclass
from .config import settings

@dataclass
class RouteDecision:
    provider: str
    model: str
    route_name: str | None

class ProxyConfig:
    def __init__(self, raw: dict):
        self.raw = raw
        self.policy_version = "v0"
        self.defaults = raw.get("defaults", {})
        self.routing = raw.get("routing", [])
        self.fallback = raw.get("fallback", {})

def load_config() -> ProxyConfig:
    with open(settings.PROXY_CONFIG_PATH, "r") as f:
        raw = yaml.safe_load(f)
    return ProxyConfig(raw)

def choose_route(cfg: ProxyConfig, est_tokens: int) -> RouteDecision:
    # deterministic first-match rules
    for rule in cfg.routing:
        when = rule.get("when", {})
        lt = when.get("est_input_tokens_lt")
        gte = when.get("est_input_tokens_gte")
        ok = True
        if lt is not None: ok = ok and (est_tokens < int(lt))
        if gte is not None: ok = ok and (est_tokens >= int(gte))
        if ok:
            use = rule.get("use", {})
            return RouteDecision(
                provider=use.get("provider", cfg.defaults.get("provider", "openai")),
                model=use.get("model", cfg.defaults.get("model", "gpt-4o")),
                route_name=rule.get("name"),
            )
    return RouteDecision(
        provider=cfg.defaults.get("provider", "openai"),
        model=cfg.defaults.get("model", "gpt-4o"),
        route_name=None,
    )
