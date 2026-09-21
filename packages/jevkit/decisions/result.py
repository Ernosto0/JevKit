"""Normalized decision results (PLAN.md §8)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["DecisionResult", "ExecutionStatus", "Usage", "ValidationStatus"]


class ExecutionStatus(StrEnum):
    """How the execution ended."""

    ACCEPTED = "accepted"
    FALLBACK_ACCEPTED = "fallback_accepted"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"
    FAILED = "failed"


class ValidationStatus(StrEnum):
    """Whether the normalized decisions satisfied the task's questions."""

    VALID = "valid"
    INVALID = "invalid"
    NOT_RUN = "not_run"


class Usage(BaseModel):
    """Provider usage metadata, recorded only when the provider reports it."""

    model_config = ConfigDict(frozen=True, extra="allow")

    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class DecisionResult(BaseModel):
    """The normalized outcome of one decision execution.

    `decisions` maps each question key to its answer. `confidence` holds
    provider-reported probabilities when available -- an absent entry means the
    provider did not report one, not that confidence was low.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    decisions: dict[str, Any] = Field(default_factory=dict)
    confidence: dict[str, float] = Field(default_factory=dict)

    task_ref: str | None = None
    provider: str | None = None
    model: str | None = None

    execution_status: ExecutionStatus = ExecutionStatus.ACCEPTED
    validation_status: ValidationStatus = ValidationStatus.NOT_RUN
    validation_failures: tuple[str, ...] = ()

    attempts: int = 1
    used_fallback: bool = False
    latency_ms: float | None = None
    usage: Usage | None = None

    trace_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    raw_response: dict[str, Any] | None = Field(
        default=None,
        description="Provider payload, retained only when trace capture is enabled.",
    )

    @property
    def accepted(self) -> bool:
        """True when a caller may act on this result under its policy."""
        return self.execution_status in (
            ExecutionStatus.ACCEPTED,
            ExecutionStatus.FALLBACK_ACCEPTED,
        )

    def __getitem__(self, key: str) -> Any:
        return self.decisions[key]
