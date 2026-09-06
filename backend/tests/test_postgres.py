"""Opt-in checks against an isolated, migrated PostgreSQL database."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.config import settings
from app.db import AuditRow, DatasetRow, JobRow, engine, now, session_factory
from app.domain import GenerateRequest
from app.ingestion.synthetic import generate
from app.worker import run_once


@pytest.mark.skipif(
    not os.getenv("RAILSHIELD_TEST_POSTGRES_URL"), reason="isolated PostgreSQL not set"
)
def test_concurrent_claims_and_expired_lease(monkeypatch):
    monkeypatch.setenv("RAILSHIELD_DATABASE_URL", os.environ["RAILSHIELD_TEST_POSTGRES_URL"])
    settings.cache_clear()
    engine.cache_clear()
    try:
        dataset = generate(GenerateRequest(tasks=3, sections=1, trains=0, days=7))
        with session_factory().begin() as session:
            row = DatasetRow(
                name="PostgreSQL worker test",
                payload=dataset.model_dump(mode="json"),
                content_hash="test",
            )
            session.add(row)
            session.flush()
            jobs = [
                JobRow(dataset_id=row.id, kind="monthly", request={"options": {"time_limit": 1}})
                for _ in range(2)
            ]
            session.add_all(jobs)
            expired = JobRow(
                dataset_id=row.id,
                kind="monthly",
                request={},
                status="running",
                started_at=now() - timedelta(seconds=1000),
                claim_token="expired",
            )
            session.add(expired)
            session.flush()
            ids, expired_id = [j.id for j in jobs], expired.id
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(lambda _: run_once(), range(2))) == [True, True]
        with session_factory()() as session:
            for key in ids:
                job = session.get(JobRow, key)
                assert job.status == "completed" and job.result["commitments"]
                events = list(session.scalars(select(AuditRow).where(AuditRow.entity_id == key)))
                assert len(events) == 1 and events[0].action == "job.completed"
            assert session.get(JobRow, expired_id).status == "failed"
    finally:
        engine().dispose()
        engine.cache_clear()
        settings.cache_clear()
