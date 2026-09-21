"""Jev wire-format mapping.

    ┌──────────────────────────────────────────────────────────────────────┐
    │  PROVISIONAL -- NOT YET VERIFIED AGAINST THE OFFICIAL JEV API.       │
    │  Phase 1 of the roadmap (PLAN.md §20) exists to replace the two      │
    │  functions below with the documented request and response schema.    │
    │  Everything Jev-specific is confined to this file on purpose, so     │
    │  correcting it does not touch the engine, policies or benchmarks.    │
    └──────────────────────────────────────────────────────────────────────┘

Do not add fields here that are not in the official documentation.
"""

from __future__ import annotations

from typing import Any

from jevkit.decisions.questions import Choice, Noul, Rank, Scalar, Selection
from jevkit.decisions.task import DecisionTask

__all__ = ["SCHEMA_VERIFIED", "build_request_payload", "parse_response_payload"]

SCHEMA_VERIFIED = False
"""Flip to True only once this mapping matches the official API documentation."""


def build_request_payload(task: DecisionTask, state: dict[str, Any]) -> dict[str, Any]:
    """Translate a JevKit task into a Jev request body."""
    questions: dict[str, Any] = {}

    for key, question in task.questions.items():
        entry: dict[str, Any] = {"type": question.kind}
        if question.instructions:
            entry["instructions"] = question.instructions

        if isinstance(question, (Choice, Selection, Rank)):
            entry["options"] = list(question.options)
        if isinstance(question, Selection):
            entry["min_selected"] = question.min_selected
            if question.max_selected is not None:
                entry["max_selected"] = question.max_selected
        if isinstance(question, Scalar):
            entry["minimum"] = question.minimum
            entry["maximum"] = question.maximum
        if isinstance(question, Noul):
            pass  # Noul carries no extra wire fields; threshold is applied locally.

        questions[key] = entry

    payload: dict[str, Any] = {"state": state, "questions": questions}
    if task.instructions:
        payload["instructions"] = task.instructions
    return payload


def parse_response_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, float]]:
    """Split a Jev response into (decisions, confidence).

    Accepts either a flat `{key: value}` map or `{key: {"value": v,
    "probability": p}}`, since the exact shape is still unverified.

    Raises:
        ProviderResponseError: if the payload is not a decision map at all.
    """
    from jevkit.errors import ProviderResponseError

    body = payload.get("decisions", payload)
    if not isinstance(body, dict):
        raise ProviderResponseError(
            f"Expected a decision map in the Jev response, got {type(body).__name__}",
            provider="jev",
        )

    decisions: dict[str, Any] = {}
    confidence: dict[str, float] = {}

    for key, raw in body.items():
        if isinstance(raw, dict):
            if "value" not in raw:
                raise ProviderResponseError(
                    f"Decision {key!r} has no 'value' field in the Jev response",
                    provider="jev",
                )
            decisions[key] = raw["value"]
            for prob_field in ("probability", "confidence"):
                if isinstance(raw.get(prob_field), (int, float)):
                    confidence[key] = float(raw[prob_field])
                    break
        else:
            decisions[key] = raw
            if isinstance(raw, float) and 0.0 <= raw <= 1.0:
                # A bare Noul answer is itself a probability.
                confidence[key] = raw

    return decisions, confidence
