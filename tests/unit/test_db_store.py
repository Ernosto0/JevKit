"""`PostgresStore` exercised against ephemeral SQLite (PLAN.md section 15).

No live Postgres is available in CI or in the environment this was written in,
so this cannot verify the real dialect end to end -- same caveat as the
reference provider's "tested against a mock, not a live account" gap. It does
verify the mapping between `apps.api.db`'s ORM rows and the SDK's own
pydantic types is correct and round-trips, at the same rigor tier as the rest
of the mocked-transport test suite. `docs/jev-api-notes.md`-style honesty:
this is not a substitute for running `alembic upgrade head` against real
Postgres before depending on this in production.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.db import Base
from apps.api.db_store import PostgresStore
from jevkit.decisions.questions import Choice, Noul
from jevkit.decisions.result import DecisionResult, ExecutionStatus, Usage, ValidationStatus
from jevkit.decisions.task import DecisionTask
from jevkit.tracing.trace import DecisionTrace, TraceStage

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture
async def store() -> AsyncIterator[PostgresStore]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield PostgresStore(sessions)
    finally:
        await engine.dispose()


@pytest.fixture
def routing_task() -> DecisionTask:
    return DecisionTask(
        name="support-routing",
        version="1",
        input_fields=("message",),
        questions={
            "department": Choice(options=("billing", "technical", "account", "other")),
            "urgent": Noul(instructions="Is this urgent?"),
        },
    )


async def test_save_and_get_task_round_trips(
    store: PostgresStore, routing_task: DecisionTask
) -> None:
    task_id, created_at = await store.save_task(routing_task)
    assert task_id
    assert created_at is not None

    fetched = await store.get_task("support-routing", "1")
    assert fetched == routing_task


async def test_get_task_without_version_returns_the_newest(store: PostgresStore) -> None:
    v1 = DecisionTask(name="triage", version="1", questions={"urgent": Noul()})
    v2 = DecisionTask(name="triage", version="2", questions={"urgent": Noul()})
    await store.save_task(v1)
    await store.save_task(v2)

    latest = await store.get_task("triage")
    assert latest is not None
    assert latest.version == "2"


async def test_get_unknown_task_is_none(store: PostgresStore) -> None:
    assert await store.get_task("does-not-exist") is None


async def test_list_tasks_orders_newest_first(
    store: PostgresStore, routing_task: DecisionTask
) -> None:
    other = DecisionTask(name="other-task", questions={"urgent": Noul()})
    await store.save_task(routing_task)
    await store.save_task(other)

    listed = await store.list_tasks()
    assert [task.name for _id, _created, task in listed] == ["other-task", "support-routing"]


async def test_save_and_get_decision_round_trips(store: PostgresStore) -> None:
    trace = DecisionTrace(task_ref="support-routing@1")
    trace.record(TraceStage.RECEIVED)
    trace.record(TraceStage.COMPLETED)
    result = DecisionResult(
        decisions={"department": "billing", "urgent": 0.9},
        confidence={"urgent": 0.9},
        task_ref="support-routing@1",
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
    assert fetched.provider == "jev"
    assert fetched.execution_status is ExecutionStatus.ACCEPTED
    assert fetched.validation_status is ValidationStatus.VALID
    assert fetched.usage is not None
    assert fetched.usage.cost_usd == pytest.approx(0.001)


async def test_get_unknown_decision_is_none(store: PostgresStore) -> None:
    assert await store.get_decision("does-not-exist") is None


async def test_get_trace_round_trips_events_and_state(store: PostgresStore) -> None:
    trace = DecisionTrace(task_ref="support-routing@1", state={"message": "hi"})
    trace.record(TraceStage.RECEIVED)
    trace.record(TraceStage.COMPLETED, status="accepted")
    result = DecisionResult(task_ref="support-routing@1", trace_id=trace.trace_id)

    await store.save_decision(result, trace)

    fetched = await store.get_trace(trace.trace_id)
    assert fetched is not None
    assert fetched.task_ref == "support-routing@1"
    assert fetched.state == {"message": "hi"}
    assert [e.stage for e in fetched.events] == [TraceStage.RECEIVED, TraceStage.COMPLETED]
    assert fetched.events[1].detail == {"status": "accepted"}


async def test_get_unknown_trace_is_none(store: PostgresStore) -> None:
    assert await store.get_trace("does-not-exist") is None


async def test_save_and_get_benchmark_round_trips(store: PostgresStore) -> None:
    record = {
        "id": "run-1",
        "status": "queued",
        "task_ref": "support-routing@1",
        "dataset_ref": "support-routing@1",
        "provider": "jev",
        "started_at": "2026-09-21T00:00:00+00:00",
        "finished_at": None,
        "error": None,
        "report": None,
    }

    run_id = await store.save_benchmark(dict(record))
    assert run_id == "run-1"

    fetched = await store.get_benchmark(run_id)
    assert fetched is not None
    assert fetched["status"] == "queued"
    assert fetched["task_ref"] == "support-routing@1"


async def test_save_benchmark_without_an_explicit_id_generates_one(store: PostgresStore) -> None:
    run_id = await store.save_benchmark(
        {
            "status": "queued",
            "task_ref": "support-routing@1",
            "dataset_ref": "support-routing@1",
            "provider": "jev",
            "started_at": "2026-09-21T00:00:00+00:00",
        }
    )
    assert run_id
    assert await store.get_benchmark(run_id) is not None


async def test_get_unknown_benchmark_is_none(store: PostgresStore) -> None:
    assert await store.get_benchmark("does-not-exist") is None
