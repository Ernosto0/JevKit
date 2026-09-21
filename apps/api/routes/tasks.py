"""Task-definition endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from apps.api.dependencies import ApiKey
from apps.api.schemas.tasks import TaskCreateRequest, TaskListResponse, TaskResponse
from apps.api.store import STORE
from jevkit.decisions.task import DecisionTask
from jevkit.errors import TaskDefinitionError

router = APIRouter(tags=["tasks"])


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task definition",
)
async def create_task(request: TaskCreateRequest, _api_key: ApiKey) -> TaskResponse:
    """Register a reusable, versioned decision task."""
    if STORE.get_task(request.name, request.version) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Task {request.name}@{request.version} already exists; bump the version instead.",
        )
    try:
        task = DecisionTask(
            name=request.name,
            version=request.version,
            description=request.description,
            instructions=request.instructions,
            questions=request.questions,
            input_fields=tuple(request.input_fields),
        )
    except (TaskDefinitionError, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    task_id, created_at = STORE.save_task(task)
    return TaskResponse(
        id=task_id,
        created_at=created_at,
        name=task.name,
        version=task.version,
        description=task.description,
        instructions=task.instructions,
        questions=task.questions,
        input_fields=list(task.input_fields),
    )


@router.get("/tasks", response_model=TaskListResponse, summary="List task definitions")
async def list_tasks(_api_key: ApiKey) -> TaskListResponse:
    items = [
        TaskResponse(
            id=task_id,
            created_at=created_at,
            name=task.name,
            version=task.version,
            description=task.description,
            instructions=task.instructions,
            questions=task.questions,
            input_fields=list(task.input_fields),
        )
        for task_id, created_at, task in STORE.list_tasks()
    ]
    return TaskListResponse(items=items, total=len(items))
