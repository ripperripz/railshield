"""Measured seeded solver smoke benchmark, with independent verification."""
import argparse
import json
import platform
import time
from pathlib import Path

import ortools

from app.domain import GenerateRequest, SolveOptions
from app.ingestion.synthetic import generate
from app.optimization.solver import solve
from app.optimization.verify import verify

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path)
parser.add_argument("--tasks", type=int, default=12)
parser.add_argument("--seconds", type=float, default=3)
args = parser.parse_args()
dataset = generate(GenerateRequest(tasks=args.tasks, sections=4, days=7, trains=16))
results = {}
for label, independent in [("independent", True), ("coordinated", False)]:
    started = time.perf_counter()
    plan = solve(dataset, SolveOptions(time_limit=args.seconds, independent=independent))
    assert plan.verified, plan.diagnostics
    assert not verify(dataset, plan.assignments, independent=independent)
    results[label] = {"status": plan.status, "metrics": plan.metrics,
                      "objective": plan.objective_value, "bound": plan.best_bound,
                      "wall_seconds": time.perf_counter()-started,
                      "solver_seconds": plan.solver_seconds}
report = {"seed": 42, "tasks": args.tasks, "python": platform.python_version(),
          "ortools": ortools.__version__, "results": results,
          "note": "Synthetic experiment; timings vary by hardware. FEASIBLE is not OPTIMAL."}
content = json.dumps(report, indent=2)+"\n"
if args.output:
    args.output.write_text(content)
print(content)
