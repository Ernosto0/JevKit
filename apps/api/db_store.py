"""PostgreSQL-backed implementation of `apps.api.store.Store` (PLAN.md section 15).

Wires the ORM models in `db.py` behind the same async interface `InMemoryStore`
exposes, so route code never needs to know which one is answering it. Selected
by setting `JEVKIT_API_PERSISTENCE=postgres`; `apps/api/store.py` does the
picking. Each method opens and closes its own session rather than assuming a
request-scoped one, since `STORE` is a module-level singleton shared across
requests.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.db import (
    BenchmarkRun,
    DecisionRun,
    DecisionTaskRow,
    DecisionTraceRow,
    session_factory,
)
from jevkit.decisions.result import DecisionResult, ExecutionStatus, Usage, ValidationStatus
from jevkit.decisions.task import DecisionTask
from jevkit.tracing.trace import DecisionTrace, TraceEvent

__all__ = ["PostgresStore"]


def _parse_dt(value: Any) -> datetime | None:
    """Accept a datetime, an ISO string (from `model_dump(mode="json")`), or None."""
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


class PostgresStore:
    """Durable `Store` backed by PostgreSQL, via the models in `db.py`."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._sessions = sessions or session_factory()

    # -- decisions and traces -----------------------------------------------

    async def save_decision(self, result: DecisionResult, trace: DecisionTrace) -> str:
        decision_id = result.trace_id or trace.trace_id
        async with self._sessions() as session:
            session.add(
                DecisionRun(
                    id=decision_id,
                    task_ref=result.task_ref,
                    provider=result.provider,
                    model=result.model,
                    execution_status=result.execution_status.value,
                    validation_status=result.validation_status.value,
                    decisions=result.decisions,
                    confidence=result.confidence,
                    attempts=result.attempts,
                    used_fallback=result.used_fallback,
                    latency_ms=result.latency_ms,
                    cost_usd=result.usage.cost_usd if result.usage else None,
                    created_at=result.created_at,
                )
            )
            session.add(
                DecisionTraceRow(
                    run_id=decision_id,
                    events=[event.model_dump(mode="json") for event in trace.events],
                    state=trace.state,
                    created_at=trace.started_at,
                )
            )
            await session.commit()
        return decision_id

    async def get_decision(self, decision_id: str) -> DecisionResult | None:
        async with self._sessions() as session:
            row = await session.get(DecisionRun, decision_id)
            if row is None:
                return None
            usage = Usage(cost_usd=row.cost_usd) if row.cost_usd is not None else None
            return DecisionResult(
                decisions=row.decisions,
                confidence=row.confidence,
                task_ref=row.task_ref,
                provider=row.provider,
                model=row.model,
                execution_status=ExecutionStatus(row.execution_status),
                validation_status=ValidationStatus(row.validation_status),
                attempts=row.attempts,
                used_fallback=row.used_fallback,
                latency_ms=row.latency_ms,
                usage=usage,
                trace_id=row.id,
                created_at=row.created_at,
            )

    async def get_trace(self, trace_id: str) -> DecisionTrace | None:
        async with self._sessions() as session:
            trace_row = (
                await session.execute(
                    select(DecisionTraceRow).where(DecisionTraceRow.run_id == trace_id)
                )
            ).scalar_one_or_none()
            if trace_row is None:
                return None
            run = await session.get(DecisionRun, trace_id)
            return DecisionTrace(
                trace_id=trace_id,
                task_ref=run.task_ref if run else None,
                started_at=trace_row.created_at,
                events=[TraceEvent.model_validate(event) for event in trace_row.events],
                state=trace_row.state,
            )

    # -- tasks ----------------------------------------------------------------

    async def save_task(self, task: DecisionTask) -> tuple[str, datetime]:
        row = DecisionTaskRow(
            name=task.name,
            version=task.version,
            description=task.description,
            definition=task.model_dump(mode="json"),
        )
        async with self._sessions() as session:
            session.add(row)
            await session.flush()
            task_id, created_at = row.id, row.created_at
            await session.commit()
        return task_id, created_at

    async def get_task(self, name: str, version: str | None = None) -> DecisionTask | None:
        stmt = select(DecisionTaskRow).where(DecisionTaskRow.name == name)
        if version is not None:
            stmt = stmt.where(DecisionTaskRow.version == version)
        stmt = stmt.order_by(DecisionTaskRow.created_at.desc()).limit(1)
        async with self._sessions() as session:
            row = (await session.execute(stmt)).scalar_one_or_none()
        return DecisionTask.model_validate(row.definition) if row is not None else None

    async def list_tasks(self) -> list[tuple[str, datetime, DecisionTask]]:
        stmt = select(DecisionTaskRow).order_by(DecisionTaskRow.created_at.desc())
        async with self._sessions() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [
            (row.id, row.created_at, DecisionTask.model_validate(row.definition)) for row in rows
        ]

    # -- benchmarks -------------------------------------------------------------

    async def save_benchmark(self, record: dict[str, Any]) -> str:
        run_id = record.get("id") or uuid.uuid4().hex
        record["id"] = run_id
        row = BenchmarkRun(
            id=run_id,
            task_ref=record["task_ref"],
            dataset_ref=record["dataset_ref"],
            provider=record["provider"],
            status=record["status"],
            policy=record.get("policy") or {},
            report=record.get("report"),
            error=record.get("error"),
            started_at=_parse_dt(record.get("started_at")) or datetime.now(UTC),
            finished_at=_parse_dt(record.get("finished_at")),
        )
        async with self._sessions() as session:
            session.add(row)
            await session.commit()
        return run_id

    async def get_benchmark(self, run_id: str) -> dict[str, Any] | None:
        async with self._sessions() as session:
            row = await session.get(BenchmarkRun, run_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "status": row.status,
            "task_ref": row.task_ref,
            "dataset_ref": row.dataset_ref,
            "provider": row.provider,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "error": row.error,
            "report": row.report,
        }
