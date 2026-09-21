"""PostgreSQL persistence (PLAN.md section 15).

The ORM models below are wired into the routes through `apps.api.db_store.PostgresStore`,
selected by setting `JEVKIT_API_PERSISTENCE=postgres` (see `apps.api.store`). Schema
changes go through Alembic migrations in `migrations/`, not `Base.metadata.create_all`.

Retention and redaction rules, not just table shapes, are part of this layer:
`decision_traces.state` is nullable on purpose and stays NULL unless input
capture is explicitly enabled.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from apps.api.config import get_api_settings

__all__ = ["Base", "get_engine", "get_session", "session_factory"]


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


# JSONB on PostgreSQL (indexable, native binary storage); portable JSON on every
# other dialect so `PostgresStore` can be exercised against ephemeral SQLite in
# tests without a live Postgres (see tests/unit/test_db_store.py).
_JSON = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    """Declarative base for every JevKit table."""


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DecisionTaskRow(Base):
    __tablename__ = "decision_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(32), default="1")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition: Mapped[dict[str, Any]] = mapped_column(_JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DecisionPolicyRow(Base):
    __tablename__ = "decision_policies"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128))
    definition: Mapped[dict[str, Any]] = mapped_column(_JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DecisionRun(Base):
    __tablename__ = "decision_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    task_ref: Mapped[str | None] = mapped_column(String(160), index=True, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    execution_status: Mapped[str] = mapped_column(String(32), index=True)
    validation_status: Mapped[str] = mapped_column(String(32))
    decisions: Mapped[dict[str, Any]] = mapped_column(_JSON)
    confidence: Mapped[dict[str, Any]] = mapped_column(_JSON, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    used_fallback: Mapped[bool] = mapped_column(default=False)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    trace: Mapped[DecisionTraceRow | None] = relationship(back_populates="run", uselist=False)
    model_calls: Mapped[list[ModelCall]] = relationship(back_populates="run")


class DecisionTraceRow(Base):
    __tablename__ = "decision_traces"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("decision_runs.id"), index=True)
    events: Mapped[list[dict[str, Any]]] = mapped_column(_JSON)
    # NULL unless input capture is explicitly enabled; see PLAN.md section 15.
    state: Mapped[dict[str, Any] | None] = mapped_column(_JSON, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped[DecisionRun] = relationship(back_populates="trace")


class ModelCall(Base):
    __tablename__ = "model_calls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("decision_runs.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped[DecisionRun] = relationship(back_populates="model_calls")


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    task_ref: Mapped[str] = mapped_column(String(160), index=True)
    dataset_ref: Mapped[str] = mapped_column(String(160), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    policy: Mapped[dict[str, Any]] = mapped_column(_JSON)
    report: Mapped[dict[str, Any] | None] = mapped_column(_JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    benchmark_run_id: Mapped[str] = mapped_column(ForeignKey("benchmark_runs.id"), index=True)
    question: Mapped[str] = mapped_column(String(128))
    metric: Mapped[str] = mapped_column(String(64))
    value: Mapped[float] = mapped_column(Float)
    scored_examples: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first use."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_api_settings().database_url, pool_pre_ping=True)
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a database session."""
    async with session_factory()() as session:
        yield session
