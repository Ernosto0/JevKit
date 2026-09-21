"""The API's persistence interface, and its default in-memory implementation.

`Store` is the contract routes depend on. `InMemoryStore` is process-local and
not durable -- it is what tests and a local `uvicorn --reload` use by default.
Setting `JEVKIT_API_PERSISTENCE=postgres` switches `STORE` to
`apps.api.db_store.PostgresStore` instead, without any route change: both
implementations expose the same async methods.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from jevkit.decisions.result import DecisionResult
from jevkit.decisions.task import DecisionTask
from jevkit.tracing.trace import DecisionTrace

__all__ = ["STORE", "InMemoryStore", "Store"]


class Store(Protocol):
    """Persistence contract for decisions, traces, tasks and benchmark runs."""

    async def save_decision(self, result: DecisionResult, trace: DecisionTrace) -> str: ...

    async def get_decision(self, decision_id: str) -> DecisionResult | None: ...

    async def get_trace(self, trace_id: str) -> DecisionTrace | None: ...

    async def save_task(self, task: DecisionTask) -> tuple[str, datetime]: ...

    async def get_task(self, name: str, version: str | None = None) -> DecisionTask | None: ...

    async def list_tasks(self) -> list[tuple[str, datetime, DecisionTask]]: ...

    async def save_benchmark(self, record: dict[str, Any]) -> str: ...

    async def get_benchmark(self, run_id: str) -> dict[str, Any] | None: ...


class InMemoryStore:
    """Minimal persistence stand-in for decisions, traces, tasks and benchmarks.

    Methods are declared `async` to match `Store` even though nothing here
    actually awaits -- callers (routes, tests) do not need to know which
    implementation of `Store` they were handed.
    """

    def __init__(self) -> None:
        self._decisions: dict[str, DecisionResult] = {}
        self._traces: dict[str, DecisionTrace] = {}
        self._tasks: dict[str, tuple[str, datetime, DecisionTask]] = {}
        self._benchmarks: dict[str, dict[str, Any]] = {}

    # -- decisions and traces ---------------------------------------------

    async def save_decision(self, result: DecisionResult, trace: DecisionTrace) -> str:
        decision_id = result.trace_id or uuid.uuid4().hex
        self._decisions[decision_id] = result
        self._traces[trace.trace_id] = trace
        return decision_id

    async def get_decision(self, decision_id: str) -> DecisionResult | None:
        return self._decisions.get(decision_id)

    async def get_trace(self, trace_id: str) -> DecisionTrace | None:
        return self._traces.get(trace_id)

    # -- tasks -------------------------------------------------------------

    @staticmethod
    def _key(name: str, version: str) -> str:
        return f"{name}@{version}"

    async def save_task(self, task: DecisionTask) -> tuple[str, datetime]:
        task_id = uuid.uuid4().hex
        created_at = datetime.now(UTC)
        self._tasks[self._key(task.name, task.version)] = (task_id, created_at, task)
        return task_id, created_at

    async def get_task(self, name: str, version: str | None = None) -> DecisionTask | None:
        if version is not None:
            entry = self._tasks.get(self._key(name, version))
            return entry[2] if entry else None
        matches = [entry for key, entry in self._tasks.items() if key.startswith(f"{name}@")]
        if not matches:
            return None
        return max(matches, key=lambda e: e[1])[2]  # newest by creation time

    async def list_tasks(self) -> list[tuple[str, datetime, DecisionTask]]:
        return sorted(self._tasks.values(), key=lambda e: e[1], reverse=True)

    # -- benchmarks --------------------------------------------------------

    async def save_benchmark(self, record: dict[str, Any]) -> str:
        run_id = record.get("id") or uuid.uuid4().hex
        record["id"] = run_id
        self._benchmarks[run_id] = record
        return run_id

    async def get_benchmark(self, run_id: str) -> dict[str, Any] | None:
        return self._benchmarks.get(run_id)

    def clear(self) -> None:
        """Reset everything. Used by tests. Not part of `Store` -- only meaningful
        for the in-memory backend, which is what tests run against."""
        self._decisions.clear()
        self._traces.clear()
        self._tasks.clear()
        self._benchmarks.clear()


def _build_store() -> Store:
    from apps.api.config import get_api_settings

    if get_api_settings().persistence == "postgres":
        from apps.api.db_store import PostgresStore

        return PostgresStore()
    return InMemoryStore()


STORE: Store = _build_store()
"""Process-wide store instance used by the routes."""
