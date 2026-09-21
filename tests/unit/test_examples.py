"""The shipped examples must stay loadable and internally consistent.

An example whose dataset labels a question the task does not ask, or whose
labels fall outside the allowed options, would silently produce meaningless
benchmark numbers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jevkit.benchmarks.dataset import BenchmarkDataset
from jevkit.decisions.questions import Choice, Noul, Rank, Scalar, Score, Selection
from jevkit.decisions.task import DecisionTask
from jevkit.validation.validators import validate_decisions

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
EXAMPLE_NAMES = ["support-routing", "agent-routing", "requirement-checks"]


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_task_definition_loads(name: str) -> None:
    path = EXAMPLES / name / "task.json"
    task = DecisionTask.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert task.name == name
    assert task.questions


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_dataset_loads_with_methodology(name: str) -> None:
    dataset = BenchmarkDataset.from_jsonl(EXAMPLES / name / "dataset.jsonl")
    assert len(dataset) > 0
    assert dataset.methodology, "every dataset must document how its labels were made"
    assert {e.id for e in dataset} == {e.id for e in dataset.examples}
    assert len({e.id for e in dataset}) == len(dataset), "example ids must be unique"


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_dataset_labels_are_valid_answers_to_the_task(name: str) -> None:
    task = DecisionTask.model_validate(
        json.loads((EXAMPLES / name / "task.json").read_text(encoding="utf-8"))
    )
    dataset = BenchmarkDataset.from_jsonl(EXAMPLES / name / "dataset.jsonl")

    for example in dataset:
        for field in task.input_fields:
            assert field in example.state, f"{example.id} is missing input field {field!r}"

        for key, label in example.expected.items():
            question = task.questions.get(key)
            assert question is not None, f"{example.id} labels unknown question {key!r}"

            # A Noul is labeled with the boolean outcome, not the probability.
            labeled_as_bool = isinstance(question, Noul) and isinstance(label, bool)
            probe = float(label) if labeled_as_bool else label
            report = validate_decisions(task, {**_full_answer(task), key: probe})
            assert report.ok, f"{example.id}.{key}: {report.failures}"


def _full_answer(task: DecisionTask) -> dict[str, object]:
    """A schema-valid answer for every question, so single keys can be probed."""
    answer: dict[str, object] = {}
    for key, question in task.questions.items():
        if isinstance(question, Noul):
            answer[key] = 0.5
        elif isinstance(question, Choice):
            answer[key] = question.options[0]
        elif isinstance(question, Selection):
            answer[key] = list(question.options[: max(question.min_selected, 0)])
        elif isinstance(question, Scalar):
            answer[key] = question.minimum
        elif isinstance(question, Rank):
            answer[key] = list(question.options)
        elif isinstance(question, Score):
            answer[key] = 0.0
    return answer


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_datasets_are_marked_synthetic(name: str) -> None:
    """These are hand-authored; mislabeling them as real traffic would mislead."""
    dataset = BenchmarkDataset.from_jsonl(EXAMPLES / name / "dataset.jsonl")
    assert dataset.synthetic is True
