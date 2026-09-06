from app.domain import Dataset, Disruption, Plan, SolveOptions
from app.optimization.monthly import allocate
from app.optimization.scenarios import disrupt, stress
from app.optimization.solver import solve


def execute(dataset: Dataset, kind: str, request: dict) -> dict:
    options = SolveOptions.model_validate(request.get("options", {}))
    if kind == "monthly":
        return allocate(dataset, options.time_limit)
    if kind == "optimize":
        coordinated = solve(dataset, options)
        independent = solve(dataset, options.model_copy(update={"independent": True}))
        return {"plan": coordinated.model_dump(), "baseline": independent.model_dump()}
    parent = Plan.model_validate(request["parent_plan"])
    if kind == "stress":
        return stress(dataset, parent, count=request.get("count", 20), seed=options.seed)
    if kind == "recovery":
        changed = disrupt(dataset, Disruption.model_validate(request["disruption"]))
        recovery = solve(changed, options, parent)
        full = solve(changed, options.model_copy(update={"locked_task_ids": []}))
        if full.verified:
            from app.optimization.verify import diff

            full.metrics.update(diff(parent, full))
        return {
            "plan": recovery.model_dump(),
            "full_replan": full.model_dump(),
            "dataset": changed.model_dump(mode="json"),
            "parent_job_id": request["parent_job_id"],
        }
    raise ValueError("Unknown job kind")
