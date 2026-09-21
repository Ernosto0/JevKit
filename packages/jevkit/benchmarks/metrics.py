"""Evaluation metrics (PLAN.md section 12).

Every function here returns `None` when the metric does not apply to the data
it was given, so a report never shows a number that was not actually measured.
Metrics are computed with the standard library only, keeping the core install
free of a numeric dependency.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "ClassificationMetrics",
    "accuracy",
    "brier_score",
    "calibration_error",
    "classification_metrics",
    "percentile",
]


@dataclass(frozen=True)
class ClassificationMetrics:
    """Per-label precision/recall/F1 plus macro averages."""

    support: dict[str, int]
    precision: dict[str, float]
    recall: dict[str, float]
    f1: dict[str, float]
    macro_precision: float
    macro_recall: float
    macro_f1: float


def accuracy(predicted: Sequence[Any], expected: Sequence[Any]) -> float | None:
    """Share of exactly matching predictions, or None when there is nothing to score."""
    if not predicted or len(predicted) != len(expected):
        return None
    hits = sum(1 for p, e in zip(predicted, expected, strict=True) if p == e)
    return hits / len(expected)


def classification_metrics(
    predicted: Sequence[Any], expected: Sequence[Any]
) -> ClassificationMetrics | None:
    """Precision, recall and F1 per observed label."""
    if not predicted or len(predicted) != len(expected):
        return None

    labels = sorted({str(x) for x in list(expected) + list(predicted)})
    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    f1: dict[str, float] = {}
    support: dict[str, int] = {}

    for label in labels:
        tp = sum(1 for p, e in zip(predicted, expected, strict=True) if str(p) == label == str(e))
        fp = sum(1 for p, e in zip(predicted, expected, strict=True) if str(p) == label != str(e))
        fn = sum(1 for p, e in zip(predicted, expected, strict=True) if str(e) == label != str(p))

        support[label] = tp + fn
        precision[label] = tp / (tp + fp) if (tp + fp) else 0.0
        recall[label] = tp / (tp + fn) if (tp + fn) else 0.0
        denominator = precision[label] + recall[label]
        f1[label] = (2 * precision[label] * recall[label] / denominator) if denominator else 0.0

    n = len(labels)
    return ClassificationMetrics(
        support=support,
        precision=precision,
        recall=recall,
        f1=f1,
        macro_precision=sum(precision.values()) / n,
        macro_recall=sum(recall.values()) / n,
        macro_f1=sum(f1.values()) / n,
    )


def brier_score(probabilities: Sequence[float], outcomes: Sequence[bool]) -> float | None:
    """Mean squared error between predicted probabilities and binary outcomes.

    Lower is better; 0.25 is what constant 0.5 guessing scores on balanced data.
    """
    if not probabilities or len(probabilities) != len(outcomes):
        return None
    return sum(
        (p - (1.0 if o else 0.0)) ** 2 for p, o in zip(probabilities, outcomes, strict=True)
    ) / len(outcomes)


def calibration_error(
    probabilities: Sequence[float], outcomes: Sequence[bool], *, bins: int = 10
) -> float | None:
    """Expected calibration error: support-weighted |confidence - accuracy| per bin.

    A well-calibrated model that says 0.7 is right about 70% of the time. This
    is a measure of agreement, not of correctness.
    """
    if not probabilities or len(probabilities) != len(outcomes) or bins < 1:
        return None

    total = len(probabilities)
    error = 0.0
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        members = [
            (p, o)
            for p, o in zip(probabilities, outcomes, strict=True)
            if (low <= p < high) or (index == bins - 1 and p == 1.0)
        ]
        if not members:
            continue
        mean_confidence = sum(p for p, _ in members) / len(members)
        observed = sum(1 for _, o in members if o) / len(members)
        error += (len(members) / total) * abs(mean_confidence - observed)
    return error


def percentile(values: Sequence[float], q: float) -> float | None:
    """Linear-interpolated percentile, with `q` in [0, 100]."""
    if not values or not 0 <= q <= 100:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * (q / 100)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight
