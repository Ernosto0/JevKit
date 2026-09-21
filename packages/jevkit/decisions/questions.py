"""Question types.

A question declares *what* is being decided and *what shape* the answer must
take. Question types are provider-agnostic on purpose: the Jev adapter maps them
onto Jev's documented question types, and any reference provider maps them onto
its own request format.

The names below mirror the SDK sketch in PLAN.md §9.

Jev implements exactly three of these -- `Noul`, `Choice` and `Score` -- as
verified in phase 1 (see docs/jev-api-notes.md). `Selection`, `Scalar` and
`Rank` have no Jev equivalent and are rejected by the Jev adapter with a clear
error; they remain here because the question vocabulary is provider-agnostic
and other adapters can support them.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["Choice", "Noul", "Question", "Rank", "Scalar", "Score", "Selection"]


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
    descriptions: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Optional per-option guidance. Jev decides against these criteria, so "
            "describing the options materially improves the answer. Keys must be options."
        ),
    )

    @model_validator(mode="after")
    def _options_unique(self) -> Choice:
        if len(set(self.options)) != len(self.options):
            raise ValueError("Choice options must be unique")
        unknown = sorted(set(self.descriptions) - set(self.options))
        if unknown:
            raise ValueError(f"descriptions reference unknown options: {unknown}")
        return self


class Score(_BaseQuestion):
    """Rate the state against an ordered rubric.

    The answer is the position on the rubric as an unrounded float in
    `[0, len(levels) - 1]` -- 2.94 on a four-level rubric means "almost exactly
    the last level". Keeping it unrounded preserves the gradation between
    levels; round it yourself if you only want the bucket.
    """

    kind: Literal["score"] = "score"
    levels: tuple[str, ...] = Field(
        min_length=1,
        max_length=10,
        description="Rubric levels, worst to best. Jev rejects more than 10.",
    )

    @model_validator(mode="after")
    def _levels_unique(self) -> Score:
        if len(set(self.levels)) != len(self.levels):
            raise ValueError("Score levels must be unique")
        return self

    @property
    def maximum(self) -> float:
        """Highest score this rubric can return."""
        return float(len(self.levels) - 1)


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
    Choice | Noul | Rank | Scalar | Score | Selection,
    Field(discriminator="kind"),
]
"""Any supported question type, discriminated by its `kind` field."""
