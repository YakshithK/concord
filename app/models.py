import uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Numeric, Integer, ForeignKey, Text
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    monthly_budget_usd: Mapped[float] = mapped_column(Numeric, default=200)
    action_on_exceed: Mapped[str] = mapped_column(String, default="downgrade")
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    key_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

class RequestLog(Base):
    __tablename__ = "requests"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    ts: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model_requested: Mapped[str] = mapped_column(String, nullable=False)
    model_used: Mapped[str] = mapped_column(String, nullable=False)
    route_name: Mapped[str | None] = mapped_column(String, nullable=True)
    cache_status: Mapped[str] = mapped_column(String, nullable=False)
    est_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    est_cost_usd: Mapped[float] = mapped_column(Numeric, nullable=False)
    actual_cost_usd: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[str] = mapped_column(String, nullable=False)

class MonthlySpend(Base):
    __tablename__ = "monthly_spend"
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    month: Mapped[str] = mapped_column(String, primary_key=True)
    total_cost_usd: Mapped[float] = mapped_column(Numeric, nullable=False, default=0)
