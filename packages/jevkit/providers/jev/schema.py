"""Jev wire-format mapping.

Verified against the live API on 2026-09-21 (`jev-1.13.0`). The captured
request/response pairs and the reasoning behind each mapping decision are in
docs/jev-api-notes.md; regenerate them with `scripts/verify_jev_api.py`.

Everything Jev-specific is confined to this file on purpose, so correcting it
does not touch the engine, policies or benchmarks.

Do not add fields here that are not in the official documentation.
"""

from __future__ import annotations

from typing import Any

from jevkit.decisions.questions import Choice, Noul, Score
from jevkit.decisions.result import Usage
from jevkit.decisions.task import DecisionTask

__all__ = [
    "SCHEMA_VERIFIED",
    "SUPPORTED_QUESTION_KINDS",
    "VERIFIED_AGAINST",
    "build_request_payload",
    "parse_response_payload",
    "parse_usage",
]

SCHEMA_VERIFIED = True
"""This mapping was exercised against the live API, not just the docs."""

VERIFIED_AGAINST = "jev-1.13.0"
"""Model version the mapping was confirmed against."""

SUPPORTED_QUESTION_KINDS = ("noul", "choice", "score")
"""The only question types Jev accepts. Anything else is a 400 from the API."""


def build_request_payload(
    task: DecisionTask,
    state: dict[str, Any],
    *,
    model: str,
) -> dict[str, Any]:
    """Translate a JevKit task into a Jev request body.

    Args:
        task: the decision task; every question must be Jev-supported.
        state: the material being judged. Sent as a JSON object.
        model: required by the API -- omitting it is a 422.

    Raises:
        TaskDefinitionError: if the task uses a question type Jev cannot answer.
    """
    from jevkit.errors import TaskDefinitionError

    questions: dict[str, Any] = {}

    for key, question in task.questions.items():
        # Jev has no task-level instruction slot -- sending one top-level is a
        # 400. Questions are evaluated independently against the same state, so
        # shared context has to ride along on each question instead.
        instructions = _compose_instructions(task.instructions, question.instructions)

        if isinstance(question, Noul):
            entry: dict[str, Any] = {"type": "noul"}
        elif isinstance(question, Choice):
            entry = {
                "type": "choice",
                # Null descriptions are accepted; the option name still carries
                # meaning. Callers who supply descriptions get better answers.
                "criteria": {opt: question.descriptions.get(opt) for opt in question.options},
            }
        elif isinstance(question, Score):
            entry = {"type": "score", "criteria": list(question.levels)}
        else:
            raise TaskDefinitionError(
                f"Question {key!r} is a {type(question).__name__}, which Jev cannot answer. "
                f"Jev supports {', '.join(SUPPORTED_QUESTION_KINDS)} "
                f"(Noul, Choice, Score). Use a different provider for this question."
            )

        # A question with neither instructions nor criteria is a 400.
        if instructions:
            entry["instructions"] = instructions
        elif "criteria" not in entry:
            raise TaskDefinitionError(
                f"Question {key!r} needs instructions: Jev rejects a noul with "
                f"neither instructions nor criteria."
            )

        questions[key] = entry

    return {"state": state, "model": model, "questions": questions}


def _compose_instructions(task_level: str | None, question_level: str | None) -> str | None:
    """Fold task-wide context into a single question's instructions."""
    parts = [p for p in (task_level, question_level) if p]
    return "\n\n".join(parts) if parts else None


def parse_response_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, float]]:
    """Split a Jev response into (decisions, confidence).

    The value of each answer lives under a key named after its question type --
    there is no generic `value` field:

        {"answers": {"urgent":   {"type": "noul",   "noul": 0.91},
                     "dept":     {"type": "choice", "choice": "billing",
                                  "confidence": 1.0, "probabilities": {...}},
                     "severity": {"type": "score",  "score": 2.94,
                                  "confidence": 0.94, "legend": {...}}}}

    `noul` answers carry no `confidence` field -- the probability *is* the
    answer -- so they contribute no confidence entry. An absent entry means the
    provider reported none, not that confidence was low.

    Raises:
        ProviderResponseError: if the payload is not a well-formed answer map.
    """
    from jevkit.errors import ProviderResponseError

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        got = type(answers).__name__ if answers is not None else "nothing"
        raise ProviderResponseError(
            f"Jev response has no 'answers' object (got {got})",
            provider="jev",
        )

    decisions: dict[str, Any] = {}
    confidence: dict[str, float] = {}

    for key, answer in answers.items():
        if not isinstance(answer, dict):
            raise ProviderResponseError(
                f"Answer {key!r} is a {type(answer).__name__}, expected an object",
                provider="jev",
            )

        kind = answer.get("type")
        if kind not in SUPPORTED_QUESTION_KINDS:
            raise ProviderResponseError(
                f"Answer {key!r} has unknown type {kind!r}",
                provider="jev",
            )

        # The value is stored under a key named after the type.
        if kind not in answer:
            raise ProviderResponseError(
                f"Answer {key!r} of type {kind!r} has no {kind!r} field",
                provider="jev",
            )
        decisions[key] = answer[kind]

        reported = answer.get("confidence")
        if isinstance(reported, (int, float)) and not isinstance(reported, bool):
            confidence[key] = float(reported)

    return decisions, confidence


def parse_usage(payload: dict[str, Any]) -> Usage | None:
    """Pull token usage out of a Jev response, if it reported any."""
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None

    def _as_int(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    return Usage(
        input_tokens=_as_int(usage.get("input_tokens")),
        output_tokens=_as_int(usage.get("output_tokens")),
    )
