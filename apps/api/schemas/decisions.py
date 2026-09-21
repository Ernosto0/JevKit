"""Request and response schemas for the decision endpoints.

These are the service's public contract. They deliberately do not re-export the
SDK's internal models wholesale, so the HTTP surface can stay stable while the
library evolves.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from jevkit.decisions.questions import Question
from jevkit.decisions.result import DecisionResult, ExecutionStatus, ValidationStatus
from jevkit.policies.policy import DecisionPolicy
from jevkit.tracing.trace import DecisionTrace, TraceStage

__all__ = [
    "DecisionRequest",
    "DecisionResponse",
    "HealthResponse",
    "TraceEventResponse",
    "TraceResponse",
]


class DecisionRequest(BaseModel):
    """Execute one decision.

    Supply either `questions` (ad hoc) or `task_name` (a stored definition).
    """

    model_config = ConfigDict(extra="forbid")

    state: dict[str, Any] = Field(description="The input the decision is made about.")
    questions: dict[str, Question] | None = None
    task_name: str | None = None
    task_version: str | None = None
    policy: DecisionPolicy | None = Field(
        default=None, description="Overrides the server's default policy for this call."
    )


class DecisionResponse(BaseModel):
    """A normalized decision. Never includes provider credentials or raw payloads."""

    model_config = ConfigDict(extra="forbid")

    decisions: dict[str, Any]
    confidence: dict[str, float] = Field(default_factory=dict)
    task_ref: str | None = None
    provider: str | None = None
    model: str | None = None
    execution_status: ExecutionStatus
    validation_status: ValidationStatus
    validation_failures: list[str] = Field(default_factory=list)
    attempts: int = 1
    used_fallback: bool = False
    latency_ms: float | None = None
    trace_id: str | None = None
    created_at: datetime

    @classmethod
    def from_result(cls, result: DecisionResult) -> DecisionResponse:
        """Project an SDK result onto the wire schema, dropping the raw payload."""
        return cls(
            decisions=result.decisions,
            confidence=result.confidence,
            task_ref=result.task_ref,
            provider=result.provider,
            model=result.model,
            execution_status=result.execution_status,
            validation_status=result.validation_status,
            validation_failures=list(result.validation_failures),
            attempts=result.attempts,
            used_fallback=result.used_fallback,
            latency_ms=result.latency_ms,
            trace_id=result.trace_id,
            created_at=result.created_at,
        )


class TraceEventResponse(BaseModel):
    """One step of an execution trace."""

    model_config = ConfigDict(extra="forbid")

    stage: TraceStage
    at: datetime
    elapsed_ms: float | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class TraceResponse(BaseModel):
    """A full execution trace. Input state is included only if capture is enabled."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str
    task_ref: str | None = None
    started_at: datetime
    events: list[TraceEventResponse]
    state: dict[str, Any] | None = None

    @classmethod
    def from_trace(cls, trace: DecisionTrace) -> TraceResponse:
        return cls(
            trace_id=trace.trace_id,
            task_ref=trace.task_ref,
            started_at=trace.started_at,
            events=[TraceEventResponse.model_validate(e.model_dump()) for e in trace.events],
            state=trace.state,
        )


class HealthResponse(BaseModel):
    """Liveness and build information."""

    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    version: str
    environment: str
    jev_schema_verified: bool = Field(
        description="False until the Jev wire format has been checked against official docs."
    )
