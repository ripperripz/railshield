"""Stateless Vercel endpoints.

The browser owns dataset and plan history in this mode. Every request carries the
complete immutable input it needs, so correctness never depends on an ephemeral
function filesystem or a continuously running worker.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field, model_validator

from app.domain import Contract, Dataset, Disruption, GenerateRequest, Plan, SolveOptions
from app.ingestion.synthetic import generate
from app.service import execute

router = APIRouter(prefix="/api/v1/stateless", tags=["stateless hosting"])


class StatelessExecution(Contract):
    dataset: Dataset
    kind: Literal["monthly", "optimize", "stress", "recovery"]
    options: SolveOptions = Field(default_factory=SolveOptions)
    parent_plan: Plan | None = None
    parent_job_id: str | None = Field(default=None, max_length=80)
    disruption: Disruption | None = None
    count: int = Field(default=20, ge=1, le=20)

    @model_validator(mode="after")
    def validate_lineage(self):
        if self.options.time_limit > 8:
            raise ValueError("Hosted solver runs are limited to 8 seconds per plan")
        if len(self.dataset.tasks) > 60 or self.dataset.horizon > 28 * 96:
            raise ValueError("Hosted demo runs support at most 60 tasks and 28 days")
        if self.kind in ("stress", "recovery"):
            if self.parent_plan is None or not self.parent_plan.verified:
                raise ValueError("A verified parent plan is required")
        if self.kind == "recovery" and self.disruption is None:
            raise ValueError("Recovery requires a disruption")
        if self.kind != "recovery" and self.options.locked_task_ids:
            raise ValueError("Locks are only supported for recovery")
        task_ids = {task.id for task in self.dataset.tasks}
        if set(self.options.commitments) - task_ids:
            raise ValueError("A commitment references an unknown task")
        if set(self.options.locked_task_ids) - task_ids:
            raise ValueError("A lock references an unknown task")
        return self


@router.post("/generate")
def stateless_generate(request: GenerateRequest):
    if request.tasks > 60 or request.days > 28:
        raise HTTPException(
            status_code=422, detail="Hosted demo generation supports at most 60 tasks and 28 days"
        )
    return {"dataset": generate(request).model_dump(mode="json")}


@router.post("/validate")
def stateless_validate(dataset: Dataset):
    return {"dataset": dataset.model_dump(mode="json")}


@router.post("/execute")
def stateless_execute(request: StatelessExecution):
    payload = request.model_dump(mode="json", exclude={"dataset", "kind"})
    if request.parent_plan is not None:
        payload["parent_plan"] = request.parent_plan.model_dump(mode="json")
    try:
        return execute(request.dataset, request.kind, payload)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
