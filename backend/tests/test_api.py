import pytest
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.db import engine
from app.main import app
from app.worker import run_once


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RAILSHIELD_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("RAILSHIELD_API_KEY", "test-secret")
    settings.cache_clear()
    engine.cache_clear()
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer test-secret"
        yield client
    engine().dispose()
    engine.cache_clear()
    settings.cache_clear()


def test_real_job_lifecycle_and_audit(client):
    response = client.post("/api/v1/datasets/generate", json={"tasks": 6, "days": 7, "sections": 2})
    assert response.status_code == 201
    dataset_id = response.json()["id"]
    job = client.post(
        "/api/v1/jobs", json={"dataset_id": dataset_id, "options": {"time_limit": 2}}
    ).json()
    assert job["status"] == "queued"
    assert run_once()
    completed = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert completed["status"] == "completed"
    assert completed["result"]["plan"]["verified"]
    stress = client.post(
        "/api/v1/jobs",
        json={"dataset_id": dataset_id, "kind": "stress", "parent_job_id": job["id"], "count": 5},
    ).json()
    assert run_once()
    assert client.get(f"/api/v1/jobs/{stress['id']}").json()["result"]["evaluated"] == 5
    assert len(client.get("/api/v1/audit").json()) >= 5
    assert not run_once()


def test_auth_validation_and_body_limit(client):
    assert (
        client.get("/api/v1/datasets", headers={"Authorization": "Bearer wrong"}).status_code == 401
    )
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert client.post("/api/v1/datasets/generate", json={"tasks": 201}).status_code == 422
    assert client.post("/api/v1/datasets", content=b"x" * 2_000_001).status_code == 413
    assert client.post("/api/v1/jobs", json={"dataset_id": "missing"}).status_code == 404


def test_production_fails_closed():
    with pytest.raises(ValueError, match="API_KEY"):
        Settings(environment="production", api_key="")


def test_recovery_lineage_and_locks(client):
    dataset = client.post("/api/v1/datasets/generate", json={"tasks": 3, "days": 7}).json()
    parent = client.post(
        "/api/v1/jobs", json={"dataset_id": dataset["id"], "options": {"time_limit": 2}}
    ).json()
    run_once()
    child = client.post(
        "/api/v1/jobs",
        json={
            "dataset_id": dataset["id"],
            "kind": "recovery",
            "parent_job_id": parent["id"],
            "options": {"time_limit": 2},
            "disruption": {"kind": "task_overrun", "magnitude": 1},
        },
    ).json()
    run_once()
    result = client.get(f"/api/v1/jobs/{child['id']}").json()
    assert result["status"] == "completed"
    assert result["result"]["parent_job_id"] == parent["id"]
    assert result["result"]["dataset"]["tasks"][0]["duration"] == (
        dataset["dataset"]["tasks"][0]["duration"] + 1
    )


def test_stateless_hosted_flow(client):
    generated = client.post(
        "/api/v1/stateless/generate",
        json={"tasks": 6, "sections": 2, "days": 7, "trains": 4, "seed": 26027},
    )
    assert generated.status_code == 200
    dataset = generated.json()["dataset"]
    monthly = client.post(
        "/api/v1/stateless/execute",
        json={"dataset": dataset, "kind": "monthly", "options": {"time_limit": 2}},
    )
    assert monthly.status_code == 200
    plan = client.post(
        "/api/v1/stateless/execute",
        json={
            "dataset": dataset,
            "kind": "optimize",
            "options": {
                "time_limit": 2,
                "commitments": monthly.json()["commitments"],
            },
        },
    )
    assert plan.status_code == 200
    assert plan.json()["plan"]["verified"]
    stress = client.post(
        "/api/v1/stateless/execute",
        json={
            "dataset": dataset,
            "kind": "stress",
            "options": {"time_limit": 2},
            "parent_plan": plan.json()["plan"],
            "parent_job_id": "browser-parent",
            "count": 5,
        },
    )
    assert stress.status_code == 200
    assert stress.json()["evaluated"] == 5


def test_stateless_hosted_limits(client):
    response = client.post(
        "/api/v1/stateless/generate",
        json={"tasks": 61, "sections": 2, "days": 7, "trains": 4},
    )
    assert response.status_code == 422
