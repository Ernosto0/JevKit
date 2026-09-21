"""Decision and trace endpoints (PLAN.md section 14).

Persistence is not wired up yet -- Phase 4 replaces the in-memory store below
with the PostgreSQL models in `apps/api/db.py`. The HTTP contract is stable
regardless of which store backs it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from apps.api.dependencies import ApiKey, Client
from apps.api.schemas.decisions import DecisionRequest, DecisionResponse, TraceResponse
from apps.api.store import STORE
from jevkit.errors import InputValidationError, ProviderError, TaskDefinitionError
from jevkit.tracing.trace import DecisionTrace

router = APIRouter(tags=["decisions"])


@router.post(
    "/decisions",
    response_model=DecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a decision",
)
async def create_decision(
    request: DecisionRequest,
    client: Client,
    _api_key: ApiKey,
) -> DecisionResponse:
    """Run one decision and return the normalized result.

    The result is a recommendation. The calling application remains responsible
    for authorization and for performing any action (PLAN.md section 17).
    """
    task = None
    if request.task_name is not None:
        task = STORE.get_task(request.task_name, request.task_version)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No task named {request.task_name!r}",
            )

    try:
        result, trace = await client.decide_with_trace(
            state=request.state,
            questions=request.questions,
            task=task,
            policy=request.policy,
        )
    except TaskDefinitionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.message) from exc
    except InputValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.message) from exc
    except ProviderError as exc:
        # Surface a provider failure without leaking credentials or internals.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, exc.message) from exc

    STORE.save_decision(result, trace)
    return DecisionResponse.from_result(result)


@router.get(
    "/decisions/{decision_id}",
    response_model=DecisionResponse,
    summary="Retrieve a decision",
)
async def get_decision(decision_id: str, _api_key: ApiKey) -> DecisionResponse:
    result = STORE.get_decision(decision_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No decision {decision_id!r}")
    return DecisionResponse.from_result(result)


@router.get(
    "/traces/{trace_id}",
    response_model=TraceResponse,
    summary="Retrieve an execution trace",
)
async def get_trace(trace_id: str, _api_key: ApiKey) -> TraceResponse:
    trace: DecisionTrace | None = STORE.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No trace {trace_id!r}")
    return TraceResponse.from_trace(trace)
