"""Validate normalized decisions against the questions that produced them.

This runs on every provider result, including fallback results: a fallback is
not assumed to be more trustworthy than the primary (PLAN.md §11).
"""

from __future__ import annotations

from typing import Any

from jevkit.decisions.questions import Choice, Noul, Question, Rank, Scalar, Selection
from jevkit.decisions.task import DecisionTask

__all__ = ["ValidationReport", "validate_decisions"]


class ValidationReport:
    """Result of checking one set of decisions. Falsy when anything failed."""

    def __init__(self, failures: list[str]) -> None:
        self.failures = failures

    @property
    def ok(self) -> bool:
        return not self.failures

    def __bool__(self) -> bool:
        return self.ok

    def __repr__(self) -> str:
        return f"ValidationReport(ok={self.ok}, failures={self.failures!r})"


def validate_decisions(task: DecisionTask, decisions: dict[str, Any]) -> ValidationReport:
    """Check that `decisions` answers every question in `task` with a legal value."""
    failures: list[str] = []

    for key in task.questions:
        if key not in decisions:
            failures.append(f"{key}: missing from provider response")

    for key, value in decisions.items():
        question = task.questions.get(key)
        if question is None:
            failures.append(f"{key}: not a question on task {task.ref}")
            continue
        failures.extend(_check_answer(key, question, value))

    return ValidationReport(failures)


def _check_answer(key: str, question: Question, value: Any) -> list[str]:
    """Return a list of human-readable failures for a single answer."""
    if isinstance(question, Noul):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return [f"{key}: expected a probability, got {type(value).__name__}"]
        if not 0.0 <= float(value) <= 1.0:
            return [f"{key}: probability {value} is outside [0, 1]"]
        return []

    if isinstance(question, Choice):
        if value not in question.options:
            return [f"{key}: {value!r} is not one of {list(question.options)}"]
        return []

    if isinstance(question, Selection):
        if not isinstance(value, (list, tuple, set)):
            return [f"{key}: expected a list of options, got {type(value).__name__}"]
        selected = list(value)
        failures = [
            f"{key}: {item!r} is not one of {list(question.options)}"
            for item in selected
            if item not in question.options
        ]
        if len(set(selected)) != len(selected):
            failures.append(f"{key}: contains duplicate selections")
        if len(selected) < question.min_selected:
            failures.append(f"{key}: selected {len(selected)}, minimum is {question.min_selected}")
        if question.max_selected is not None and len(selected) > question.max_selected:
            failures.append(f"{key}: selected {len(selected)}, maximum is {question.max_selected}")
        return failures

    if isinstance(question, Scalar):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return [f"{key}: expected a number, got {type(value).__name__}"]
        if not question.minimum <= float(value) <= question.maximum:
            return [f"{key}: {value} is outside [{question.minimum}, {question.maximum}]"]
        return []

    if isinstance(question, Rank):
        if not isinstance(value, (list, tuple)):
            return [f"{key}: expected an ordered list, got {type(value).__name__}"]
        ranked = list(value)
        if sorted(map(str, ranked)) != sorted(question.options):
            return [f"{key}: ranking must be a permutation of {list(question.options)}"]
        return []

    # Defensive. mypy proves this is unreachable against today's Question union,
    # but a question type added without a branch above must fail validation
    # loudly rather than pass silently.
    return [  # type: ignore[unreachable]
        f"{key}: unsupported question type {type(question).__name__}"
    ]
