"""The provider abstraction (PLAN.md §8).

Everything provider-specific lives behind this interface so that the engine,
the policies, the validators and the benchmarks never depend on one vendor's
wire format.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from jevkit.decisions.result import Usage
from jevkit.decisions.task import DecisionTask

__all__ = ["ModelProvider", "ProviderRequest", "ProviderResponse"]


class ProviderRequest(BaseModel):
    """A normalized decision request handed to a provider adapter."""

    model_config = ConfigDict(frozen=True)

    task: DecisionTask
    state: dict[str, Any]
    timeout_seconds: float = 10.0
    trace_id: str | None = None


class ProviderResponse(BaseModel):
    """A provider's reply, already normalized into JevKit's vocabulary.

    Adapters are responsible for turning a vendor payload into this shape and
    for raising a typed `ProviderError` when they cannot.
    """

    model_config = ConfigDict(frozen=True)

    decisions: dict[str, Any] = Field(default_factory=dict)
    confidence: dict[str, float] = Field(default_factory=dict)
    model: str | None = None
    latency_ms: float | None = None
    usage: Usage | None = None
    raw: dict[str, Any] | None = None


class ModelProvider(ABC):
    """Base class for every provider adapter.

    Implementations must:
      * be async and honour `request.timeout_seconds`;
      * raise the typed errors in `jevkit.errors` rather than vendor exceptions;
      * never retry internally -- retries belong to the policy engine;
      * never log or return credentials.
    """

    #: Stable identifier recorded in traces and benchmark runs, e.g. "jev".
    name: str = "unnamed"

    @abstractmethod
    async def decide(self, request: ProviderRequest) -> ProviderResponse:
        """Execute one decision request."""
        raise NotImplementedError

    async def aclose(self) -> None:
        """Release transport resources. Safe to call more than once."""
        return None

    async def __aenter__(self) -> ModelProvider:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r}>"
