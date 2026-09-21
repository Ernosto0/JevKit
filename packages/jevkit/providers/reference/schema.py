"""Reference-provider wire-format mapping.

Unlike Jev, this adapter targets an OpenAI-compatible Chat Completions API
(`POST {base_url}/chat/completions`) using JSON-schema structured outputs, so
it is not limited to three question types -- it supports the full
provider-agnostic vocabulary in `jevkit.decisions.questions`.

The generated JSON schema deliberately sticks to the keyword subset every
strict-mode implementation accepts (`type`, `properties`, `required`,
`additionalProperties`, `items`, `enum`): numeric ranges and selection/rank
cardinality are described in the prompt instead of enforced by the schema,
and are checked afterwards by `jevkit.validation.validators` like any other
provider's output. A model that ignores the prompt just produces an invalid
response, handled by the normal policy path -- it does not need bespoke
enforcement here.
"""

from __future__ import annotations

import json
from typing import Any

from jevkit.decisions.questions import Choice, Noul, Question, Rank, Scalar, Score, Selection
from jevkit.decisions.result import Usage
from jevkit.decisions.task import DecisionTask

__all__ = ["build_request_payload", "parse_response_payload", "parse_usage"]

_SCHEMA_NAME = "decision"


def build_request_payload(
    task: DecisionTask,
    state: dict[str, Any],
    *,
    model: str,
) -> dict[str, Any]:
    """Translate a JevKit task into an OpenAI-compatible chat completion request."""
    properties: dict[str, Any] = {}
    for key, question in task.questions.items():
        properties[key] = _answer_schema(question)

    response_schema = {
        "type": "object",
        "properties": properties,
        "required": list(task.questions),
        "additionalProperties": False,
    }

    return {
        "model": model,
        "messages": _build_messages(task, state),
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": _SCHEMA_NAME,
                "schema": response_schema,
                "strict": True,
            },
        },
    }


def _answer_schema(question: Question) -> dict[str, Any]:
    """One question's answer as `{"value": ..., "confidence"?: ...}`.

    A `Noul` value already *is* a probability, so no separate confidence is
    requested for it -- mirroring the Jev adapter's treatment of `noul`.
    """
    entry: dict[str, Any] = {
        "type": "object",
        "properties": {"value": _value_schema(question)},
        "required": ["value"],
        "additionalProperties": False,
    }
    if not isinstance(question, Noul):
        entry["properties"]["confidence"] = {
            "type": "number",
            "description": "Self-reported confidence in [0, 1] that `value` is correct.",
        }
        entry["required"].append("confidence")
    return entry


def _value_schema(question: Question) -> dict[str, Any]:
    if isinstance(question, Noul):
        return {
            "type": "number",
            "description": "Probability in [0, 1] that the answer is 'yes'.",
        }
    if isinstance(question, Choice):
        return {"type": "string", "enum": list(question.options)}
    if isinstance(question, Selection):
        return {
            "type": "array",
            "items": {"type": "string", "enum": list(question.options)},
        }
    if isinstance(question, Scalar):
        return {
            "type": "number",
            "description": f"A number in [{question.minimum}, {question.maximum}].",
        }
    if isinstance(question, Score):
        return {
            "type": "number",
            "description": (
                f"Position on the rubric as an unrounded number in [0, {question.maximum}], "
                f"worst to best."
            ),
        }
    if isinstance(question, Rank):
        return {
            "type": "array",
            "items": {"type": "string", "enum": list(question.options)},
            "description": "A permutation of the options, best first.",
        }
    # pragma: no cover - unreachable against today's Question union
    raise TypeError(f"No JSON schema for question type {type(question).__name__}")


def _build_messages(task: DecisionTask, state: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "You are answering structured decision questions about the state below. "
        "Reply with a JSON object holding one entry per question key, each entry "
        "an object with a `value` (and a `confidence` in [0, 1] when asked for one)."
    )
    if task.instructions:
        system = f"{system}\n\n{task.instructions}"

    lines = ["State:", json.dumps(state, ensure_ascii=False, indent=2), "", "Questions:"]
    for key, question in task.questions.items():
        instructions = question.instructions or "(no extra instructions)"
        lines.append(f"- {key} ({question.kind}): {instructions}")
        lines.extend(_question_hint(question))

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(lines)},
    ]


def _question_hint(question: Question) -> list[str]:
    """Extra, human-readable constraints a JSON schema can't express here."""
    if isinstance(question, Noul):
        return [
            "    answer with the probability that the answer is 'yes' "
            f"(threshold {question.threshold})"
        ]
    if isinstance(question, Choice):
        hints = [f"    options: {list(question.options)}"]
        hints.extend(f"      {opt}: {desc}" for opt, desc in question.descriptions.items())
        return hints
    if isinstance(question, Selection):
        upper = question.max_selected
        if upper is None:
            upper = len(question.options)
        return [
            f"    options: {list(question.options)} "
            f"(choose between {question.min_selected} and {upper} of them)"
        ]
    if isinstance(question, Scalar):
        return [f"    range: [{question.minimum}, {question.maximum}]"]
    if isinstance(question, Score):
        return [f"    levels, worst to best: {list(question.levels)}"]
    return [f"    options to rank, best first: {list(question.options)}"]


def parse_response_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, float]]:
    """Split a chat-completion response into (decisions, confidence).

    Raises:
        ProviderResponseError: if the payload is not a well-formed completion,
            the model refused, or its content is not the expected JSON shape.
    """
    from jevkit.errors import ProviderResponseError

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderResponseError(
            "Reference provider response has no 'choices'", provider="reference"
        )

    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ProviderResponseError(
            "Reference provider response has no 'message'", provider="reference"
        )

    refusal = message.get("refusal")
    if refusal:
        raise ProviderResponseError(
            f"Reference model declined to answer: {refusal}", provider="reference"
        )

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ProviderResponseError("Reference provider returned no content", provider="reference")

    try:
        parsed = json.loads(content)
    except ValueError as exc:
        raise ProviderResponseError(
            "Reference provider content was not valid JSON", provider="reference"
        ) from exc

    if not isinstance(parsed, dict):
        raise ProviderResponseError(
            f"Reference provider content was a JSON {type(parsed).__name__}, expected an object",
            provider="reference",
        )

    decisions: dict[str, Any] = {}
    confidence: dict[str, float] = {}
    for key, entry in parsed.items():
        if not isinstance(entry, dict) or "value" not in entry:
            raise ProviderResponseError(
                f"Answer {key!r} has no 'value' field", provider="reference"
            )
        decisions[key] = entry["value"]
        reported = entry.get("confidence")
        if isinstance(reported, (int, float)) and not isinstance(reported, bool):
            confidence[key] = float(reported)

    return decisions, confidence


def parse_usage(payload: dict[str, Any]) -> Usage | None:
    """Pull token usage out of a chat-completion response, if it reported any."""
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None

    def _as_int(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    return Usage(
        input_tokens=_as_int(usage.get("prompt_tokens")),
        output_tokens=_as_int(usage.get("completion_tokens")),
    )
