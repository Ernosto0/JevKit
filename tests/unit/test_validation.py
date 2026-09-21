"""Output validation must catch every way a provider can answer wrongly."""

from __future__ import annotations

import pytest

from jevkit.decisions.questions import Choice, Noul, Rank, Scalar, Selection
from jevkit.decisions.task import DecisionTask
from jevkit.validation.validators import validate_decisions


def _task(**questions: object) -> DecisionTask:
    return DecisionTask(name="t", questions=questions)  # type: ignore[arg-type]


def test_valid_answers_pass(routing_task: DecisionTask) -> None:
    report = validate_decisions(routing_task, {"department": "billing", "urgent": 0.7})
    assert report.ok
    assert report.failures == []


def test_missing_answer_is_reported(routing_task: DecisionTask) -> None:
    report = validate_decisions(routing_task, {"department": "billing"})
    assert not report.ok
    assert any("urgent" in f and "missing" in f for f in report.failures)


def test_unknown_key_is_reported(routing_task: DecisionTask) -> None:
    report = validate_decisions(routing_task, {"department": "billing", "urgent": 0.5, "extra": 1})
    assert not report.ok
    assert any("extra" in f for f in report.failures)


def test_choice_rejects_option_outside_the_set(routing_task: DecisionTask) -> None:
    report = validate_decisions(routing_task, {"department": "legal", "urgent": 0.5})
    assert not report.ok
    assert any("legal" in f for f in report.failures)


@pytest.mark.parametrize("value", [-0.1, 1.1, "yes", None, True])
def test_noul_rejects_non_probabilities(value: object) -> None:
    task = _task(urgent=Noul())
    assert not validate_decisions(task, {"urgent": value}).ok


def test_noul_accepts_the_boundaries() -> None:
    task = _task(urgent=Noul())
    assert validate_decisions(task, {"urgent": 0.0}).ok
    assert validate_decisions(task, {"urgent": 1.0}).ok


def test_selection_enforces_membership_and_bounds() -> None:
    task = _task(tags=Selection(options=("a", "b", "c"), min_selected=1, max_selected=2))
    assert validate_decisions(task, {"tags": ["a", "b"]}).ok
    assert not validate_decisions(task, {"tags": []}).ok
    assert not validate_decisions(task, {"tags": ["a", "b", "c"]}).ok
    assert not validate_decisions(task, {"tags": ["a", "z"]}).ok
    assert not validate_decisions(task, {"tags": ["a", "a"]}).ok


def test_scalar_enforces_its_range() -> None:
    task = _task(score=Scalar(minimum=1, maximum=5))
    assert validate_decisions(task, {"score": 3}).ok
    assert validate_decisions(task, {"score": 1}).ok
    assert not validate_decisions(task, {"score": 5.5}).ok
    assert not validate_decisions(task, {"score": "high"}).ok


def test_rank_requires_a_full_permutation() -> None:
    task = _task(order=Rank(options=("a", "b", "c")))
    assert validate_decisions(task, {"order": ["c", "a", "b"]}).ok
    assert not validate_decisions(task, {"order": ["a", "b"]}).ok
    assert not validate_decisions(task, {"order": ["a", "b", "b"]}).ok


def test_question_definitions_reject_bad_configuration() -> None:
    with pytest.raises(ValueError, match="unique"):
        Choice(options=("a", "a"))
    with pytest.raises(ValueError, match="minimum must be strictly less"):
        Scalar(minimum=1.0, maximum=1.0)
    with pytest.raises(ValueError, match="max_selected must be >="):
        Selection(options=("a", "b"), min_selected=2, max_selected=1)
