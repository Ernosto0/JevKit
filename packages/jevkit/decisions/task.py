"""Reusable decision task definitions (PLAN.md §8)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jevkit.decisions.questions import Question

__all__ = ["DecisionTask"]


class DecisionTask(BaseModel):
    """A named, versioned decision with a fixed set of questions.

    A task is the unit that gets benchmarked, so `name` + `version` must
    identify it unambiguously in a stored run.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    version: str = Field(default="1", min_length=1)
    description: str | None = None

    questions: dict[str, Question] = Field(min_length=1)

    input_fields: tuple[str, ...] = Field(
        default=(),
        description="State keys the task requires. Empty means 'accept any state'.",
    )
    instructions: str | None = Field(
        default=None,
        description="Shared context applied to every question in this task.",
    )

    @model_validator(mode="after")
    def _question_keys_are_identifiers(self) -> DecisionTask:
        for key in self.questions:
            if not key.isidentifier():
                raise ValueError(f"Question key {key!r} must be a valid Python identifier")
        return self

    @property
    def ref(self) -> str:
        """Stable reference used in traces and benchmark records."""
        return f"{self.name}@{self.version}"

    def validate_state(self, state: dict[str, Any]) -> None:
        """Check the caller's input against `input_fields`.

        Raises:
            InputValidationError: if a declared field is missing or empty.
        """
        from jevkit.errors import InputValidationError

        missing = [f for f in self.input_fields if f not in state]
        if missing:
            raise InputValidationError(
                f"Task {self.ref} requires state field(s) {missing}; got keys {sorted(state)}"
            )
