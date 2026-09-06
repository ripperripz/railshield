import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field
from sqlalchemy import func, select, text

from app.config import settings
from app.db import AuditRow, DatasetRow, JobRow, engine, initialize, session_factory
from app.domain import Contract, Dataset, Disruption, GenerateRequest, SolveOptions
from app.ingestion.synthetic import generate
from app.serverless import router as serverless_router


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks, total = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            total += len(message.get("body", b""))
            if total > settings().max_body_bytes:
                return await JSONResponse({"detail": "Request body exceeds 2 MB"}, 413)(
                    scope, receive, send
                )
            chunks.append(message)
            if not message.get("more_body", False):
                break
        index = 0

        async def replay():
            nonlocal index
            if index < len(chunks):
                message = chunks[index]
                index += 1
                return message
            return await receive()

        await self.app(scope, replay, send)


@asynccontextmanager
async def lifespan(_app):
    settings()  # Fail closed on invalid production configuration.
    if settings().environment == "development":
        initialize()
    yield
    engine().dispose()


app = FastAPI(title="RailShield", version="0.1.0", lifespan=lifespan)
app.add_middleware(BodyLimit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
bearer = HTTPBearer(auto_error=False)


def authenticate(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    key = settings().api_key
    if key and (
        credentials is None
        or not hmac.compare_digest(credentials.credentials.encode(), key.encode())
    ):
        raise HTTPException(
            401, "Valid bearer API key required", headers={"WWW-Authenticate": "Bearer"}
        )


protected = [Depends(authenticate)]
app.include_router(
    serverless_router,
    dependencies=[] if settings().environment == "serverless" else protected,
)


@app.get("/health/live")
def live():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/health/ready")
def ready():
    if settings().environment == "serverless":
        return {"status": "ready", "environment": "serverless"}
    try:
        with engine().connect() as connection:
            connection.execute(select(DatasetRow.id).limit(1))
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ready", "environment": settings().environment}


def save_dataset(dataset: Dataset) -> dict:
    payload = dataset.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with session_factory().begin() as session:
        row = DatasetRow(name=dataset.name, payload=payload, content_hash=digest)
        session.add(row)
        session.flush()
        session.add(
            AuditRow(
                action="dataset.created",
                entity_id=row.id,
                detail={"sha256": digest, "synthetic": dataset.synthetic},
            )
        )
        return {"id": row.id, "name": row.name, "content_hash": digest, "dataset": payload}


@app.post("/api/v1/datasets", dependencies=protected, status_code=201)
def import_dataset(dataset: Dataset):
    return save_dataset(dataset)


@app.post("/api/v1/datasets/generate", dependencies=protected, status_code=201)
def generate_dataset(request: GenerateRequest):
    return save_dataset(generate(request))


@app.get("/api/v1/datasets", dependencies=protected)
def list_datasets(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    with session_factory()() as session:
        rows = session.scalars(
            select(DatasetRow).order_by(DatasetRow.created_at.desc()).limit(limit).offset(offset)
        )
        return [
            {
                "id": r.id,
                "name": r.name,
                "created_at": r.created_at,
                "synthetic": r.payload["synthetic"],
                "tasks": len(r.payload["tasks"]),
            }
            for r in rows
        ]


@app.get("/api/v1/datasets/{dataset_id}", dependencies=protected)
def get_dataset(dataset_id: str):
    with session_factory()() as session:
        row = session.get(DatasetRow, dataset_id)
        if row is None:
            raise HTTPException(404, "Dataset not found")
        return {
            "id": row.id,
            "name": row.name,
            "content_hash": row.content_hash,
            "dataset": row.payload,
        }


class JobRequest(Contract):
    dataset_id: str = Field(min_length=1, max_length=36)
    kind: Literal["monthly", "optimize", "stress", "recovery"] = "optimize"
    options: SolveOptions = Field(default_factory=SolveOptions)
    parent_job_id: str | None = Field(default=None, max_length=36)
    disruption: Disruption | None = None
    count: int = Field(default=20, ge=1, le=100)


def job_dict(row):
    return {
        "id": row.id,
        "dataset_id": row.dataset_id,
        "parent_job_id": row.request.get("parent_job_id"),
        "kind": row.kind,
        "status": row.status,
        "result": row.result,
        "error": row.error,
        "created_at": row.created_at,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
    }


@app.post("/api/v1/jobs", dependencies=protected, status_code=202)
def create_job(request: JobRequest):
    with session_factory().begin() as session:
        if engine().dialect.name == "postgresql":
            # Serialize admission only, not solver execution.
            session.execute(text("SELECT pg_advisory_xact_lock(26027)"))
        row = session.get(DatasetRow, request.dataset_id)
        if row is None:
            raise HTTPException(404, "Dataset not found")
        count = session.scalar(
            select(func.count()).select_from(JobRow).where(JobRow.status.in_(["queued", "running"]))
        )
        if count >= settings().max_pending_jobs:
            raise HTTPException(429, "Planning queue is full", headers={"Retry-After": "10"})
        payload = request.model_dump(mode="json")
        if request.kind in ("stress", "recovery"):
            parent = session.get(JobRow, request.parent_job_id) if request.parent_job_id else None
            if (
                parent is None
                or parent.dataset_id != row.id
                or parent.status != "completed"
                or not parent.result
                or not parent.result.get("plan", {}).get("verified")
            ):
                raise HTTPException(422, "A completed verified plan from this dataset is required")
            payload["parent_plan"] = parent.result["plan"]
            payload["parent_dataset"] = parent.result.get("dataset", row.payload)
            if request.kind == "recovery" and request.disruption is None:
                raise HTTPException(422, "Recovery requires a disruption")
        elif request.options.locked_task_ids:
            raise HTTPException(422, "Locks are only supported for recovery")
        ids = {t["id"] for t in payload.get("parent_dataset", row.payload)["tasks"]}
        if set(request.options.commitments) - ids or set(request.options.locked_task_ids) - ids:
            raise HTTPException(422, "Unknown task in commitments or locks")
        job = JobRow(dataset_id=row.id, kind=request.kind, request=payload)
        session.add(job)
        session.flush()
        session.add(
            AuditRow(
                action="job.queued",
                entity_id=job.id,
                detail={"kind": request.kind, "parent_job_id": request.parent_job_id},
            )
        )
        return job_dict(job)


@app.get("/api/v1/jobs", dependencies=protected)
def list_jobs(dataset_id: str | None = None, limit: int = Query(30, ge=1, le=100)):
    with session_factory()() as session:
        query = select(JobRow).order_by(JobRow.created_at.desc()).limit(limit)
        if dataset_id:
            query = query.where(JobRow.dataset_id == dataset_id)
        return [job_dict(row) for row in session.scalars(query)]


@app.get("/api/v1/jobs/{job_id}", dependencies=protected)
def get_job(job_id: str):
    with session_factory()() as session:
        row = session.get(JobRow, job_id)
        if row is None:
            raise HTTPException(404, "Job not found")
        return job_dict(row)


@app.get("/api/v1/audit", dependencies=protected)
def audit(limit: int = Query(50, ge=1, le=100)):
    with session_factory()() as session:
        return [
            {
                "id": r.id,
                "action": r.action,
                "entity_id": r.entity_id,
                "detail": r.detail,
                "created_at": r.created_at,
            }
            for r in session.scalars(
                select(AuditRow).order_by(AuditRow.created_at.desc()).limit(limit)
            )
        ]
