"""Seeded, finite scenario experiments; never presented as probability guarantees."""

import math
import random
from collections.abc import Sequence
from typing import Any, TypedDict

from app.domain import (
    Assignment,
    Dataset,
    Disruption,
    DisruptionKind,
    Plan,
    Resource,
    Section,
    Task,
    Train,
)
from app.optimization.verify import verify


class ScenarioResult(TypedDict):
    scenario: dict[str, Any]
    feasible: bool
    violations: list[str]
    valid: bool


def disrupt(dataset: Dataset, scenario: Disruption) -> Dataset:
    data = dataset.model_dump(mode="json")
    rows = data[
        {
            "train_delay": "trains",
            "task_overrun": "tasks",
            "crew_loss": "resources",
            "corridor_reduction": "sections",
            "emergency": "sections",
        }[scenario.kind]
    ]
    if not rows:
        raise ValueError(f"No targets available for {scenario.kind}")
    target = (
        next((r for r in rows if r["id"] == scenario.target_id), None)
        if (scenario.target_id)
        else rows[0]
    )
    if target is None:
        raise ValueError("Unknown disruption target")
    n = scenario.magnitude
    if scenario.kind == "train_delay":
        # Preserve occupation duration; reject overflow instead of clipping it away.
        target["start"] += n
        target["end"] += n
        if target["end"] > dataset.horizon:
            raise ValueError("Delayed train exceeds dataset horizon")
    elif scenario.kind == "task_overrun":
        target["duration"] += n
    elif scenario.kind == "crew_loss":
        target["capacity"] = max(0, target["capacity"] - n)
    elif scenario.kind == "corridor_reduction":
        target["windows"] = [
            {**w, "end": w["end"] - n} for w in target["windows"] if w["end"] - n > w["start"]
        ]
        if not target["windows"]:
            raise ValueError("Reduction removes every corridor window")
    else:
        if len(data["tasks"]) >= 200:
            raise ValueError("Emergency exceeds dataset task limit")
        ids = {t.id for t in dataset.tasks}
        number = 1
        while f"EMERGENCY-{number}" in ids:
            number += 1
        w = target["windows"][0]
        data["tasks"].append(
            Task(
                id=f"EMERGENCY-{number}",
                title="Emergency track defect",
                department="ENG",
                section_id=target["id"],
                activity="ENG",
                duration=n,
                earliest=w["start"],
                deadline=w["end"],
                priority=10,
                required=True,
                demands={dataset.resources[0].id: 1} if dataset.resources else {},
            ).model_dump()
        )
    data["name"] = f"{dataset.name[:85]} · {scenario.kind}"
    return Dataset.model_validate(data)


def stress(dataset: Dataset, plan: Plan, *, count: int = 20, seed: int = 42) -> dict:
    if not plan.verified:
        raise ValueError("Stress testing requires a verified plan")
    rng = random.Random(seed)
    kinds: list[DisruptionKind] = ["task_overrun", "corridor_reduction", "emergency"]
    if dataset.trains:
        kinds.append("train_delay")
    if dataset.resources:
        kinds.append("crew_loss")
    results: list[ScenarioResult] = []
    for i in range(count):
        kind = kinds[i % len(kinds)]
        pools: dict[str, Sequence[Task | Train | Resource | Section]] = {
            "task_overrun": dataset.tasks,
            "corridor_reduction": dataset.sections,
            "emergency": dataset.sections,
            "train_delay": dataset.trains,
            "crew_loss": dataset.resources,
        }
        pool = pools[kind]
        target = rng.choice(pool)
        scenario = Disruption(kind=kind, magnitude=rng.randint(1, 3), target_id=target.id)
        try:
            changed = disrupt(dataset, scenario)
            durations = {t.id: t.duration for t in changed.tasks}
            assignments = [
                Assignment(
                    task_id=a.task_id, start=a.start, end=min(2976, a.start + durations[a.task_id])
                )
                for a in plan.assignments
            ]
            violations = verify(changed, assignments)
            results.append(
                {
                    "scenario": scenario.model_dump(),
                    "feasible": not violations,
                    "violations": violations,
                    "valid": True,
                }
            )
        except ValueError as error:
            results.append(
                {
                    "scenario": scenario.model_dump(),
                    "feasible": False,
                    "violations": [str(error)],
                    "valid": False,
                }
            )
    valid = [r for r in results if r["valid"]]
    successes = sum(r["feasible"] for r in valid)
    n = len(valid)
    p = successes / n if n else 0
    # Wilson interval summarizes this sample only; scenario distribution is synthetic.
    denom = 1 + 3.8416 / n if n else 1
    center = (p + 1.9208 / n) / denom if n else 0
    margin = 1.96 * math.sqrt(p * (1 - p) / n + 0.9604 / n**2) / denom if n else 0
    return {
        "seed": seed,
        "requested": count,
        "evaluated": n,
        "invalid": count - n,
        "feasible": successes,
        "feasibility_rate": p if n else None,
        "sample_interval_95": [max(0, center - margin), min(1, center + margin)] if n else None,
        "mean_violation_count": sum(len(r["violations"]) for r in valid) / n if n else None,
        "results": results,
        "interpretation": "Fixed starts; overruns extend task ends. Synthetic sample, "
        "not a real-world reliability guarantee. No recovery performed in this score.",
    }
