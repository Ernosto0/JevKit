"""The decision execution engine (PLAN.md section 10).

Implements the lifecycle exactly once, so the SDK, the CLI and the FastAPI
service all behave identically::

    receive -> validate input -> resolve policy -> select provider -> execute
    -> parse -> validate output -> apply acceptance policy -> trace -> return
"""

from __future__ import annotations

import asyncio
from typing import Any

from jevkit.decisions.result import DecisionResult, ExecutionStatus, ValidationStatus
from jevkit.decisions.task import DecisionTask
from jevkit.errors import ProviderError
from jevkit.policies.policy import DecisionPolicy, OnFailure
from jevkit.providers.base import ModelProvider, ProviderRequest, ProviderResponse
from jevkit.tracing.recorder import NullTraceRecorder, TraceRecorder
from jevkit.tracing.trace import DecisionTrace, TraceStage
from jevkit.validation.validators import validate_decisions

__all__ = ["DecisionEngine"]

_FALLBACK_TRIGGERS = frozenset({OnFailure.FALLBACK, OnFailure.RETRY_THEN_FALLBACK})


class DecisionEngine:
    """Runs one decision under an explicit policy, recording a trace."""

    def __init__(
        self,
        *,
        primary: ModelProvider,
        fallback: ModelProvider | None = None,
        policy: DecisionPolicy | None = None,
        recorder: TraceRecorder | None = None,
        store_inputs: bool = False,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.policy = policy or DecisionPolicy(
            primary_provider=primary.name,
            fallback_provider=fallback.name if fallback else None,
        )
        self.recorder = recorder or NullTraceRecorder()
        self.store_inputs = store_inputs

    async def run(
        self,
        task: DecisionTask,
        state: dict[str, Any],
        *,
        policy: DecisionPolicy | None = None,
    ) -> tuple[DecisionResult, DecisionTrace]:
        """Execute `task` against `state`, returning the result and its trace."""
        active = policy or self.policy
        trace = DecisionTrace(task_ref=task.ref, state=dict(state) if self.store_inputs else None)
        trace.record(TraceStage.RECEIVED, questions=sorted(task.questions))

        task.validate_state(dict(state))
        trace.record(TraceStage.INPUT_VALIDATED)
        trace.record(
            TraceStage.POLICY_RESOLVED,
            primary=active.primary_provider,
            fallback=active.fallback_provider,
            max_retries=active.max_retries,
            timeout_seconds=active.timeout_seconds,
        )

        result = await self._attempt_provider(
            self.primary, task, state, active, trace, is_fallback=False
        )

        if result is None and self._should_fallback(active) and self.fallback is not None:
            trace.record(TraceStage.FALLBACK, provider=self.fallback.name)
            result = await self._attempt_provider(
                self.fallback, task, state, active, trace, is_fallback=True
            )

        if result is None:
            result = DecisionResult(
                task_ref=task.ref,
                provider=active.primary_provider,
                execution_status=ExecutionStatus.FAILED,
                validation_status=ValidationStatus.NOT_RUN,
                trace_id=trace.trace_id,
            )
            trace.record(TraceStage.FAILED)
        else:
            trace.record(TraceStage.COMPLETED, status=result.execution_status.value)

        self.recorder.save(trace)
        return result, trace

    async def _attempt_provider(
        self,
        provider: ModelProvider,
        task: DecisionTask,
        state: dict[str, Any],
        policy: DecisionPolicy,
        trace: DecisionTrace,
        *,
        is_fallback: bool,
    ) -> DecisionResult | None:
        """Call one provider, retrying within the policy's bounded budget.

        Returns None when this provider produced nothing acceptable, which hands
        control back to `run` to decide about fallback.
        """
        trace.record(TraceStage.PROVIDER_SELECTED, provider=provider.name, fallback=is_fallback)
        request = ProviderRequest(
            task=task,
            state=dict(state),
            timeout_seconds=policy.timeout_seconds,
            trace_id=trace.trace_id,
        )

        for attempt in range(1, policy.max_retries + 2):
            trace.record(TraceStage.PROVIDER_CALL, provider=provider.name, attempt=attempt)
            try:
                response = await asyncio.wait_for(
                    provider.decide(request), timeout=policy.timeout_seconds
                )
            except (ProviderError, TimeoutError) as exc:
                retryable = isinstance(exc, TimeoutError) or getattr(exc, "retryable", False)
                trace.record(
                    TraceStage.FAILED,
                    provider=provider.name,
                    attempt=attempt,
                    error=type(exc).__name__,
                    retryable=retryable,
                )
                if retryable and attempt <= policy.max_retries:
                    trace.record(TraceStage.RETRY, attempt=attempt + 1, reason="provider_error")
                    await asyncio.sleep(policy.retry_backoff_seconds * attempt)
                    continue
                return None

            trace.record(TraceStage.RESPONSE_PARSED, provider=provider.name, model=response.model)
            report = validate_decisions(task, response.decisions)
            trace.record(TraceStage.OUTPUT_VALIDATED, ok=report.ok, failures=report.failures)

            if not report.ok:
                if policy.on_invalid_response is OnFailure.RETRY and attempt <= policy.max_retries:
                    trace.record(TraceStage.RETRY, attempt=attempt + 1, reason="invalid_response")
                    continue
                if policy.on_invalid_response is OnFailure.REVIEW:
                    return self._build_result(
                        task,
                        response,
                        provider,
                        trace,
                        attempt,
                        is_fallback,
                        status=ExecutionStatus.NEEDS_REVIEW,
                        validation=ValidationStatus.INVALID,
                        failures=report.failures,
                    )
                return None

            status = ExecutionStatus.FALLBACK_ACCEPTED if is_fallback else ExecutionStatus.ACCEPTED
            if self._is_low_confidence(response, policy):
                trace.record(TraceStage.OUTPUT_VALIDATED, low_confidence=True)
                action = policy.on_low_confidence
                if action is OnFailure.REVIEW:
                    status = ExecutionStatus.NEEDS_REVIEW
                elif action is OnFailure.FAIL:
                    status = ExecutionStatus.REJECTED
                elif action in _FALLBACK_TRIGGERS and not is_fallback and policy.fallback_allowed():
                    return None

            return self._build_result(
                task,
                response,
                provider,
                trace,
                attempt,
                is_fallback,
                status=status,
                validation=ValidationStatus.VALID,
                failures=[],
            )

        return None

    @staticmethod
    def _is_low_confidence(response: ProviderResponse, policy: DecisionPolicy) -> bool:
        """Low confidence is a policy judgement, never a correctness signal."""
        if policy.min_confidence is None or not response.confidence:
            return False
        return min(response.confidence.values()) < policy.min_confidence

    @staticmethod
    def _should_fallback(policy: DecisionPolicy) -> bool:
        if not policy.fallback_allowed():
            return False
        configured = {policy.on_provider_error, policy.on_timeout, policy.on_invalid_response}
        return bool(configured & _FALLBACK_TRIGGERS)

    @staticmethod
    def _build_result(
        task: DecisionTask,
        response: ProviderResponse,
        provider: ModelProvider,
        trace: DecisionTrace,
        attempts: int,
        is_fallback: bool,
        *,
        status: ExecutionStatus,
        validation: ValidationStatus,
        failures: list[str],
    ) -> DecisionResult:
        latency = response.latency_ms if response.latency_ms is not None else trace.duration_ms
        return DecisionResult(
            decisions=response.decisions,
            confidence=response.confidence,
            task_ref=task.ref,
            provider=provider.name,
            model=response.model,
            execution_status=status,
            validation_status=validation,
            validation_failures=tuple(failures),
            attempts=attempts,
            used_fallback=is_fallback,
            latency_ms=latency,
            usage=response.usage,
            trace_id=trace.trace_id,
            raw_response=response.raw,
        )
