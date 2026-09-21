"""Execution traces (PLAN.md §8, §10).

A trace records the lifecycle of one decision so that any outcome can be
explained after the fact. Inputs are captured only when explicitly enabled;
secrets are never recorded.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["DecisionTrace", "TraceEvent", "TraceStage"]


class TraceStage(StrEnum):
    """The lifecycle stages a decision passes through."""

    RECEIVED = "received"
    INPUT_VALIDATED = "input_validated"
    POLICY_RESOLVED = "policy_resolved"
    PROVIDER_SELECTED = "provider_selected"
    PROVIDER_CALL = "provider_call"
    RESPONSE_PARSED = "response_parsed"
    OUTPUT_VALIDATED = "output_validated"
    RETRY = "retry"
    FALLBACK = "fallback"
    COMPLETED = "completed"
    FAILED = "failed"


class TraceEvent(BaseModel):
    """One step in a trace."""

    model_config = ConfigDict(frozen=True)

    stage: TraceStage
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    elapsed_ms: float | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class DecisionTrace(BaseModel):
    """The ordered record of one decision execution."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    task_ref: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    events: list[TraceEvent] = Field(default_factory=list)

    state: dict[str, Any] | None = Field(
        default=None,
        description="Captured input; None unless trace_store_inputs is enabled.",
    )

    _t0: float = 0.0

    def model_post_init(self, __context: Any) -> None:
        self._t0 = time.perf_counter()

    def record(self, stage: TraceStage, **detail: Any) -> TraceEvent:
        """Append an event, stamped with elapsed time since the trace started."""
        event = TraceEvent(
            stage=stage,
            elapsed_ms=(time.perf_counter() - self._t0) * 1000,
            detail=detail,
        )
        self.events.append(event)
        return event

    @property
    def duration_ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000

    def summary(self) -> list[str]:
        """One line per stage, for CLI output and quick debugging."""
        return [
            f"{e.elapsed_ms or 0:8.1f}ms  {e.stage.value:<18} {e.detail or ''}".rstrip()
            for e in self.events
        ]
