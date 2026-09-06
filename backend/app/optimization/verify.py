"""Independent sweep-line verifier; does not reuse model constraints."""

from collections import defaultdict
from itertools import combinations

from app.domain import Assignment, Block, Dataset, Plan


def overlap(a, b) -> bool:
    return a.start < b.end and b.start < a.end


def compatible(dataset: Dataset, first: str, second: str) -> bool:
    return any({a, b} == {first, second} for a, b in dataset.compatible)


def verify(
    dataset: Dataset,
    assignments: list[Assignment],
    *,
    independent: bool = False,
    baseline: Plan | None = None,
    locked: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    tasks = {t.id: t for t in dataset.tasks}
    sections = {s.id: s for s in dataset.sections}
    by_id = {a.task_id: a for a in assignments}
    if len(by_id) != len(assignments):
        errors.append("Duplicate task assignment")
    for task in dataset.tasks:
        if task.required and task.id not in by_id:
            errors.append(f"Required task missing: {task.id}")
    known = []
    for a in assignments:
        if a.task_id not in tasks:
            errors.append(f"Unknown task: {a.task_id}")
            continue
        known.append(a)
        task = tasks[a.task_id]
        if a.end - a.start != task.duration:
            errors.append(f"Duration mismatch: {task.id}")
        if a.start < task.earliest or a.end > task.deadline:
            errors.append(f"Task window violated: {task.id}")
        if not any(
            w.start <= a.start and a.end <= w.end for w in sections[task.section_id].windows
        ):
            errors.append(f"Corridor window violated: {task.id}")
        for train in dataset.trains:
            if train.section_id == task.section_id and overlap(a, train):
                errors.append(f"Train conflict: {task.id} / {train.id}")
        for pred in task.predecessors:
            if pred not in by_id or by_id[pred].end > a.start:
                errors.append(f"Precedence violated: {pred} → {task.id}")
    for a, b in combinations(known, 2):
        ta, tb = tasks[a.task_id], tasks[b.task_id]
        if ta.section_id == tb.section_id and overlap(a, b):
            if independent or not compatible(dataset, ta.activity, tb.activity):
                errors.append(f"Incompatible overlap: {ta.id} / {tb.id}")
    for resource in dataset.resources:
        events: dict[int, int] = defaultdict(int)
        for a in known:
            demand = tasks[a.task_id].demands.get(resource.id, 0)
            events[a.start] += demand
            events[a.end] -= demand
        load = 0
        for slot in sorted(events):
            load += events[slot]
            if load > resource.capacity:
                errors.append(f"Resource capacity: {resource.id} at slot {slot}")
    if baseline:
        old = {a.task_id: a for a in baseline.assignments}
        for key in locked or []:
            if by_id.get(key) != old.get(key):
                errors.append(f"Locked assignment changed: {key}")
    return errors


def blocks_for(dataset: Dataset, assignments: list[Assignment]) -> list[Block]:
    tasks = {t.id: t for t in dataset.tasks}
    blocks: list[Block] = []
    for section in dataset.sections:
        rows = sorted(
            (a for a in assignments if tasks[a.task_id].section_id == section.id),
            key=lambda a: a.start,
        )
        current: Block | None = None
        for a in rows:
            if current and a.start <= current.end:
                current.end = max(current.end, a.end)
                current.task_ids.append(a.task_id)
            else:
                current = Block(
                    section_id=section.id, start=a.start, end=a.end, task_ids=[a.task_id]
                )
                blocks.append(current)
    return blocks


def diff(old: Plan, new: Plan) -> dict[str, float]:
    a, b = ({x.task_id: x for x in p.assignments} for p in (old, new))
    keys = a.keys() | b.keys()
    changed = sum(a.get(k) != b.get(k) for k in keys)
    displacement = sum(abs(a[k].start - b[k].start) for k in a.keys() & b.keys())
    return {
        "changed_tasks": changed,
        "churn_rate": changed / len(keys) if keys else 0,
        "displacement_slots": displacement,
    }
