"""Metrics must be correct on known inputs and absent when inapplicable.

The second property matters as much as the first: a report that silently shows
0.0 for a metric it could not compute is a misleading benchmark
(PLAN.md section 12).
"""

from __future__ import annotations

import pytest

from jevkit.benchmarks.metrics import (
    accuracy,
    brier_score,
    calibration_error,
    classification_metrics,
    percentile,
)


def test_accuracy_on_known_values() -> None:
    assert accuracy(["a", "b", "c", "d"], ["a", "b", "c", "x"]) == pytest.approx(0.75)
    assert accuracy(["a"], ["a"]) == 1.0
    assert accuracy(["a"], ["b"]) == 0.0


def test_accuracy_is_none_when_inapplicable() -> None:
    assert accuracy([], []) is None
    assert accuracy(["a"], ["a", "b"]) is None


def test_classification_metrics_on_a_worked_example() -> None:
    # Label "a": 2 true positives, 1 false positive, 0 false negatives.
    predicted = ["a", "a", "a", "b"]
    expected = ["a", "a", "b", "b"]
    metrics = classification_metrics(predicted, expected)
    assert metrics is not None

    assert metrics.precision["a"] == pytest.approx(2 / 3)
    assert metrics.recall["a"] == pytest.approx(1.0)
    assert metrics.f1["a"] == pytest.approx(0.8)
    assert metrics.support["a"] == 2

    assert metrics.precision["b"] == pytest.approx(1.0)
    assert metrics.recall["b"] == pytest.approx(0.5)
    assert metrics.macro_f1 == pytest.approx((0.8 + 2 / 3) / 2)


def test_classification_metrics_is_none_when_inapplicable() -> None:
    assert classification_metrics([], []) is None
    assert classification_metrics(["a"], []) is None


def test_brier_score_rewards_confident_correct_predictions() -> None:
    assert brier_score([1.0, 0.0], [True, False]) == pytest.approx(0.0)
    assert brier_score([0.0, 1.0], [True, False]) == pytest.approx(1.0)
    assert brier_score([0.5, 0.5], [True, False]) == pytest.approx(0.25)
    assert brier_score([], []) is None


def test_calibration_error_is_zero_for_a_calibrated_predictor() -> None:
    # Says 1.0 and is always right; says 0.0 and is always wrong about "yes".
    error = calibration_error([1.0, 1.0, 0.0, 0.0], [True, True, False, False], bins=2)
    assert error == pytest.approx(0.0)


def test_calibration_error_detects_overconfidence() -> None:
    # Claims 0.9 confidence but is right only half the time.
    error = calibration_error([0.9, 0.9, 0.9, 0.9], [True, True, False, False], bins=10)
    assert error == pytest.approx(0.4)


def test_calibration_error_is_none_when_inapplicable() -> None:
    assert calibration_error([], []) is None
    assert calibration_error([0.5], [True, False]) is None
    assert calibration_error([0.5], [True], bins=0) is None


def test_percentile_interpolates() -> None:
    values = [10.0, 20.0, 30.0, 40.0]
    assert percentile(values, 0) == 10.0
    assert percentile(values, 100) == 40.0
    assert percentile(values, 50) == pytest.approx(25.0)
    assert percentile([5.0], 95) == 5.0
    assert percentile([], 50) is None
    assert percentile([1.0], 150) is None
