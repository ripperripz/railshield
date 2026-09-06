import argparse
import json
from pathlib import Path

from app.domain import Dataset, GenerateRequest, SolveOptions
from app.ingestion.synthetic import export, generate
from app.optimization.solver import solve


def main():
    parser = argparse.ArgumentParser(prog="railshield")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    for flag, default in [
        ("seed", 42),
        ("sections", 4),
        ("tasks", 24),
        ("trains", 28),
        ("days", 28),
    ]:
        gen.add_argument(f"--{flag}", type=int, default=default)
    gen.add_argument("--output", type=Path, default=Path("../datasets/demo"))
    opt = sub.add_parser("solve")
    opt.add_argument("dataset", type=Path)
    opt.add_argument("--seconds", type=float, default=10)
    opt.add_argument("--output", type=Path)
    sub.add_parser("init-db")
    schema = sub.add_parser("schema")
    schema.add_argument("--output", type=Path, default=Path("../datasets/schema.json"))
    args = parser.parse_args()
    if args.command == "generate":
        config = GenerateRequest(
            **{k: getattr(args, k) for k in ("seed", "sections", "tasks", "trains", "days")}
        )
        dataset = generate(config)
        export(dataset, args.output)
        print(f"Synthetic dataset exported to {args.output}")
    elif args.command == "solve":
        result = solve(
            Dataset.model_validate_json(args.dataset.read_text()),
            SolveOptions(time_limit=args.seconds),
        )
        content = result.model_dump_json(indent=2) + "\n"
        if args.output:
            args.output.write_text(content)
        else:
            print(content)
        if not result.verified:
            raise SystemExit(2)
    elif args.command == "schema":
        args.output.write_text(json.dumps(Dataset.model_json_schema(), indent=2) + "\n")
    else:
        from app.db import initialize

        initialize()
        print("Development database initialized")
