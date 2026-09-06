# RailShield technical plan

## Scope and acceptance
Build a reproducible SIH26027 decision-support repository with an end-to-end local demo: import/generate data → monthly commitments → detailed coordinated scheduling → independent baseline → fixed-plan stress tests → stability-aware recovery → auditable results. Synthetic data is explicitly labelled. A feasible result must pass a separate constraint checker before persistence. Operational railway deployment requires validated railway rules, real data agreements and authority approval; this repository does not issue operational movement authorities.

## Architecture
- Python 3.12, FastAPI, Pydantic contracts, SQLAlchemy, Alembic, PostgreSQL in Compose; SQLite for lightweight local development.
- OR-Tools CP-SAT in a pure domain package. Integer 15-minute slots; half-open intervals. Validated input limits bound model construction and solver duration.
- React, TypeScript, Vite, TanStack Query, Lucide icons and a custom accessible slot timeline. Use upstream FastAPI/OR-Tools examples as architectural references, install libraries, never copy another SIH solution.
- Durable database job queue processed outside the web process; persisted immutable dataset/plan snapshots and audit records. PostgreSQL row claims support concurrent workers; one worker for SQLite.
- Production bearer-key authentication, explicit development mode, CORS allowlist, request limits, error handling, readiness checks and container health checks.

## Scheduling formulation
For each task enumerate starts that fit a corridor, task release/deadline and train exclusions. Optional tasks may defer with a priority-weighted penalty; required tasks must execute. Candidate Booleans link to per-slot resource demand and section occupation. Same-section overlap requires an explicit symmetric activity compatibility rule; all pairs must be compatible. Section occupancy is a Boolean OR of active work, charging the union once. Fragmentation counts occupation starts. Crews use per-slot capacity constraints. Predecessor completion and predecessor presence are mandatory for successors.

Monthly CP-SAT assigns tasks to eligible weeks using conservative section-minute budgets and per-resource crew-minute budgets. These are advisory allocations: exact feasibility is only established by the detailed solver. Detailed scheduling covers the full input horizon so cross-week dependencies are maintained; deviations from monthly commitments are penalized. The UI shows selected weekly slices.

Recovery solves a disrupted snapshot against an immutable parent. Locked tasks retain start and presence; impossible locks produce infeasibility, never silently unlock. Objective includes changed task count and displacement. Compare to a full replan on the same disrupted input. Fixed-plan stress testing measures violations before any recovery and reports observed results only.

## Build sequence
1. Contracts and seeded synthetic JSON/CSV generator with explicit units and cross-reference validation.
2. CP-SAT core, independent baseline, independent verifier, fixtures and property tests.
3. Monthly allocator, stress scenarios, recovery and diff metrics.
4. Persistent API, migrations, job worker, authentication and integration tests.
5. Planning dashboard, timeline, topology, data import/export, disruption lab and browser tests.
6. Docker, CI, benchmark smoke, licenses, runbook and model limitations.

## Validation gates
Ruff, mypy, pytest/Hypothesis; TypeScript and ESLint; Playwright against the real API and worker; seeded solver benchmark with checker; frontend production build. Report any environment-blocked checks rather than claiming them complete.
