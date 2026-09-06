import csv
import json
import random
from datetime import datetime
from pathlib import Path

from app.domain import Dataset, Department, GenerateRequest, Resource, Section, Task, Train, Window


def generate(config: GenerateRequest) -> Dataset:
    rng = random.Random(config.seed)
    horizon = config.days * 96
    stations = ["Ambala", "Barara", "Jagadhri", "Saharanpur", "Roorkee", "Laksar"]
    sections = [
        Section(
            id=f"SEC-{i + 1:02}",
            name=f"Corridor {i + 1:02}",
            from_station=stations[i % len(stations)],
            to_station=stations[(i + 1) % len(stations)],
            windows=[Window(start=d * 96 + 4, end=d * 96 + 28) for d in range(config.days)],
        )
        for i in range(config.sections)
    ]
    resources = [
        Resource(id=f"CREW-{d}", name=f"{d} field teams", capacity=3) for d in ("ENG", "TRD", "SNT")
    ]
    tasks = []
    labels = {
        "ENG": "Track geometry correction",
        "TRD": "OHE inspection",
        "SNT": "Signal servicing",
    }
    for i in range(config.tasks):
        departments: tuple[Department, ...] = ("ENG", "SNT", "TRD")
        dept = departments[i % 3]
        week = (i // (config.sections * 3)) % max(1, (config.days + 6) // 7)
        earliest = min(week * 672, horizon - 96)
        tasks.append(
            Task(
                id=f"{dept}-{i + 1:03}",
                title=labels[dept],
                department=dept,
                section_id=sections[(i // 3) % config.sections].id,
                activity=dept,
                duration=rng.randint(3, 6),
                earliest=earliest,
                deadline=min(horizon, earliest + 672),
                priority=rng.randint(4, 10),
                required=i % 7 != 6,
                demands={f"CREW-{dept}": 1},
            )
        )
    trains = []
    for i in range(config.trains):
        day = rng.randrange(config.days)
        start = day * 96 + rng.choice([3, 12, 24, 36, 48, 72])
        trains.append(
            Train(
                id=f"TRAIN-{i + 1:03}",
                section_id=rng.choice(sections).id,
                start=start,
                end=start + 2,
            )
        )
    return Dataset(
        name=f"Northern corridor · seed {config.seed}",
        seed=config.seed,
        epoch=datetime.fromisoformat("2026-09-07T00:00:00+05:30"),
        horizon=horizon,
        sections=sections,
        resources=resources,
        tasks=tasks,
        trains=trains,
        compatible=[("ENG", "SNT"), ("ENG", "TRD")],
    )


def export(dataset: Dataset, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "dataset.json").write_text(dataset.model_dump_json(indent=2) + "\n")
    tables = {
        "assets": [s.model_dump(exclude={"windows"}) for s in dataset.sections],
        "coa": [
            {"section_id": s.id, **w.model_dump()} for s in dataset.sections for w in s.windows
        ],
        "trains": [t.model_dump() for t in dataset.trains],
        "resources": [r.model_dump() for r in dataset.resources],
    }
    for source, dept in [("tms", "ENG"), ("smms", "SNT"), ("tdms", "TRD")]:
        tables[source] = [t.model_dump() for t in dataset.tasks if t.department == dept]
    for name, rows in tables.items():
        with (directory / f"{name}.csv").open("w", newline="") as handle:
            if rows:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(
                    {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()}
                    for row in rows
                )
