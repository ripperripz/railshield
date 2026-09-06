"""Bounded time-indexed CP-SAT with exact section occupation union."""

from collections import defaultdict
from itertools import combinations

from ortools.sat.python import cp_model

from app.domain import Assignment, Dataset, Plan, SolveOptions
from app.optimization.verify import blocks_for, compatible, diff, verify

MAX_CANDIDATES = 100_000
MAX_ACTIVE_TERMS = 2_000_000


def traffic_prefixes(dataset: Dataset) -> dict[str, list[int]]:
    """Prefix counts of train-occupied slots, built in O(trains + sections*horizon)."""
    differences = {section.id: [0] * (dataset.horizon + 1) for section in dataset.sections}
    for train in dataset.trains:
        differences[train.section_id][train.start] += 1
        differences[train.section_id][train.end] -= 1
    result = {}
    for key, changes in differences.items():
        prefix, load = [0], 0
        for slot in range(dataset.horizon):
            load += changes[slot]
            prefix.append(prefix[-1] + int(load > 0))
        result[key] = prefix
    return result


def candidate_starts(dataset: Dataset, task, prefix: list[int] | None = None) -> list[int]:
    section = next(s for s in dataset.sections if s.id == task.section_id)
    if prefix is None:
        prefix = traffic_prefixes(dataset)[section.id]
    starts = set()
    for window in section.windows:
        for start in range(
            max(task.earliest, window.start), min(task.deadline, window.end) - task.duration + 1
        ):
            if prefix[start + task.duration] == prefix[start]:
                starts.add(start)
    return sorted(starts)


