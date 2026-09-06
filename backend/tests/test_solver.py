from datetime import datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.domain import (
    Assignment,
    Dataset,
    Disruption,
    GenerateRequest,
    Resource,
    Section,
    SolveOptions,
    Task,
    Train,
    Window,
)
from app.ingestion.synthetic import generate
from app.optimization.monthly import allocate
from app.optimization.scenarios import disrupt, stress
from app.optimization.solver import solve
from app.optimization.verify import verify


def fixture(duration=4, capacity=2, compatible=True):
    return Dataset(
        name="Small fixture",
        epoch=datetime.fromisoformat("2026-09-07T00:00:00+05:30"),
        horizon=16,
        sections=[
            Section(
                id="S",
                name="A–B",
                from_station="A",
                to_station="B",
                windows=[Window(start=0, end=16)],
            )
        ],
        resources=[Resource(id="R", name="Crew", capacity=capacity)],
        tasks=[
            Task(
                id="A",
                title="Track",
                department="ENG",
                section_id="S",
                activity="ENG",
                duration=duration,
                deadline=16,
                demands={"R": 1},
            ),
            Task(
                id="B",
                title="Signal",
                department="SNT",
                section_id="S",
                activity="SNT",
                duration=duration,
                deadline=16,
                demands={"R": 1},
            ),
        ],
        compatible=[("ENG", "SNT")] if compatible else [],
    )


def test_shared_possession_is_union():
    d = fixture()
    plan = solve(d)
    baseline = solve(d, SolveOptions(independent=True))
    assert plan.status == "OPTIMAL" and plan.verified
    assert plan.metrics["downtime_minutes"] == 60
    assert baseline.metrics["downtime_minutes"] == 120
    assert sum(plan.objective.values()) == plan.objective_value


@pytest.mark.parametrize("capacity,allow", [(1, True), (2, False)])
def test_overlap_requires_both_capacity_and_compatibility(capacity, allow):
    plan = solve(fixture(capacity=capacity, compatible=allow))
    assert plan.metrics["downtime_minutes"] == 120


def test_train_exclusion_and_precedence():
    d = fixture()
    d.trains = [Train(id="T", section_id="S", start=0, end=4)]
    d.tasks[1].predecessors = ["A"]
    plan = solve(d)
    a, b = ({x.task_id: x for x in plan.assignments}[k] for k in ("A", "B"))
    assert a.start >= 4 and b.start >= a.end


def test_optional_deferral_and_required_infeasibility():
    d = fixture(duration=10, compatible=False)
    assert solve(d).status == "INFEASIBLE"
    d.tasks[1].required = False
    plan = solve(d)
    assert plan.verified and plan.deferred == ["B"]


def test_successor_cannot_outlive_missing_predecessor():
    d = fixture(capacity=0)
    d.tasks[0].required = False
    d.tasks[1].demands = {}
    d.tasks[1].predecessors = ["A"]
    assert solve(d).status == "INFEASIBLE"


def test_lock_is_never_relaxed():
    d = fixture()
    parent = solve(d)
    first = parent.assignments[0]
    d.trains = [Train(id="T", section_id="S", start=first.start, end=first.end)]
    recovered = solve(d, SolveOptions(locked_task_ids=[first.task_id]), parent)
    assert recovered.status == "INFEASIBLE" and recovered.assignments == []


def test_recovery_preserves_unchanged_instance():
    d = fixture()
    parent = solve(d)
    recovered = solve(d, baseline=parent)
    assert recovered.assignments == parent.assignments
    assert recovered.metrics["changed_tasks"] == 0


def test_lock_protects_end_after_overrun():
    d = fixture()
    parent = solve(d)
    changed = disrupt(d, Disruption(kind="task_overrun", target_id="A", magnitude=1))
    assert solve(changed, SolveOptions(locked_task_ids=["A"]), parent).status == "INFEASIBLE"


def test_verifier_catches_invalid_external_plan():
    errors = verify(
        fixture(capacity=1),
        [Assignment(task_id="A", start=0, end=4), Assignment(task_id="B", start=0, end=4)],
    )
    assert any("Resource" in e for e in errors)
    assert verify(fixture(), [Assignment(task_id="A", start=15, end=19)])


