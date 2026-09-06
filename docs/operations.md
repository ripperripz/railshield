# Operations runbook

## Configuration

Backend settings use `RAILSHIELD_` prefixes. `DATABASE_URL`, `ENVIRONMENT`, `API_KEY`, `CORS_ORIGINS`, `MAX_PENDING_JOBS`, `MAX_BODY_BYTES` and `JOB_LEASE_SECONDS` are defined in `backend/app/config.py`. Local `.env` loading is relative to the process working directory; the Makefile runs backend commands from `backend/`. Compose injects variables from the root `.env` explicitly.

Run `alembic upgrade head` before starting production services. `alembic check` detects model/schema drift. Never use development `create_all` to upgrade a production database. The initial downgrade drops data; back up before using any downgrade.

## Health and failures

- `/health/live` confirms the API process is alive.
- `/health/ready` checks database access and the dataset table.
- Queued jobs require a running worker (`python -m app.worker`). API readiness does not assert worker liveness.
- Inspect `docker compose logs worker` and `/api/v1/jobs/{id}` when jobs stall.
- Running jobs whose lease expires are marked failed by the next worker poll. Submit a new job after investigating; historical results are never overwritten.
- Infeasible solver output is a completed computation, not infrastructure failure. Change inputs/locks explicitly and create a new version.
- Shutdown grants the worker 90 seconds in Compose. Interrupted work is recovered as an expired job, not falsely marked complete.

For PostgreSQL, workers claim with row locks and completion tokens; multiple workers can be used after load testing. SQLite permits only one API process and one worker. Bound CPU/memory and ingress rates when exposing a deployment. There is a queue size guard, but no per-user quota or multi-tenant isolation.

## Backup and restore

Use PostgreSQL tools matching your deployed major version. Store backups outside the container and test restoration into an isolated database.

```bash
docker compose exec -T db pg_dump -U railshield -d railshield -Fc > railshield-backup.dump
# Restore only into an empty, separately prepared database after reviewing the target.
# pg_restore --dbname=<restore target> railshield-backup.dump
```

The named `postgres-data` volume survives `docker compose down`. `docker compose down -v` destroys it; use that only for disposable CI/test deployments. Application JSON exports supplement, but do not replace, full database backups.

## Before an operational pilot

Obtain railway-approved constraint semantics, data contracts and operational validation. Add per-user identity, authorization, approval workflows, auditable publishing, source-data freshness gates and monitored worker health. Validate multi-track capacity, electrical isolation, safety margins and track/route conflict semantics with domain owners. Benchmark representative datasets and design decomposition if the bounded discrete model is insufficient. Pin container digests for a deployment release and scan transitive dependencies and images.
