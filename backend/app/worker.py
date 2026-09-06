"""Durable job worker. Run separately from the API. SQLite supports one worker."""

import logging
import time
from datetime import timedelta

from sqlalchemy import select, update

from app.config import settings
from app.db import AuditRow, DatasetRow, JobRow, identifier, now, session_factory
from app.domain import Dataset
from app.service import execute

log = logging.getLogger("railshield.worker")


def run_once() -> bool:
    factory = session_factory()
    with factory.begin() as session:
        expired = now() - timedelta(seconds=settings().job_lease_seconds)
        session.execute(
            update(JobRow)
            .where(JobRow.status == "running", JobRow.started_at < expired)
            .values(
                status="failed",
                error="Worker lease expired; submit a new job",
                completed_at=now(),
                claim_token=None,
            )
        )
        job = session.scalar(
            select(JobRow)
            .where(JobRow.status == "queued")
            .order_by(JobRow.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return False
        token = identifier()
        job.status, job.started_at, job.claim_token = "running", now(), token
        job_id, kind, request = job.id, job.kind, job.request
        row = session.get(DatasetRow, job.dataset_id)
        if row is None:
            raise RuntimeError("Dataset foreign key missing")
        dataset = Dataset.model_validate(request.get("parent_dataset", row.payload))
    try:
        result, error = execute(dataset, kind, request), None
    except ValueError as exc:
        result, error = None, str(exc)[:500]
    except Exception:
        log.exception("Job %s failed", job_id)
        result, error = None, "Planning failed; inspect worker logs using the job ID"
    with factory.begin() as session:
        updated = session.execute(
            update(JobRow)
            .where(JobRow.id == job_id, JobRow.status == "running", JobRow.claim_token == token)
            .values(
                result=result,
                error=error,
                completed_at=now(),
                status="failed" if error else "completed",
            )
        )
        if updated.rowcount:
            session.add(
                AuditRow(
                    action="job.failed" if error else "job.completed",
                    entity_id=job_id,
                    detail={"kind": kind},
                )
            )
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    log.info("RailShield worker started")
    while True:
        try:
            if not run_once():
                time.sleep(0.5)
        except KeyboardInterrupt:
            return
        except Exception:
            log.exception("Worker polling error")
            time.sleep(3)


if __name__ == "__main__":
    main()
