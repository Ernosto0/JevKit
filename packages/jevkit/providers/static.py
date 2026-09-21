"""A deterministic in-process provider.

Used by unit tests, examples and the CLI's `--dry-run`, so that the engine,
policies and benchmark runner can be exercised without network access or spend.
It makes no attempt to be accurate and must never be benchmarked as a model.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from jevkit.decisions.questions import Choice, Noul, Rank, Scalar, Score, Selection
from jevkit.providers.base import ModelProvider, ProviderRequest, ProviderResponse

__all__ = ["StaticProvider"]


class StaticProvider(ModelProvider):
    """Answers with fixed values, a callable, or a schema-valid placeholder."""

    name = "static"

    def __init__(
        self,
        decisions: dict[str, Any] | None = None,
        *,
        name: str = "static",
        responder: Callable[[ProviderRequest], dict[str, Any]] | None = None,
        confidence: dict[str, float] | None = None,
    ) -> None:
        self.name = name
        self._decisions = decisions
        self._responder = responder
        self._confidence = confidence or {}

    async def decide(self, request: ProviderRequest) -> ProviderResponse:
        if self._responder is not None:
            decisions = self._responder(request)
        elif self._decisions is not None:
            decisions = dict(self._decisions)
        else:
            decisions = {
                key: _placeholder(question) for key, question in request.task.questions.items()
            }
        return ProviderResponse(
            decisions=decisions,
            confidence=dict(self._confidence),
            model=f"{self.name}-stub",
            latency_ms=0.0,
            raw={"stub": True},
        )


def _placeholder(question: Any) -> Any:
    """The first schema-valid answer for a question type."""
    if isinstance(question, Noul):
        return 0.5
    if isinstance(question, Choice):
        return question.options[0]
    if isinstance(question, Selection):
        return list(question.options[: max(question.min_selected, 1)])
    if isinstance(question, Scalar):
        return (question.minimum + question.maximum) / 2
    if isinstance(question, Score):
        return question.maximum / 2
    if isinstance(question, Rank):
        return list(question.options)
    raise TypeError(f"No placeholder for question type {type(question).__name__}")
