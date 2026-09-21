"""Benchmark endpoints.

Runs get durable storage when `STORE` is backed by PostgreSQL (`apps/api/store.py`).
Dataset loading and actual execution are still Phase 3 follow-up work: the
contract is already fixed -- starting a run returns immediately with an id, and
results are polled.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from apps.api.dependencies import ApiKey
from apps.api.schemas.benchmarks import (
    BenchmarkRunResponse,
    BenchmarkStartRequest,
    BenchmarkStatus,
)
from apps.api.store import STORE

router = APIRouter(tags=["benchmarks"])


@router.post(
    "/benchmarks",
    response_model=BenchmarkRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a benchmark run",
)
async def start_benchmark(request: BenchmarkStartRequest, _api_key: ApiKey) -> BenchmarkRunResponse:
    """Queue a benchmark run over a labeled dataset.

    Runs are billable and slow, so this never executes inline.
    """
    task = await STORE.get_task(request.task_name, request.task_version)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No task named {request.task_name!r}")

    record = BenchmarkRunResponse(
        id=uuid.uuid4().hex,
        status=BenchmarkStatus.QUEUED,
        task_ref=task.ref,
        dataset_ref=request.dataset_ref,
        provider=request.provider,
        started_at=datetime.now(UTC),
    )
    await STORE.save_benchmark(record.model_dump(mode="json"))

    # TODO(phase-3): dispatch to the runner in jevkit.benchmarks and persist the
    # report. Execution is deliberately not wired up until datasets are stored.
    return record


@router.get(
    "/benchmarks/{run_id}",
    response_model=BenchmarkRunResponse,
    summary="Retrieve benchmark status and results",
)
async def get_benchmark(run_id: str, _api_key: ApiKey) -> BenchmarkRunResponse:
    record = await STORE.get_benchmark(run_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No benchmark run {run_id!r}")
    return BenchmarkRunResponse.model_validate(record)
