"""HTTP contract tests for the FastAPI service.

The provider is replaced with the deterministic stub, so these run offline and
exercise the service's own responsibilities: auth, validation, status codes,
and not leaking secrets.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_client
from apps.api.main import app
from apps.api.store import STORE
from jevkit.client.client import DecisionClient
from jevkit.policies.policy import DecisionPolicy
from jevkit.providers.static import StaticProvider

TASK_PAYLOAD = {
    "name": "support-routing",
    "version": "1",
    "input_fields": ["message"],
    "questions": {
        "department": {
            "kind": "choice",
            "options": ["billing", "technical", "account", "other"],
        },
        "urgent": {"kind": "noul"},
    },
}


async def _stub_client() -> AsyncIterator[DecisionClient]:
    client = DecisionClient(
        provider=StaticProvider(
            {"department": "billing", "urgent": 0.9},
            name="static",
            confidence={"urgent": 0.9},
        ),
        policy=DecisionPolicy(primary_provider="static", max_retries=0),
    )
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    STORE.clear()
    app.dependency_overrides[get_client] = _stub_client
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    STORE.clear()


def test_health_is_open_and_reports_schema_status(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    # Honest by default: the Jev mapping is unverified until Phase 1 confirms it.
    assert body["jev_schema_verified"] is False


def test_decide_with_ad_hoc_questions(client: TestClient) -> None:
    response = client.post(
        "/v1/decisions",
        json={
            "state": {"message": "I was charged twice."},
            "questions": {
                "department": {
                    "kind": "choice",
                    "options": ["billing", "technical", "account", "other"],
                },
                "urgent": {"kind": "noul"},
            },
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["decisions"]["department"] == "billing"
    assert body["execution_status"] == "accepted"
    assert body["validation_status"] == "valid"
    assert body["trace_id"]


def test_decision_response_never_includes_the_raw_provider_payload(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/decisions",
        json={
            "state": {"message": "hi"},
            "questions": {"urgent": {"kind": "noul"}},
        },
    )
    assert response.status_code == 200
    assert "raw_response" not in response.json()


def test_trace_is_retrievable_after_a_decision(client: TestClient) -> None:
    decision = client.post(
        "/v1/decisions",
        json={"state": {"message": "hi"}, "questions": {"urgent": {"kind": "noul"}}},
    ).json()

    trace = client.get(f"/v1/traces/{decision['trace_id']}")
    assert trace.status_code == 200

    body = trace.json()
    assert body["trace_id"] == decision["trace_id"]
    assert body["events"][0]["stage"] == "received"
    # Input capture is off by default.
    assert body["state"] is None


def test_unknown_trace_is_404(client: TestClient) -> None:
    assert client.get("/v1/traces/does-not-exist").status_code == 404


def test_create_then_use_a_stored_task(client: TestClient) -> None:
    created = client.post("/v1/tasks", json=TASK_PAYLOAD)
    assert created.status_code == 201
    assert created.json()["name"] == "support-routing"

    listed = client.get("/v1/tasks").json()
    assert listed["total"] == 1

    used = client.post(
        "/v1/decisions",
        json={"state": {"message": "I was charged twice."}, "task_name": "support-routing"},
    )
    assert used.status_code == 200
    assert used.json()["task_ref"] == "support-routing@1"


def test_duplicate_task_version_is_rejected(client: TestClient) -> None:
    assert client.post("/v1/tasks", json=TASK_PAYLOAD).status_code == 201
    conflict = client.post("/v1/tasks", json=TASK_PAYLOAD)
    assert conflict.status_code == 409


def test_missing_required_input_field_is_422(client: TestClient) -> None:
    client.post("/v1/tasks", json=TASK_PAYLOAD)
    response = client.post(
        "/v1/decisions",
        json={"state": {"wrong_key": "x"}, "task_name": "support-routing"},
    )
    assert response.status_code == 422


def test_unknown_task_is_404(client: TestClient) -> None:
    response = client.post("/v1/decisions", json={"state": {}, "task_name": "nope"})
    assert response.status_code == 404


def test_both_task_and_questions_is_rejected(client: TestClient) -> None:
    client.post("/v1/tasks", json=TASK_PAYLOAD)
    response = client.post(
        "/v1/decisions",
        json={
            "state": {"message": "hi"},
            "task_name": "support-routing",
            "questions": {"urgent": {"kind": "noul"}},
        },
    )
    assert response.status_code == 422


def test_benchmark_start_requires_a_known_task(client: TestClient) -> None:
    response = client.post(
        "/v1/benchmarks",
        json={"task_name": "nope", "dataset_ref": "support-routing@1", "provider": "jev"},
    )
    assert response.status_code == 404


def test_benchmark_run_is_queued_not_executed(client: TestClient) -> None:
    client.post("/v1/tasks", json=TASK_PAYLOAD)
    started = client.post(
        "/v1/benchmarks",
        json={"task_name": "support-routing", "dataset_ref": "support-routing@1"},
    )
    assert started.status_code == 202
    assert started.json()["status"] == "queued"

    run_id = started.json()["id"]
    assert client.get(f"/v1/benchmarks/{run_id}").json()["id"] == run_id


def test_openapi_document_is_served(client: TestClient) -> None:
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert "/v1/decisions" in schema.json()["paths"]
