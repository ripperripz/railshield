# RailShield

**Coordinated railway maintenance planning for SIH26027.** A working full-stack decision-support application with OR-Tools CP-SAT, explicit department compatibility, monthly commitments, fixed-plan scenario experiments and stability-aware recovery.

The repository includes the API, durable worker, React dashboard, PostgreSQL migrations, reproducible synthetic data, tests, CI, containers and technical documentation. It is a tested engineering foundation, not an approved railway control system. Real railway integrations and operating rules remain deployment prerequisites.

## Run locally

Requirements: Python 3.12 or 3.13, [uv](https://docs.astral.sh/uv/), Node.js 22.12+ (or 24), npm.

```bash
make setup
make dev
```

Open [RailShield](http://localhost:5173). API docs: [OpenAPI](http://localhost:8000/docs). `Ctrl+C` stops all three services. Local development uses `backend/railshield.db` (SQLite), creates its schema automatically, and runs without authentication unless `RAILSHIELD_API_KEY` is set. Bind local services to loopback only. Use one API process and one worker with SQLite.

1. Create a demo dataset or import `datasets/demo/dataset.json` through Data sources.
2. Build monthly commitments, then Generate plan. Exact planning spans the dataset horizon; the timeline displays daily slices.
3. Inspect a timeline task and lock it for recovery if desired.
4. Open Disruption lab, run a stress test, then inject an overrun and Recover plan.
5. Open Plan history to inspect prior runs, or export the current plan JSON.

## PostgreSQL / container deployment

```bash
cp .env.example .env
# Replace both placeholder secrets with separate random values, e.g. openssl rand -hex 32.
# Use URL-safe characters in POSTGRES_PASSWORD, or URL-encode the connection string.
docker compose up --build -d --wait
```

Open [RailShield on port 8080](http://localhost:8080). In Connection settings, enter the API key from `.env`. Compose runs a migration job before API/worker startup and persists PostgreSQL in a named volume. The port binds to localhost; use an authenticated TLS reverse proxy for remote access. Do not commit `.env`.

Production configuration fails closed unless a key of at least 32 characters and PostgreSQL are configured. Authentication is a shared deployment key, not multi-user identity or role-based authorization. See [operations](docs/operations.md) before deployment.

## Vercel hosted demo

The repository also has a Vercel-native deployment profile. Vercel builds the Vite app from
`frontend/` and exposes `api/index.py` as one FastAPI function. Hosted planning runs execute
synchronously and keep datasets and plan history in browser local storage. Each request carries its
complete validated snapshot, so the hosted demo does not depend on Vercel's ephemeral filesystem or
a worker that cannot stay alive between invocations.

```bash
npx vercel@latest deploy --prod
```

The public profile is intentionally bounded to 60 tasks, 28 days, 20 stress scenarios, and eight
seconds per individual CP-SAT solve. Browser-local history is specific to one browser and origin;
export important results. Use the PostgreSQL deployment for shared durable history, multi-user
operations, or larger instances.

## Commands

```bash
make check       # Ruff, formatting, mypy, ESLint, TypeScript and Vite production build
make test        # pytest/Hypothesis + Playwright real API/worker flow
make benchmark   # seeded, verified independent/coordinated comparison
make demo        # regenerate JSON and source-shaped CSV fixtures
make schema      # export versioned dataset JSON Schema
```

First browser test run: `cd frontend && npx playwright install chromium`. Playwright starts API, worker and Vite automatically; stop `make dev` first to avoid a second SQLite worker. For larger experiments:

```bash
cd backend
uv run railshield generate --sections 12 --tasks 100 --trains 60 --days 28 --seed 42 --output ../datasets/generated/seed42
uv run railshield solve ../datasets/generated/seed42/dataset.json --seconds 30 --output ../datasets/generated/seed42/plan.json
```

Input limits are deliberate: 200 tasks, 20 sections, 31 days, 100,000 candidate starts and 2,000,000 slot contributions. Large instances may return FEASIBLE or UNKNOWN at the deadline. Only FEASIBLE/OPTIMAL solutions that pass the independent verifier are marked verified.

## What is implemented

| Capability | Behavior |
|---|---|
| Co-scheduling | Explicit symmetric activity compatibility, section occupation union, per-slot global resource capacity |
| Hard constraints | Corridor windows, train exclusion, task release/deadline, duration, required work, presence-aware precedence |
| Monthly → detail | Coarse CP-SAT weekly budgets; detailed full-horizon solver penalizes commitment deviation |
| Baseline | Identical instance and budget with section sharing disabled; compare matching completed task sets |
| Stress testing | Seeded train delays, task overruns, crew loss, corridor reductions and emergency tasks; fixed starts independently checked |
| Recovery | Immutable parent snapshot, hard locks, changed-task and displacement penalties; side-by-side unconstrained replan |
| Traceability | SHA-256 dataset fingerprints, durable job status, input/parent snapshots, objective terms, bounds and audit records |
| Dashboard | Live job polling, Cytoscape topology, daily slot timeline, register, objective weights, JSON import/export and history |

## Repository map

```text
backend/app/domain.py           Validated domain and API contracts
backend/app/optimization/       CP-SAT, monthly allocator, verifier, scenarios
backend/app/ingestion/          Seeded synthetic JSON/CSV exports
backend/app/main.py             Versioned API, authentication and request limits
backend/app/worker.py           Durable database queue worker
backend/migrations/            Alembic schema migrations
frontend/src/                  React workstation
frontend/e2e/                  Real browser workflow and responsive checks
datasets/demo/                 Seed 42 JSON + synthetic TMS/SMMS/TDMS/COA exports
scripts/                       Development runner and benchmark
.github/workflows/ci.yml        Backend, frontend/E2E and Compose checks
```

Start with the [technical plan](docs/technical-plan.md), [architecture](docs/architecture.md), [optimization model](docs/optimization-model.md), [data contracts](docs/data-contracts.md), [testing strategy](docs/testing-strategy.md) and [demo script](docs/demo-script.md). Reuse and licenses are recorded in [THIRD_PARTY.md](THIRD_PARTY.md). See the [verification record](docs/verification.md) for executed checks and environment limits.