def solve(
    dataset: Dataset, options: SolveOptions | None = None, baseline: Plan | None = None
) -> Plan:
    options = options or SolveOptions()
    tasks = {t.id: t for t in dataset.tasks}
    if set(options.commitments) - tasks.keys() or set(options.locked_task_ids) - tasks.keys():
        raise ValueError("Commitments or locks reference unknown tasks")
    if options.locked_task_ids and baseline is None:
        raise ValueError("Locks require a parent plan")
    if baseline and not baseline.verified:
        raise ValueError("Recovery requires a verified parent plan")
    traffic = traffic_prefixes(dataset)
    candidates = {t.id: candidate_starts(dataset, t, traffic[t.section_id]) for t in dataset.tasks}
    if sum(map(len, candidates.values())) > MAX_CANDIDATES:
        raise ValueError("Instance exceeds 100,000 candidate starts; narrow corridor/task windows")
    if sum(len(candidates[t.id]) * t.duration for t in dataset.tasks) > MAX_ACTIVE_TERMS:
        raise ValueError("Instance exceeds 2,000,000 active terms; narrow planning windows")
    model = cp_model.CpModel()
    selected, present, starts, ends = {}, {}, {}, {}
    active: dict[str, dict[int, cp_model.LinearExpr | int]] = {}
    old = {a.task_id: a for a in baseline.assignments} if baseline else {}
    diagnostics = []
    terms: dict[str, list] = defaultdict(list)
    w = options.weights
    for task in dataset.tasks:
        key = task.id
        selected[key] = {s: model.new_bool_var(f"x_{key}_{s}") for s in candidates[key]}
        present[key] = model.new_bool_var(f"present_{key}")
        model.add(sum(selected[key].values()) == present[key])
        if task.required:
            model.add(present[key] == 1)
            if not candidates[key]:
                diagnostics.append(
                    f"{key}: no start fits task/corridor windows and train exclusions"
                )
        starts[key] = model.new_int_var(0, dataset.horizon, f"start_{key}")
        ends[key] = model.new_int_var(0, dataset.horizon, f"end_{key}")
        model.add(starts[key] == sum(s * x for s, x in selected[key].items()))
        model.add(ends[key] == starts[key] + task.duration * present[key])
        buckets: dict[int, list] = defaultdict(list)
        for s, x in selected[key].items():
            for slot in range(s, s + task.duration):
                buckets[slot].append(x)
        active[key] = {slot: sum(xs) for slot, xs in buckets.items()}
        terms["deferral"].append(w.deferral * task.priority * (1 - present[key]))
        if key in options.commitments:
            terms["commitment"].extend(
                w.commitment * abs(s // 672 - options.commitments[key]) * x
                for s, x in selected[key].items()
            )
        if baseline:
            previous = old.get(key)
            unchanged = (
                (
                    selected[key].get(previous.start, 0)
                    if previous.end - previous.start == task.duration
                    else 0
                )
                if previous
                else 1 - present[key]
            )
            terms["changed"].append(w.changed * (1 - unchanged))
            if previous:
                terms["displacement"].extend(
                    w.displacement * abs(s - previous.start) * x for s, x in selected[key].items()
                )
        if key in options.locked_task_ids:
            if key in old:
                model.add(selected[key].get(old[key].start, 0) == 1)
                # A lock protects duration/end as well as start.
                model.add(ends[key] == old[key].end)
            else:
                model.add(present[key] == 0)
    for task in dataset.tasks:
        for pred in task.predecessors:
            model.add(present[task.id] <= present[pred])
            model.add(starts[task.id] >= ends[pred]).only_enforce_if(present[task.id])
    for a, b in combinations(dataset.tasks, 2):
        if a.section_id == b.section_id and (
            options.independent or not compatible(dataset, a.activity, b.activity)
        ):
            # One disjunctive interval constraint is cheaper than a row for every slot.
            before = model.new_bool_var(f"before_{a.id}_{b.id}")
            model.add(ends[a.id] <= starts[b.id]).only_enforce_if(
                [present[a.id], present[b.id], before]
            )
            model.add(ends[b.id] <= starts[a.id]).only_enforce_if(
                [present[a.id], present[b.id], before.Not()]
            )
    for resource in dataset.resources:
        loads: dict[int, list] = defaultdict(list)
        for task in dataset.tasks:
            if resource.id in task.demands:
                for slot, expression in active[task.id].items():
                    loads[slot].append(task.demands[resource.id] * expression)
        for expressions in loads.values():
            model.add(sum(expressions) <= resource.capacity)
    for section in dataset.sections:
        occupation: dict[int, list] = defaultdict(list)
        for task in dataset.tasks:
            if task.section_id == section.id:
                for slot, expression in active[task.id].items():
                    occupation[slot].append(expression)
        y = {}
        for slot, expressions in occupation.items():
            y[slot] = model.new_bool_var(f"occupied_{section.id}_{slot}")
            model.add_max_equality(y[slot], expressions)
            terms["downtime"].append(w.downtime * y[slot])
        for slot, value in y.items():
            onset = model.new_bool_var(f"onset_{section.id}_{slot}")
            previous_occupation = y.get(slot - 1, 0)
            model.add(onset >= value - previous_occupation)
            model.add(onset <= value)
            model.add(onset <= 1 - previous_occupation)
            terms["fragmentation"].append(w.fragmentation * onset)
    model.minimize(sum(sum(v) for v in terms.values()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = options.time_limit
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = options.seed
    status = solver.solve(model)
    plan = Plan(
        status=solver.status_name(status), solver_seconds=solver.wall_time, diagnostics=diagnostics
    )
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        plan.diagnostics.append(
            "No feasible schedule proved within the time limit; no assignments returned."
            if status == cp_model.UNKNOWN
            else "Hard constraints cannot be satisfied together. Inspect windows, required work, "
            "compatibility, resource capacity, dependencies and locks. "
            "This is not a minimal unsat core."
        )
        return plan
    plan.assignments = sorted(
        [
            Assignment(task_id=t.id, start=solver.value(starts[t.id]), end=solver.value(ends[t.id]))
            for t in dataset.tasks
            if solver.value(present[t.id])
        ],
        key=lambda a: (a.start, a.task_id),
    )
    plan.deferred = [t.id for t in dataset.tasks if not solver.value(present[t.id])]
    errors = verify(
        dataset,
        plan.assignments,
        independent=options.independent,
        baseline=baseline,
        locked=options.locked_task_ids,
    )
    if errors:
        raise RuntimeError(f"Independent verification failed: {errors}")
    plan.verified = True
    plan.blocks = blocks_for(dataset, plan.assignments)
    minutes = sum(b.end - b.start for b in plan.blocks) * dataset.slot_minutes
    plan.metrics = {
        "downtime_minutes": minutes,
        "blocks": len(plan.blocks),
        "scheduled_tasks": len(plan.assignments),
        "deferred_tasks": len(plan.deferred),
        "availability_percent": 100
        * (1 - minutes / (dataset.horizon * 15 * len(dataset.sections))),
        "train_conflicts": 0,
        "shared_blocks": sum(
            any(
                a.start < c.end and c.start < a.end
                for a, c in combinations(
                    [x for x in plan.assignments if x.task_id in b.task_ids], 2
                )
            )
            for b in plan.blocks
        ),
    }
    if baseline:
        plan.metrics.update(diff(baseline, plan))
    plan.objective = {name: float(solver.value(sum(values))) for name, values in terms.items()}
    plan.objective_value = solver.objective_value
    plan.best_bound = solver.best_objective_bound
    return plan
