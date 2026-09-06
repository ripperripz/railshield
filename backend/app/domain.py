"""Validated, storage-independent contracts. All times are integer slots from epoch."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Id = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]
Slot = Annotated[int, Field(ge=0, le=2976)]
Department = Literal["ENG", "TRD", "SNT"]
DisruptionKind = Literal[
    "train_delay", "task_overrun", "crew_loss", "corridor_reduction", "emergency"
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Window(Contract):
    start: Slot
    end: Slot

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("Window end must be after start")
        return self


class Section(Contract):
    id: Id
    name: str = Field(min_length=1, max_length=120)
    from_station: str = Field(min_length=1, max_length=80)
    to_station: str = Field(min_length=1, max_length=80)
    windows: list[Window] = Field(min_length=1, max_length=100)


class Resource(Contract):
    id: Id
    name: str = Field(min_length=1, max_length=120)
    capacity: int = Field(ge=0, le=100)


class Task(Contract):
    id: Id
    title: str = Field(min_length=1, max_length=160)
    department: Department
    section_id: Id
    activity: Id
    duration: int = Field(ge=1, le=192)
    earliest: Slot = 0
    deadline: Slot
    priority: int = Field(ge=1, le=10, default=5)
    required: bool = True
    demands: dict[Id, Annotated[int, Field(ge=1, le=100)]] = Field(default_factory=dict)
    predecessors: list[Id] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def ordered(self):
        if self.earliest >= self.deadline:
            raise ValueError("Task earliest must precede deadline")
        return self


class Train(Contract):
    id: Id
    section_id: Id
    start: Slot
    end: Slot

    @model_validator(mode="after")
    def ordered(self):
        if self.start >= self.end:
            raise ValueError("Train end must follow start")
        return self


class Dataset(Contract):
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=120)
    synthetic: bool = True
    seed: int | None = None
    epoch: datetime
    slot_minutes: Literal[15] = 15
    horizon: int = Field(ge=1, le=2976)
    sections: list[Section] = Field(min_length=1, max_length=20)
    resources: list[Resource] = Field(max_length=30)
    tasks: list[Task] = Field(min_length=1, max_length=200)
    trains: list[Train] = Field(default_factory=list, max_length=2000)
    compatible: list[tuple[Id, Id]] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def references(self):
        if self.epoch.tzinfo is None or self.epoch.utcoffset() is None:
            raise ValueError("epoch must include a timezone offset")
        for name in ("sections", "resources", "tasks", "trains"):
            items = getattr(self, name)
            if len({x.id for x in items}) != len(items):
                raise ValueError(f"Duplicate {name} IDs")
        sections = {s.id for s in self.sections}
        resources = {r.id for r in self.resources}
        tasks = {t.id: t for t in self.tasks}
        for section in self.sections:
            ordered = sorted(section.windows, key=lambda w: w.start)
            if any(w.end > self.horizon for w in ordered):
                raise ValueError("Corridor exceeds horizon")
            if any(a.end > b.start for a, b in zip(ordered, ordered[1:], strict=False)):
                raise ValueError("Corridor windows must not overlap")
        for t in self.tasks:
            if t.section_id not in sections or set(t.demands) - resources:
                raise ValueError(f"Unknown section or resource in {t.id}")
            if set(t.predecessors) - tasks.keys() or len(set(t.predecessors)) != len(
                t.predecessors
            ):
                raise ValueError(f"Invalid predecessors in {t.id}")
            if t.deadline > self.horizon:
                raise ValueError("Task deadline exceeds horizon")
        for train in self.trains:
            if train.section_id not in sections or train.end > self.horizon:
                raise ValueError("Invalid train section or horizon")
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(key: str):
            if key in visiting:
                raise ValueError("Precedence graph contains a cycle")
            if key in visited:
                return
            visiting.add(key)
            for pred in tasks[key].predecessors:
                visit(pred)
            visiting.remove(key)
            visited.add(key)

        for key in tasks:
            visit(key)
        return self


class Weights(Contract):
    downtime: int = Field(default=10, ge=0, le=1000)
    fragmentation: int = Field(default=5, ge=0, le=1000)
    deferral: int = Field(default=10000, ge=1, le=100000)
    commitment: int = Field(default=100, ge=0, le=10000)
    changed: int = Field(default=1000, ge=0, le=100000)
    displacement: int = Field(default=2, ge=0, le=1000)


class Assignment(Contract):
    task_id: Id
    start: Slot
    end: Slot


class Block(Contract):
    section_id: Id
    start: Slot
    end: Slot
    task_ids: list[str]


class Plan(Contract):
    status: str
    assignments: list[Assignment] = Field(default_factory=list)
    deferred: list[str] = Field(default_factory=list)
    blocks: list[Block] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    objective: dict[str, float] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)
    solver_seconds: float = 0
    best_bound: float | None = None
    objective_value: float | None = None
    verified: bool = False


class SolveOptions(Contract):
    time_limit: float = Field(default=10, ge=0.1, le=30)
    seed: int = Field(default=42, ge=0, le=2147483647)
    independent: bool = False
    weights: Weights = Field(default_factory=Weights)
    commitments: dict[Id, Annotated[int, Field(ge=0, le=4)]] = Field(default_factory=dict)
    locked_task_ids: list[Id] = Field(default_factory=list, max_length=200)


class Disruption(Contract):
    kind: DisruptionKind
    magnitude: int = Field(default=2, ge=1, le=12)
    target_id: Id | None = None


class GenerateRequest(Contract):
    seed: int = Field(default=42, ge=0, le=2147483647)
    sections: int = Field(default=4, ge=1, le=12)
    tasks: int = Field(default=24, ge=1, le=200)
    trains: int = Field(default=28, ge=0, le=500)
    days: int = Field(default=28, ge=1, le=31)
