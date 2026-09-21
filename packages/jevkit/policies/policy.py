"""Execution policy (PLAN.md §11).

Policies are explicit and deterministic. There is no self-learning router in
v0.1, and no unbounded retry loop anywhere.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["DecisionPolicy", "OnFailure"]


class OnFailure(StrEnum):
    """What to do when an attempt does not produce an acceptable result."""

    FAIL = "fail"
    RETRY = "retry"
    FALLBACK = "fallback"
    RETRY_THEN_FALLBACK = "retry_then_fallback"
    REVIEW = "review"


class DecisionPolicy(BaseModel):
    """Provider choice, limits, and acceptance rules for one decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    primary_provider: str = "jev"
    fallback_provider: str | None = None

    timeout_seconds: float = Field(default=10.0, gt=0)
    max_retries: int = Field(default=1, ge=0, le=5)
    retry_backoff_seconds: float = Field(default=0.5, ge=0)

    on_provider_error: OnFailure = OnFailure.RETRY_THEN_FALLBACK
    on_timeout: OnFailure = OnFailure.RETRY_THEN_FALLBACK
    on_invalid_response: OnFailure = OnFailure.FALLBACK
    on_low_confidence: OnFailure = OnFailure.REVIEW

    min_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Probability below which a result is treated as low-confidence. "
            "Confidence is not a correctness guarantee (PLAN.md §17)."
        ),
    )
    max_cost_usd: float | None = Field(
        default=None, gt=0, description="Per-decision budget ceiling, when cost is reported."
    )

    def fallback_allowed(self) -> bool:
        """A fallback can only run if one is actually configured."""
        return self.fallback_provider is not None


DEFAULT_POLICY = DecisionPolicy()
"""Jev primary, one retry, no fallback configured."""
