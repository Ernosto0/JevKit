"""Question types.

A question declares *what* is being decided and *what shape* the answer must
take. Question types are provider-agnostic on purpose: the Jev adapter maps them
onto Jev's documented question types, and any reference provider maps them onto
its own request format.

The names below mirror the SDK sketch in PLAN.md §9. The exact set of question
types Jev supports must be confirmed against the official API before the
adapter mapping in `jevkit.providers.jev` is finalized.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["Choice", "Noul", "Question", "Rank", "Scalar", "Selection"]


class _BaseQuestion(BaseModel):
    """Fields shared by every question type."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    instructions: str | None = Field(
        default=None,
        description="Plain-language description of what is being asked.",
    )


class Noul(_BaseQuestion):
    """A yes/no question answered with a probability in [0, 1].

    The value is the provider's stated probability that the answer is "yes".
    Treat it as a probability, never as a guarantee of correctness (PLAN.md §17).
    """

    kind: Literal["noul"] = "noul"
    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Probability at or above which the answer is read as 'yes'.",
    )


class Choice(_BaseQuestion):
    """Pick exactly one option from a closed set."""

    kind: Literal["choice"] = "choice"
    options: tuple[str, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _options_unique(self) -> Choice:
        if len(set(self.options)) != len(self.options):
            raise ValueError("Choice options must be unique")
        return self


class Selection(_BaseQuestion):
    """Pick zero or more options from a closed set."""

    kind: Literal["selection"] = "selection"
    options: tuple[str, ...] = Field(min_length=1)
    min_selected: int = Field(default=0, ge=0)
    max_selected: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _bounds_are_sane(self) -> Selection:
        if len(set(self.options)) != len(self.options):
            raise ValueError("Selection options must be unique")
        if self.max_selected is not None:
            if self.max_selected < self.min_selected:
                raise ValueError("max_selected must be >= min_selected")
            if self.max_selected > len(self.options):
                raise ValueError("max_selected cannot exceed the number of options")
        return self


class Scalar(_BaseQuestion):
    """A numeric score within an explicit, inclusive range."""

    kind: Literal["scalar"] = "scalar"
    minimum: float = 0.0
    maximum: float = 1.0

    @model_validator(mode="after")
    def _range_is_ordered(self) -> Scalar:
        if self.minimum >= self.maximum:
            raise ValueError("minimum must be strictly less than maximum")
        return self


class Rank(_BaseQuestion):
    """Order a closed set of options from best to worst against the criteria."""

    kind: Literal["rank"] = "rank"
    options: tuple[str, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _options_unique(self) -> Rank:
        if len(set(self.options)) != len(self.options):
            raise ValueError("Rank options must be unique")
        return self


Question = Annotated[
    Choice | Noul | Rank | Scalar | Selection,
    Field(discriminator="kind"),
]
"""Any supported question type, discriminated by its `kind` field."""
