"""Schemas for benchmark runs."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from jevkit.policies.policy import DecisionPolicy

__all__ = ["BenchmarkRunResponse", "BenchmarkStartRequest", "BenchmarkStatus"]


class BenchmarkStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BenchmarkStartRequest(BaseModel):
    """Start a benchmark run.

    Comparing providers means starting one run per provider against the same
    dataset ref and the same policy (PLAN.md section 12).
    """

    model_config = ConfigDict(extra="forbid")

    task_name: str
    task_version: str | None = None
    dataset_ref: str
    provider: str = "jev"
    policy: DecisionPolicy | None = None
    concurrency: int = Field(default=4, ge=1, le=32)


class BenchmarkRunResponse(BaseModel):
    """Status and, once finished, the measured report."""

    model_config = ConfigDict(extra="forbid")

    id: str
    status: BenchmarkStatus
    task_ref: str
    dataset_ref: str
    provider: str
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
    report: dict[str, Any] | None = Field(
        default=None, description="The BenchmarkReport, present once status is completed."
    )
