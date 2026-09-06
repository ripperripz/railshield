"""Coarse weekly budgets. Advisory; detailed planning establishes exact feasibility."""

from ortools.sat.python import cp_model

from app.domain import Dataset
from app.optimization.solver import candidate_starts, traffic_prefixes


def allocate(dataset: Dataset, time_limit: float = 10) -> dict:
    weeks = (dataset.horizon + 671) // 672
    model = cp_model.CpModel()
    choices = {}
    traffic = traffic_prefixes(dataset)
    for task in dataset.tasks:
        eligible = sorted(
            {
                s // 672
                for s in candidate_starts(dataset, task, traffic[task.section_id])
                if s + task.duration <= (s // 672 + 1) * 672
            }
        )
        choices[task.id] = {w: model.new_bool_var(f"week_{task.id}_{w}") for w in eligible}
        model.add(sum(choices[task.id].values()) == 1) if task.required else model.add(
            sum(choices[task.id].values()) <= 1
        )
    for section in dataset.sections:
        for week in range(weeks):
            # Unique train-free corridor slots; sum(task duration) is deliberately conservative.
            available = {
                s
                for win in section.windows
                for s in range(max(win.start, week * 672), min(win.end, (week + 1) * 672))
                if traffic[section.id][s + 1] == traffic[section.id][s]
            }
            model.add(
                sum(
                    t.duration * choices[t.id].get(week, 0)
                    for t in dataset.tasks
                    if t.section_id == section.id
                )
                <= len(available)
            )
    for resource in dataset.resources:
        for week in range(weeks):
            slots = min(672, dataset.horizon - week * 672)
            model.add(
                sum(
                    t.duration * t.demands.get(resource.id, 0) * choices[t.id].get(week, 0)
                    for t in dataset.tasks
                )
                <= slots * resource.capacity
            )
    for task in dataset.tasks:
        for pred in task.predecessors:
            model.add(sum(choices[task.id].values()) <= sum(choices[pred].values()))
            for week, x in choices[task.id].items():
                model.add(sum(v for w, v in choices[pred].items() if w <= week) >= x)
    model.minimize(
        sum(
            10000 * t.priority * (1 - sum(choices[t.id].values()))
            + sum(week * x for week, x in choices[t.id].items())
            for t in dataset.tasks
        )
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    status = solver.solve(model)
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    commitments = {
        key: w
        for key, values in choices.items()
        for w, x in values.items()
        if ok and solver.value(x)
    }
    return {
        "status": solver.status_name(status),
        "commitments": commitments,
        "weeks": weeks,
        "advisory": True,
        "note": "Conservative weekly budgets; detailed feasibility is not guaranteed.",
        "solver_seconds": solver.wall_time,
    }