def test_cyclic_import_rejected():
    raw = fixture().model_dump()
    raw["tasks"][0]["predecessors"] = ["B"]
    raw["tasks"][1]["predecessors"] = ["A"]
    with pytest.raises(ValidationError, match="cycle"):
        Dataset.model_validate(raw)


@given(duration=st.integers(1, 8), capacity=st.integers(0, 2), allow=st.booleans())
@settings(max_examples=25, deadline=None)
def test_small_random_instances_match_analytic_feasibility(duration, capacity, allow):
    d = fixture(duration, capacity, allow)
    plan = solve(d, SolveOptions(time_limit=1))
    assert plan.verified == (capacity > 0)
    if plan.verified:
        assert verify(d, plan.assignments) == []
        expected = duration if allow and capacity == 2 else duration * 2
        assert plan.metrics["downtime_minutes"] == expected * 15


def test_seeded_generator_and_scenarios():
    cfg = GenerateRequest(tasks=6, sections=2, days=7, trains=4)
    d = generate(cfg)
    assert d == generate(cfg)
    plan = solve(d, SolveOptions(time_limit=2))
    assert plan.verified
    assert stress(d, plan, count=5) == stress(d, plan, count=5)


def test_monthly_advisory_refines_to_verified_plan():
    d = generate(GenerateRequest(tasks=6, sections=2, days=14, trains=4))
    monthly = allocate(d, 2)
    assert monthly["advisory"] and len(monthly["commitments"]) == 6
    detail = solve(d, SolveOptions(commitments=monthly["commitments"], time_limit=2))
    assert detail.verified


def test_all_disruptions_validate():
    d = generate(GenerateRequest(tasks=6, sections=2, days=7, trains=4))
    for kind in ["train_delay", "task_overrun", "crew_loss", "corridor_reduction", "emergency"]:
        changed = disrupt(d, Disruption(kind=kind, magnitude=1))
        assert changed != d
        Dataset.model_validate(changed.model_dump())


def test_boundary_touching_is_not_overlap():
    d = fixture(compatible=False)
    assert not verify(
        d, [Assignment(task_id="A", start=0, end=4), Assignment(task_id="B", start=4, end=8)]
    )


def test_compatibility_is_not_transitive():
    d = fixture()
    d.resources[0].capacity = 3
    d.tasks.append(
        Task(
            id="C",
            title="Traction",
            department="TRD",
            section_id="S",
            activity="TRD",
            duration=4,
            deadline=16,
            demands={"R": 1},
        )
    )
    d.compatible.append(("ENG", "TRD"))
    plan = solve(d)
    by_id = {a.task_id: a for a in plan.assignments}
    assert plan.verified and plan.metrics["downtime_minutes"] == 120
    b, c = by_id["B"], by_id["C"]
    assert b.end <= c.start or c.end <= b.start


def test_task_must_fit_one_window():
    d = fixture(duration=4)
    d.sections[0].windows = [Window(start=0, end=3), Window(start=4, end=7)]
    assert solve(d).status == "INFEASIBLE"


def test_resources_are_shared_across_sections():
    d = fixture(capacity=1)
    d.sections.append(d.sections[0].model_copy(update={"id": "OTHER"}))
    d.tasks[1].section_id = "OTHER"
    plan = solve(d)
    a, b = plan.assignments
    assert a.end <= b.start or b.end <= a.start


def test_overrun_counts_as_changed_even_with_same_start():
    d = fixture()
    parent = solve(d)
    changed = disrupt(d, Disruption(kind="task_overrun", target_id="A", magnitude=1))
    result = solve(changed, baseline=parent)
    assert result.verified
    assert result.objective["changed"] == result.metrics["changed_tasks"] * 1000


def test_locked_deferred_task_stays_absent():
    d = fixture(duration=10, compatible=False)
    d.tasks[1].required = False
    parent = solve(d)
    d.tasks[0].duration = 2
    recovered = solve(d, SolveOptions(locked_task_ids=["B"]), parent)
    assert recovered.verified and recovered.deferred == ["B"]
