#!/usr/bin/env python3
"""Phase 4: verify JevKit's PostgreSQL persistence against a real database.

Closes the "implemented, unverified live" gap on `apps.api.db_store.PostgresStore`.
`tests/unit/test_db_store.py` exercises the same read/write surface against
ephemeral SQLite, which checks the row<->pydantic mapping but not the real
dialect (JSONB, asyncpg, the hand-written Alembic migration). This script runs
that surface against whatever `JEVKIT_DATABASE_URL` points at -- intended to be
a live PostgreSQL -- so the migration and the store are proven end to end.

    # bring a database up (docker compose up db, or any Postgres), then:
    alembic upgrade head
    python scripts/verify_postgres_persistence.py

Reads JEVKIT_DATABASE_URL from the environment or .env (same place the API and
the Alembic env read it). It does NOT create the schema itself -- run
`alembic upgrade head` first, so that this verifies the migration too, not just
`Base.metadata`. Rows it writes are cleaned up before it exits.

Exit codes: 0 every round-trip held against the live database, 1 a round-trip
failed or the schema was missing, 2 no database URL configured.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import sys

# `apps` is not an installed package (only `jevkit` is); put the repo root on the
# path, the same way alembic.ini's `prepend_sys_path = .` does for migrations.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.config import get_api_settings
from apps.api.db import (
    BenchmarkRun,
    DecisionRun,
    DecisionTaskRow,
    DecisionTraceRow,
)
from apps.api.db_store import PostgresStore
from jevkit.decisions.questions import Choice, Noul
from jevkit.decisions.result import DecisionResult, ExecutionStatus, Usage, ValidationStatus
from jevkit.decisions.task import DecisionTask
from jevkit.tracing.trace import DecisionTrace, TraceStage

# A marker carried in the task name/refs so cleanup only ever removes what this
# script wrote, never a real row that happens to share the database. Lowercase
# and hyphenated to satisfy DecisionTask's name pattern (^[a-z0-9][a-z0-9_-]*$).
MARKER = "zzz-verify-pg"


def _ok(label: str) -> None:
    print(f"  ok   {label}")


async def _verify(sessions: async_sessionmaker) -> None:
    store = PostgresStore(sessions)

    # -- tasks: save, get (pinned + latest), list ---------------------------
    task = DecisionTask(
        name=f"{MARKER}-routing",
        version="1",
        input_fields=("message",),
        questions={
            "department": Choice(options=("billing", "technical", "account", "other")),
            "urgent": Noul(instructions="Is this urgent?"),
        },
    )
    task_id, created_at = await store.save_task(task)
    assert task_id and created_at is not None
    assert await store.get_task(task.name, "1") == task
    _ok("task save/get round-trips through JSONB")

    v2 = DecisionTask(name=f"{MARKER}-routing", version="2", questions={"urgent": Noul()})
    await store.save_task(v2)
    latest = await store.get_task(f"{MARKER}-routing")
    assert latest is not None and latest.version == "2"
    _ok("get_task without version returns the newest")

    listed = [t for _id, _c, t in await store.list_tasks() if t.name == f"{MARKER}-routing"]
    assert len(listed) == 2
    _ok("list_tasks returns persisted rows")

    # -- decisions + traces: save, get, trace with state --------------------
    trace = DecisionTrace(task_ref=f"{MARKER}-routing@1", state={"message": "hi"})
    trace.record(TraceStage.RECEIVED)
    trace.record(TraceStage.COMPLETED, status="accepted")
    result = DecisionResult(
        decisions={"department": "billing", "urgent": 0.9},
        confidence={"urgent": 0.9},
        task_ref=f"{MARKER}-routing@1",
        provider="jev",
        model="jev-latest",
        execution_status=ExecutionStatus.ACCEPTED,
        validation_status=ValidationStatus.VALID,
        attempts=1,
        latency_ms=42.5,
        usage=Usage(input_tokens=10, output_tokens=5, cost_usd=0.001),
        trace_id=trace.trace_id,
    )
    decision_id = await store.save_decision(result, trace)
    assert decision_id == trace.trace_id

    fetched = await store.get_decision(decision_id)
    assert fetched is not None
    assert fetched.decisions == result.decisions
    assert fetched.confidence == result.confidence
    assert fetched.execution_status is ExecutionStatus.ACCEPTED
    assert fetched.validation_status is ValidationStatus.VALID
    assert fetched.usage is not None and abs(fetched.usage.cost_usd - 0.001) < 1e-9
    _ok("decision save/get round-trips (status enums, usage, cost)")

    fetched_trace = await store.get_trace(trace.trace_id)
    assert fetched_trace is not None
    assert fetched_trace.state == {"message": "hi"}
    assert [e.stage for e in fetched_trace.events] == [TraceStage.RECEIVED, TraceStage.COMPLETED]
    assert fetched_trace.events[1].detail == {"status": "accepted"}
    _ok("trace events + captured state round-trip through JSONB arrays")

    # -- benchmarks: save (explicit + generated id), get --------------------
    run_id = await store.save_benchmark(
        {
            "id": f"{MARKER}-run-1",
            "status": "completed",
            "task_ref": f"{MARKER}-routing@1",
            "dataset_ref": f"{MARKER}-routing@1",
            "provider": "jev",
            "policy": {"retries": 1},
            "report": {"accuracy": 0.875, "f1": 0.867},
            "started_at": "2026-10-04T00:00:00+00:00",
            "finished_at": "2026-10-04T00:00:01+00:00",
            "error": None,
        }
    )
    assert run_id == f"{MARKER}-run-1"
    bench = await store.get_benchmark(run_id)
    assert bench is not None and bench["status"] == "completed"
    assert bench["report"] == {"accuracy": 0.875, "f1": 0.867}
    _ok("benchmark run save/get round-trips (report through JSONB)")

    assert await store.get_decision("does-not-exist") is None
    assert await store.get_trace("does-not-exist") is None
    assert await store.get_benchmark("does-not-exist") is None
    _ok("unknown ids return None, not an error")


async def _cleanup(sessions: async_sessionmaker) -> None:
    async with sessions() as session:
        await session.execute(delete(BenchmarkRun).where(BenchmarkRun.id.like(f"{MARKER}%")))
        await session.execute(
            delete(DecisionTraceRow).where(
                DecisionTraceRow.run_id.in_(
                    # traces are keyed by run id; delete the ones whose run is ours
                    [
                        r
                        for (r,) in (
                            await session.execute(
                                text("SELECT id FROM decision_runs WHERE task_ref LIKE :m"),
                                {"m": f"{MARKER}%"},
                            )
                        ).all()
                    ]
                )
            )
        )
        await session.execute(delete(DecisionRun).where(DecisionRun.task_ref.like(f"{MARKER}%")))
        await session.execute(
            delete(DecisionTaskRow).where(DecisionTaskRow.name.like(f"{MARKER}%"))
        )
        await session.commit()


async def _main() -> int:
    url = get_api_settings().database_url
    if not url or url.startswith("sqlite"):
        print(
            "JEVKIT_DATABASE_URL is not set to a database (got: "
            f"{url or '<empty>'}). Point it at a live Postgres first.",
            file=sys.stderr,
        )
        return 2

    # Redact credentials when echoing which database we are hitting.
    safe = url
    if "@" in safe:
        safe = safe.split("@", 1)[0].rsplit(":", 1)[0] + ":***@" + safe.split("@", 1)[1]
    print(f"Verifying PostgreSQL persistence against: {safe}")

    engine = create_async_engine(url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        # Fail clearly if the migration has not been run.
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1 FROM decision_tasks LIMIT 1"))
            row = (await conn.execute(text("SELECT version_num FROM alembic_version"))).first()
            print(f"  ok   schema present, alembic at {row[0] if row else '<none>'}")
        await _cleanup(sessions)  # clear any leftovers from a previous aborted run
        await _verify(sessions)
        await _cleanup(sessions)
    except Exception as exc:  # this is a top-level probe; any failure is a non-zero exit
        print(f"\nFAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            "If this is a 'relation does not exist' error, run `alembic upgrade head` first.",
            file=sys.stderr,
        )
        await engine.dispose()
        return 1

    await engine.dispose()
    print("\nAll PostgreSQL persistence round-trips held against the live database.")
    return 0


if __name__ == "__main__":
    # Allow running from a checkout without an editable install on the path.
    if "JEVKIT_API_PERSISTENCE" not in os.environ:
        os.environ["JEVKIT_API_PERSISTENCE"] = "postgres"
    raise SystemExit(asyncio.run(_main()))
