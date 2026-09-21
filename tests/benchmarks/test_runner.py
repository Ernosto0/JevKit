"""The benchmark runner, driven by the stub provider.

Marked `benchmark` but offline: these verify that the runner computes what it
claims to compute. A real provider run is a separate, billable activity.
"""

from __future__ import annotations

import pytest

from jevkit.benchmarks.dataset import BenchmarkDataset, DatasetExample
from jevkit.benchmarks.runner import run_benchmark
from jevkit.decisions.questions import Choice, Noul
from jevkit.decisions.task import DecisionTask
from jevkit.policies.policy import DecisionPolicy
from jevkit.providers.base import ProviderRequest
from jevkit.providers.static import StaticProvider

pytestmark = pytest.mark.benchmark

TASK = DecisionTask(
    name="routing",
    input_fields=("message",),
    questions={
        "department": Choice(options=("billing", "technical")),
        "urgent": Noul(),
    },
)

DATASET = BenchmarkDataset(
    name="tiny",
    version="1",
    methodology="Hand-authored for tests only.",
    examples=[
        DatasetExample(
            id="1",
            state={"message": "billing issue"},
            expected={"department": "billing", "urgent": True},
        ),
        DatasetExample(
            id="2",
            state={"message": "app crash"},
            expected={"department": "technical", "urgent": True},
        ),
        DatasetExample(
            id="3",
            state={"message": "billing question"},
            expected={"department": "billing", "urgent": False},
        ),
        DatasetExample(
            id="4",
            state={"message": "how do I export"},
            expected={"department": "technical", "urgent": False},
        ),
    ],
)

POLICY = DecisionPolicy(primary_provider="static", max_retries=0, retry_backoff_seconds=0.0)


def _keyword_provider() -> StaticProvider:
    """Answers "billing" when the message says billing. Gets 4/4 on department."""

    def respond(request: ProviderRequest) -> dict[str, object]:
        message = str(request.state.get("message", "")).lower()
        return {
            "department": "billing" if "billing" in message else "technical",
            "urgent": 0.9 if "issue" in message or "crash" in message else 0.2,
        }

    return StaticProvider(name="keyword", responder=respond)


async def test_report_records_what_was_run() -> None:
    report = await run_benchmark(
        task=TASK, dataset=DATASET, provider=_keyword_provider(), policy=POLICY
    )

    assert report.task_ref == "routing@1"
    assert report.dataset_ref == "tiny@1"
    assert report.provider == "keyword"
    assert report.total_examples == 4
    assert report.policy == POLICY


async def test_accuracy_matches_the_known_answers() -> None:
    report = await run_benchmark(
        task=TASK, dataset=DATASET, provider=_keyword_provider(), policy=POLICY
    )
    by_question = {q.question: q for q in report.questions}

    # "billing issue" / "billing question" -> billing; the other two -> technical.
    assert by_question["department"].accuracy == pytest.approx(1.0)
    assert by_question["department"].macro_f1 == pytest.approx(1.0)
    # urgent: "issue"/"crash" -> 0.9, others -> 0.2; thresholded at 0.5 this
    # matches all four labels.
    assert by_question["urgent"].accuracy == pytest.approx(1.0)
    # (0.1^2)*2 + (0.2^2)*2, over 4
    assert by_question["urgent"].brier_score == pytest.approx(0.025)
    assert by_question["urgent"].calibration_error is not None


async def test_wrong_answers_lower_the_score() -> None:
    """A provider that always says "urgent" gets exactly half the labels right."""
    always_urgent = StaticProvider(
        name="always-urgent",
        responder=lambda request: {
            "department": "billing" if "billing" in str(request.state["message"]) else "technical",
            "urgent": 0.95,
        },
    )
    report = await run_benchmark(task=TASK, dataset=DATASET, provider=always_urgent, policy=POLICY)
    by_question = {q.question: q for q in report.questions}

    assert by_question["urgent"].accuracy == pytest.approx(0.5)
    # Confidently wrong half the time: a much worse Brier score.
    # (0.05^2)*2 + (0.95^2)*2, over 4
    assert by_question["urgent"].brier_score == pytest.approx(0.4525)


async def test_invalid_answers_are_excluded_and_counted() -> None:
    """An unparseable answer lowers coverage instead of scoring as wrong."""
    broken = StaticProvider({"department": "legal", "urgent": 0.5}, name="broken")
    report = await run_benchmark(task=TASK, dataset=DATASET, provider=broken, policy=POLICY)

    assert report.accepted == 0
    assert report.coverage == 0.0
    assert report.invalid_response_rate == 1.0
    assert all(q.scored == 0 for q in report.questions)
    assert all(q.accuracy is None for q in report.questions)


async def test_latency_percentiles_are_recorded() -> None:
    report = await run_benchmark(
        task=TASK, dataset=DATASET, provider=_keyword_provider(), policy=POLICY
    )
    assert report.latency_p50_ms is not None
    assert report.latency_p95_ms is not None


async def test_summary_lines_render() -> None:
    report = await run_benchmark(
        task=TASK, dataset=DATASET, provider=_keyword_provider(), policy=POLICY
    )
    text = "\n".join(report.summary_lines())
    assert "routing@1" in text
    assert "tiny@1" in text


async def test_dataset_roundtrips_through_jsonl(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "tiny.jsonl"
    DATASET.to_jsonl(path)
    reloaded = BenchmarkDataset.from_jsonl(path)

    assert reloaded.ref == DATASET.ref
    assert reloaded.methodology == DATASET.methodology
    assert [e.id for e in reloaded] == [e.id for e in DATASET]
