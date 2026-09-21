"""Schemas for task-definition management."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from jevkit.decisions.questions import Question

__all__ = ["TaskCreateRequest", "TaskListResponse", "TaskResponse"]


class TaskCreateRequest(BaseModel):
    """Register a reusable decision task."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    version: str = "1"
    description: str | None = None
    instructions: str | None = None
    questions: dict[str, Question] = Field(min_length=1)
    input_fields: list[str] = Field(default_factory=list)


class TaskResponse(TaskCreateRequest):
    """A stored task definition."""

    id: str
    created_at: datetime


class TaskListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TaskResponse]
    total: int
