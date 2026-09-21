"""Shared fixtures.

No test in `tests/unit` may touch the network. Integration tests are marked and
skipped unless credentials are present.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jevkit.decisions.questions import Choice, Noul
from jevkit.decisions.task import DecisionTask
from jevkit.policies.policy import DecisionPolicy
from jevkit.providers.static import StaticProvider

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"


@pytest.fixture
def routing_task() -> DecisionTask:
    """A two-question task covering both a Choice and a Noul."""
    return DecisionTask(
        name="support-routing",
        version="1",
        input_fields=("message",),
        questions={
            "department": Choice(options=("billing", "technical", "account", "other")),
            "urgent": Noul(instructions="Is this urgent?"),
        },
    )


@pytest.fixture
def good_provider() -> StaticProvider:
    """Returns a valid answer for `routing_task`."""
    return StaticProvider(
        {"department": "billing", "urgent": 0.9},
        name="good",
        confidence={"urgent": 0.9},
    )


@pytest.fixture
def bad_provider() -> StaticProvider:
    """Returns an option that is not in the task's allowed set."""
    return StaticProvider({"department": "legal", "urgent": 0.4}, name="bad")


@pytest.fixture
def strict_policy() -> DecisionPolicy:
    """No retries, no fallback: makes failure paths deterministic."""
    return DecisionPolicy(primary_provider="static", max_retries=0, retry_backoff_seconds=0.0)


@pytest.fixture
def example_task_paths() -> list[Path]:
    return sorted(EXAMPLES.glob("*/task.json"))


@pytest.fixture
def example_dataset_paths() -> list[Path]:
    return sorted(EXAMPLES.glob("*/dataset.jsonl"))


@pytest.fixture
def load_example_task():
    def _load(name: str) -> DecisionTask:
        path = EXAMPLES / name / "task.json"
        return DecisionTask.model_validate(json.loads(path.read_text(encoding="utf-8")))

    return _load
