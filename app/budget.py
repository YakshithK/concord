from datetime import datetime
from .cache import r

def month_key() -> str:
    return datetime.utcnow().strftime("%Y-%m")

def get_month_spend(workspace_id: str) -> float:
    v = r.get(f"spend:{workspace_id}:{month_key()}")
    return float(v) if v else 0.0

def add_month_spend(workspace_id: str, amount: float) -> None:
    k = f"spend:{workspace_id}:{month_key()}"
    r.incrbyfloat(k, amount)
