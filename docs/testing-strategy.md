# Verification strategy

The solver is tested against independent invariants and small known outcomes, not only HTTP status codes. Tests cover exact shared union downtime, incompatible work, crew limits, train exclusion, presence-aware dependencies, deferral/infeasibility, immutable locks including duration changes, seeded scenarios, monthly refinement, and half-open boundaries. Hypothesis varies durations, capacities and compatibility and compares to analytically known outcomes.

API tests use temporary databases and a real worker iteration, exercising dataset validation, queued execution, persisted plans, parent lineage, stress jobs, audit events, auth failure, production configuration and body limits. PostgreSQL migration and concurrent worker smoke checks complement SQLite integration tests.

Playwright imports a dataset file, builds monthly commitments, generates a verified schedule, runs stress scenarios, recovers, downloads JSON and inspects history. It also checks mobile navigation and page overflow. Screenshot artifacts are captured for visual review. These are real API/worker tests, with no mocked solver results.

`make benchmark` saves measured seed-42 results in `datasets/benchmark-smoke.json`. Report task counts, scheduled work, status and bound alongside savings. Runtime measurements vary with hardware and concurrent load. Full-scale 100+ task benchmarks and long scenario campaigns belong outside per-commit CI.

CI has backend lint/types/tests/benchmark, frontend lint/types/build/Chromium, and PostgreSQL Compose startup/health jobs. No secrets are committed; CI generates ephemeral database/key values. Docker execution requires a Docker-enabled runner. See `docs/verification.md` for checks actually performed during this build.
