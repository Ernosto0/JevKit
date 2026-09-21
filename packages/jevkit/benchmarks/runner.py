"""Benchmark runner (PLAN.md section 12).

Runs one task over one labeled dataset with one provider, under bounded
concurrency, and records everything needed to reproduce the run: provider,
model, task ref, dataset ref, policy, and date.

Comparing providers means calling `run_benchmark` once per provider with the
*same* dataset and the *same* policy.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from jevkit.benchmarks.dataset import BenchmarkDataset, DatasetExample
from jevkit.benchmarks.metrics import (
    accuracy,
    brier_score,
    calibration_error,
    classification_metrics,
    percentile,
)
from jevkit.client.engine import DecisionEngine
from jevkit.decisions.questions import Noul
from jevkit.decisions.result import DecisionResult
from jevkit.decisions.task import DecisionTask
from jevkit.policies.policy import DecisionPolicy
from jevkit.providers.base import ModelProvider

__all__ = ["BenchmarkReport", "ExampleOutcome", "QuestionMetrics", "run_benchmark"]


class ExampleOutcome(BaseModel):
    """What happened for one example."""

    model_config = ConfigDict(extra="forbid")

    example_id: str
    accepted: bool
    decisions: dict[str, Any] = Field(default_factory=dict)
    confidence: dict[str, float] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float | None = None
    used_fallback: bool = False
    error: str | None = None


class QuestionMetrics(BaseModel):
    """Metrics for a single question. Absent values were not applicable."""

    model_config = ConfigDict(extra="forbid")

    question: str
    scored: int
    accuracy: float | None = None
    macro_precision: float | None = None
    macro_recall: float | None = None
    macro_f1: float | None = None
    brier_score: float | None = None
    calibration_error: float | None = None


class BenchmarkReport(BaseModel):
    """A reproducible record of one benchmark run.

    Contains only measured values. An empty metric means it was not applicable
    to this dataset, not that the provider scored zero.
    """

    model_config = ConfigDict(extra="forbid")

    task_ref: str
    dataset_ref: str
    provider: str
    model: str | None = None
    run_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    policy: DecisionPolicy

    total_examples: int
    accepted: int
    invalid_response_rate: float
    fallback_rate: float
    coverage: float

    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None
    total_cost_usd: float | None = None
    cost_per_1k_decisions_usd: float | None = None

    questions: list[QuestionMetrics] = Field(default_factory=list)
    outcomes: list[ExampleOutcome] = Field(default_factory=list)

    def summary_lines(self) -> list[str]:
        """Compact, human-readable summary for CLI output."""
        lines = [
            f"task     {self.task_ref}",
            f"dataset  {self.dataset_ref} ({self.total_examples} examples)",
            f"provider {self.provider}" + (f" / {self.model}" if self.model else ""),
            f"coverage {self.coverage:.1%}  invalid {self.invalid_response_rate:.1%}"
            f"  fallback {self.fallback_rate:.1%}",
        ]
        if self.latency_p50_ms is not None:
            lines.append(
                f"latency  p50 {self.latency_p50_ms:.0f}ms  p95 {self.latency_p95_ms or 0:.0f}ms"
            )
        for q in self.questions:
            parts = [f"  {q.question}: n={q.scored}"]
            if q.accuracy is not None:
                parts.append(f"acc={q.accuracy:.3f}")
            if q.macro_f1 is not None:
                parts.append(f"f1={q.macro_f1:.3f}")
            if q.brier_score is not None:
                parts.append(f"brier={q.brier_score:.3f}")
            if q.calibration_error is not None:
                parts.append(f"ece={q.calibration_error:.3f}")
            lines.append(" ".join(parts))
        return lines


async def run_benchmark(
    *,
    task: DecisionTask,
    dataset: BenchmarkDataset,
    provider: ModelProvider,
    policy: DecisionPolicy | None = None,
    fallback: ModelProvider | None = None,
    concurrency: int = 4,
) -> BenchmarkReport:
    """Run `task` over `dataset` with `provider` and return a measured report."""
    active = policy or DecisionPolicy(
        primary_provider=provider.name,
        fallback_provider=fallback.name if fallback else None,
    )
    engine = DecisionEngine(primary=provider, fallback=fallback, policy=active)
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run_one(example: DatasetExample) -> ExampleOutcome:
        async with semaphore:
            try:
                result, _trace = await engine.run(task, example.state, policy=active)
            except Exception as exc:
                return ExampleOutcome(
                    example_id=example.id,
                    accepted=False,
                    expected=example.expected,
                    error=f"{type(exc).__name__}: {exc}",
                )
            return _to_outcome(example, result)

    outcomes = list(await asyncio.gather(*(run_one(e) for e in dataset.examples)))
    return _build_report(
        task=task, dataset=dataset, provider=provider, policy=active, outcomes=outcomes
    )


def _to_outcome(example: DatasetExample, result: DecisionResult) -> ExampleOutcome:
    return ExampleOutcome(
        example_id=example.id,
        accepted=result.accepted,
        decisions=result.decisions,
        confidence=result.confidence,
        expected=example.expected,
        latency_ms=result.latency_ms,
        used_fallback=result.used_fallback,
        error=None if result.accepted else "; ".join(result.validation_failures) or None,
    )


def _build_report(
    *,
    task: DecisionTask,
    dataset: BenchmarkDataset,
    provider: ModelProvider,
    policy: DecisionPolicy,
    outcomes: list[ExampleOutcome],
) -> BenchmarkReport:
    total = len(outcomes)
    accepted = [o for o in outcomes if o.accepted]
    latencies = [o.latency_ms for o in outcomes if o.latency_ms is not None]
    invalid = sum(1 for o in outcomes if not o.accepted)

    return BenchmarkReport(
        task_ref=task.ref,
        dataset_ref=dataset.ref,
        provider=provider.name,
        model=next((o.decisions.get("__model__") for o in accepted if o.decisions), None),
        policy=policy,
        total_examples=total,
        accepted=len(accepted),
        invalid_response_rate=(invalid / total) if total else 0.0,
        fallback_rate=(sum(1 for o in outcomes if o.used_fallback) / total) if total else 0.0,
        coverage=(len(accepted) / total) if total else 0.0,
        latency_p50_ms=percentile(latencies, 50),
        latency_p95_ms=percentile(latencies, 95),
        questions=[_question_metrics(task, key, accepted) for key in task.questions],
        outcomes=outcomes,
    )


def _question_metrics(
    task: DecisionTask, key: str, accepted: list[ExampleOutcome]
) -> QuestionMetrics:
    """Score one question over the accepted outcomes that carry a label for it."""
    scored = [o for o in accepted if key in o.expected and key in o.decisions]
    predicted = [o.decisions[key] for o in scored]
    expected = [o.expected[key] for o in scored]

    metrics = QuestionMetrics(question=key, scored=len(scored))
    if not scored:
        return metrics

    question = task.questions[key]
    if isinstance(question, Noul):
        # A Noul answer is a probability: threshold it for accuracy, and score
        # the raw probability for Brier/calibration.
        probabilities = [float(p) for p in predicted]
        outcomes = [bool(e) for e in expected]
        thresholded = [p >= question.threshold for p in probabilities]
        return metrics.model_copy(
            update={
                "accuracy": accuracy(thresholded, outcomes),
                "brier_score": brier_score(probabilities, outcomes),
                "calibration_error": calibration_error(probabilities, outcomes),
            }
        )

    update: dict[str, Any] = {"accuracy": accuracy(predicted, expected)}
    classification = classification_metrics(predicted, expected)
    if classification is not None:
        update |= {
            "macro_precision": classification.macro_precision,
            "macro_recall": classification.macro_recall,
            "macro_f1": classification.macro_f1,
        }
    return metrics.model_copy(update=update)
