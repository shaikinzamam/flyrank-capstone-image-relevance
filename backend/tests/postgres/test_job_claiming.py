import os
from datetime import datetime, timedelta, timezone
from threading import Barrier, Lock, Thread
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker

from app.models.image_asset import ImageAsset
from app.models.processing_job import ProcessingJob, ProcessingJobItem
from app.repositories.processing_jobs import ProcessingJobRepository

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_POSTGRES_CONCURRENCY") != "1",
    reason="requires an explicitly enabled migrated PostgreSQL database",
)


def test_two_postgres_workers_cannot_claim_the_same_item() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_engine(database_url, pool_pre_ping=True)
    sessions = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )
    unique = uuid4().hex
    asset_id = uuid4()
    with sessions() as session:
        asset = ImageAsset(
            id=asset_id,
            filename=f"claim-{unique}.png",
            storage_key=f"test/{unique}.png",
            mime_type="image/png",
            byte_size=1,
            sha256=unique.ljust(64, "0"),
            processing_status="uploaded",
        )
        job = ProcessingJob(
            total_items=1,
            idempotency_key=f"postgres-claim-{unique}",
            items=[
                ProcessingJobItem(
                    image_id=asset.id,
                    max_attempts=3,
                    # Avoid host/container subsecond clock skew in this fixture.
                    available_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                )
            ],
        )
        session.add_all([asset, job])
        session.commit()
        job_id = job.id

    barrier = Barrier(3)
    result_lock = Lock()
    claims: list[object] = []

    def claim(worker_id: str) -> None:
        with sessions() as session:
            barrier.wait()
            result = ProcessingJobRepository(session).claim_next(
                worker_id=worker_id,
                lease_seconds=60,
            )
            with result_lock:
                claims.append(result)

    threads = [
        Thread(target=claim, args=("postgres-worker-a",)),
        Thread(target=claim, args=("postgres-worker-b",)),
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=10)

    try:
        assert all(not thread.is_alive() for thread in threads)
        assert len(claims) == 2
        assert sum(claim is not None for claim in claims) == 1
    finally:
        with sessions() as session:
            session.execute(delete(ProcessingJob).where(ProcessingJob.id == job_id))
            session.execute(delete(ImageAsset).where(ImageAsset.id == asset_id))
            session.commit()
        engine.dispose()
