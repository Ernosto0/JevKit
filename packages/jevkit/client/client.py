"""The public SDK surface (PLAN.md section 9).

`DecisionClient` is the one object most users touch. It is async-first, takes
explicit types, and never retries beyond the configured policy.
"""

from __future__ import annotations

from typing import Any

from jevkit.client.engine import DecisionEngine
from jevkit.config import JevKitSettings, get_settings
from jevkit.decisions.questions import Question
from jevkit.decisions.result import DecisionResult
from jevkit.decisions.task import DecisionTask
from jevkit.policies.policy import DecisionPolicy
from jevkit.providers.base import ModelProvider
from jevkit.providers.registry import build_provider
from jevkit.tracing.recorder import NullTraceRecorder, TraceRecorder
from jevkit.tracing.trace import DecisionTrace

__all__ = ["DecisionClient"]

_AD_HOC_TASK = "ad-hoc"


class DecisionClient:
    """Submit structured decisions and get validated, traced results back.

    Typical use::

        client = DecisionClient.from_env()
        result = await client.decide(
            state={"message": "I was charged twice."},
            questions={"department": Choice(options=["billing", "technical"])},
        )
    """

    def __init__(
        self,
        *,
        provider: ModelProvider,
        fallback: ModelProvider | None = None,
        policy: DecisionPolicy | None = None,
        recorder: TraceRecorder | None = None,
        store_inputs: bool = False,
    ) -> None:
        self._engine = DecisionEngine(
            primary=provider,
            fallback=fallback,
            policy=policy,
            recorder=recorder or NullTraceRecorder(),
            store_inputs=store_inputs,
        )

    # -- construction ------------------------------------------------------

    @classmethod
    def from_env(
        cls,
        *,
        settings: JevKitSettings | None = None,
        policy: DecisionPolicy | None = None,
        recorder: TraceRecorder | None = None,
    ) -> DecisionClient:
        """Build a client from environment configuration.

        Raises:
            ConfigurationError: if the primary provider has no credentials.
        """
        cfg = settings or get_settings()
        active = policy or DecisionPolicy(
            timeout_seconds=cfg.timeout_seconds,
            max_retries=cfg.max_retries,
            fallback_provider=cfg.fallback_provider,
        )
        primary = build_provider(active.primary_provider, settings=cfg)
        fallback = (
            build_provider(active.fallback_provider, settings=cfg)
            if active.fallback_provider
            else None
        )
        return cls(
            provider=primary,
            fallback=fallback,
            policy=active,
            recorder=recorder,
            store_inputs=cfg.trace_store_inputs,
        )

    # -- execution ---------------------------------------------------------

    async def decide(
        self,
        *,
        state: dict[str, Any],
        questions: dict[str, Question] | None = None,
        task: DecisionTask | None = None,
        policy: DecisionPolicy | None = None,
    ) -> DecisionResult:
        """Run one decision.

        Pass either `questions` (an ad-hoc task) or a reusable `task`.
        Benchmarks and stored runs should always use a named `task`, since the
        task ref is what makes a run identifiable later.
        """
        resolved = self._resolve_task(task, questions)
        result, _trace = await self._engine.run(resolved, state, policy=policy)
        return result

    async def decide_with_trace(
        self,
        *,
        state: dict[str, Any],
        questions: dict[str, Question] | None = None,
        task: DecisionTask | None = None,
        policy: DecisionPolicy | None = None,
    ) -> tuple[DecisionResult, DecisionTrace]:
        """Same as `decide`, but also returns the full execution trace."""
        resolved = self._resolve_task(task, questions)
        return await self._engine.run(resolved, state, policy=policy)

    @staticmethod
    def _resolve_task(
        task: DecisionTask | None, questions: dict[str, Question] | None
    ) -> DecisionTask:
        from jevkit.errors import TaskDefinitionError

        if task is not None and questions is not None:
            raise TaskDefinitionError("Pass either `task` or `questions`, not both")
        if task is not None:
            return task
        if not questions:
            raise TaskDefinitionError("A decision needs at least one question")
        return DecisionTask(name=_AD_HOC_TASK, questions=questions)

    # -- lifecycle ---------------------------------------------------------

    async def aclose(self) -> None:
        """Close the underlying provider transports."""
        await self._engine.primary.aclose()
        if self._engine.fallback is not None:
            await self._engine.fallback.aclose()

    async def __aenter__(self) -> DecisionClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
