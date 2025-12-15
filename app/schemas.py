from pydantic import BaseModel
from typing import Any, Optional

class CreateWorkspace(BaseModel):
    name: str
    monthly_budget_usd: float = 200
    action_on_exceed: str = "downgrade"  # downgrade|block

class CreateKeyResponse(BaseModel):
    api_key: str

class StatsResponse(BaseModel):
    requests_today: int
    cost_today_usd: float
    would_have_cost_usd: float
    savings_usd: float
    savings_pct: float
