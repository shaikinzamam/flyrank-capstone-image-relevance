from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import UUID

from PIL import Image
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.image_metadata import AiCallLog, ImageMetadata
from app.models.image_asset import ImageAsset
from app.models.processing_job import ProcessingJob, ProcessingJobItem
from app.providers.fake import FakeVisionProvider
from app.providers.vision import ProviderFailureError
from app.repositories.processing_jobs import ProcessingJobRepository
from app.workers.image_processing import ImageProcessingWorker
from tests.conftest import ImageApiContext


VALID_METADATA = {
    "subject": "red fox",
    "subject_code": "red_fox",
    "category": "animal",
    "caption": "A red fox processed by the worker",
    "tags": ["red fox", "worker"],
    "attributes": ["orange fur"],
    "objects": ["fox"],
    "confidence": 0.94,
}


def upload_image(context: ImageApiContext, color: str = "red") -> dict:
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=color).save(buffer, format="PNG")
    response = context.client.post(
        "/images",
        files={"file": (f"{color}.png", buffer.getvalue(), "image/png")},
    )
    assert response.status_code == 201
    return response.json()


def queue_job(
    context: ImageApiContext,
    image_ids: list[str],
    key: str,
) -> dict:
    response = context.client.post(
        "/images/process",
        json={"image_ids": image_ids, "idempotency_key": key},
    )
    assert response.status_code == 202
    return response.json()


def worker(
    context: ImageApiContext,
    provider: FakeVisionProvider,
    *,
    budget: float | None = None,
    worker_id: str = "test-worker",
) -> ImageProcessingWorker:
    settings = get_settings().model_copy(
        update={
            "vision_budget_usd": budget,
            "processing_initial_backoff_seconds": 1,
            "processing_max_backoff_seconds": 4,
        }
    )
    return ImageProcessingWorker(
        worker_id,
        session_factory=context.session_factory,
        settings=settings,
        provider=provider,
        storage=context.storage,
    )


def force_retry_available(context: ImageApiContext, job_id: str) -> None:
    with context.session_factory() as session:
        item = session.scalar(
            select(ProcessingJobItem).where(
                ProcessingJobItem.job_id == UUID(job_id)
            )
        )
        assert item is not None
        item.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()


def test_worker_claims_and_successfully_completes_job(
    image_api: ImageApiContext,
) -> None:
    image = upload_image(image_api)
    job = queue_job(image_api, [image["id"]], "success")
    provider = FakeVisionProvider(VALID_METADATA)

    assert worker(image_api, provider).process_one() is True

    with image_api.session_factory() as session:
        persisted_job = session.get(ProcessingJob, UUID(job["id"]))
        assert persisted_job is not None
        assert persisted_job.status == "completed"
        assert persisted_job.processed_items == 1
        assert persisted_job.failed_items == 0
        item = session.scalar(
            select(ProcessingJobItem).where(
                ProcessingJobItem.job_id == UUID(job["id"])
            )
        )
        assert item is not None
        assert item.status == "succeeded"
        assert item.attempt_count == 1
        assert session.scalar(select(func.count()).select_from(ImageMetadata)) == 1
        call = session.scalar(select(AiCallLog))
        assert call is not None
        assert call.status == "succeeded"
        assert call.retry_count == 0


def test_job_completes_after_all_batch_items_succeed(
    image_api: ImageApiContext,
) -> None:
    first = upload_image(image_api, "red")
    second = upload_image(image_api, "blue")
    job = queue_job(image_api, [first["id"], second["id"]], "batch-success")
    processing_worker = worker(image_api, FakeVisionProvider(VALID_METADATA))

    assert processing_worker.process_one() is True
    assert processing_worker.process_one() is True

    with image_api.session_factory() as session:
        persisted_job = session.get(ProcessingJob, UUID(job["id"]))
        assert persisted_job is not None
        assert persisted_job.status == "completed"
        assert persisted_job.processed_items == 2
        assert persisted_job.failed_items == 0


def test_active_lease_prevents_second_worker_claim(
    image_api: ImageApiContext,
) -> None:
    image = upload_image(image_api)
    queue_job(image_api, [image["id"]], "active-lease")

    with image_api.session_factory() as first_session:
        first = ProcessingJobRepository(first_session).claim_next(
            worker_id="worker-a", lease_seconds=60
        )
    with image_api.session_factory() as second_session:
        second = ProcessingJobRepository(second_session).claim_next(
            worker_id="worker-b", lease_seconds=60
        )

    assert first is not None
    assert second is None


def test_abandoned_lease_can_be_reclaimed(image_api: ImageApiContext) -> None:
    image = upload_image(image_api)
    job = queue_job(image_api, [image["id"]], "abandoned")
    with image_api.session_factory() as session:
        first = ProcessingJobRepository(session).claim_next(
            worker_id="worker-a", lease_seconds=60
        )
    assert first is not None
    with image_api.session_factory() as session:
        item = session.get(ProcessingJobItem, first.id)
        assert item is not None
        item.leased_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()
    with image_api.session_factory() as session:
        second = ProcessingJobRepository(session).claim_next(
            worker_id="worker-b", lease_seconds=60
        )

    assert second is not None
    assert second.id == first.id
    assert second.lease_token != first.lease_token
    assert second.attempt_count == 2
    assert second.job_id == UUID(job["id"])


def test_worker_recovers_abandoned_processing_state(
    image_api: ImageApiContext,
) -> None:
    image = upload_image(image_api)
    job = queue_job(image_api, [image["id"]], "recovery")
    with image_api.session_factory() as session:
        first = ProcessingJobRepository(session).claim_next(
            worker_id="crashed-worker", lease_seconds=60
        )
    assert first is not None
    with image_api.session_factory() as session:
        item = session.get(ProcessingJobItem, first.id)
        asset = session.get(ImageAsset, UUID(image["id"]))
        assert item is not None and asset is not None
        item.leased_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        asset.processing_status = "processing"
        session.commit()

    provider = FakeVisionProvider(VALID_METADATA)
    assert worker(image_api, provider, worker_id="recovery-worker").process_one()

    with image_api.session_factory() as session:
        persisted_job = session.get(ProcessingJob, UUID(job["id"]))
        item = session.get(ProcessingJobItem, first.id)
        call = session.scalar(select(AiCallLog))
        assert persisted_job is not None and item is not None and call is not None
        assert persisted_job.status == "completed"
        assert item.status == "succeeded"
        assert item.attempt_count == 2
        assert call.retry_count == 1


def test_transient_failure_retries_then_succeeds(
    image_api: ImageApiContext,
) -> None:
    image = upload_image(image_api)
    job = queue_job(image_api, [image["id"]], "retry-success")
    provider = FakeVisionProvider(ProviderFailureError("temporary outage"))
    processing_worker = worker(image_api, provider)

    assert processing_worker.process_one() is True
    with image_api.session_factory() as session:
        item = session.scalar(
            select(ProcessingJobItem).where(
                ProcessingJobItem.job_id == UUID(job["id"])
            )
        )
        assert item is not None
        assert item.status == "retry_scheduled"
        assert item.attempt_count == 1

    provider.output = VALID_METADATA
    force_retry_available(image_api, job["id"])
    assert processing_worker.process_one() is True

    with image_api.session_factory() as session:
        item = session.scalar(
            select(ProcessingJobItem).where(
                ProcessingJobItem.job_id == UUID(job["id"])
            )
        )
        assert item is not None
        assert item.status == "succeeded"
        assert item.attempt_count == 2
        calls = list(session.scalars(select(AiCallLog).order_by(AiCallLog.created_at)))
        assert [call.status for call in calls] == ["failed", "succeeded"]
        assert [call.retry_count for call in calls] == [0, 1]


def test_permanent_failure_is_not_retried(image_api: ImageApiContext) -> None:
    image = upload_image(image_api)
    job = queue_job(image_api, [image["id"]], "permanent")
    provider = FakeVisionProvider("not-json")
    processing_worker = worker(image_api, provider)

    assert processing_worker.process_one() is True
    assert processing_worker.process_one() is False

    with image_api.session_factory() as session:
        item = session.scalar(
            select(ProcessingJobItem).where(
                ProcessingJobItem.job_id == UUID(job["id"])
            )
        )
        assert item is not None
        assert item.status == "failed"
        assert item.attempt_count == 1
        persisted_job = session.get(ProcessingJob, UUID(job["id"]))
        assert persisted_job is not None
        assert persisted_job.status == "failed"


def test_retry_exhaustion_marks_item_failed(image_api: ImageApiContext) -> None:
    image = upload_image(image_api)
    job = queue_job(image_api, [image["id"]], "exhaustion")
    with image_api.session_factory() as session:
        item = session.scalar(
            select(ProcessingJobItem).where(
                ProcessingJobItem.job_id == UUID(job["id"])
            )
        )
        assert item is not None
        item.max_attempts = 2
        session.commit()
    provider = FakeVisionProvider(ProviderFailureError("still unavailable"))
    processing_worker = worker(image_api, provider)

    assert processing_worker.process_one() is True
    force_retry_available(image_api, job["id"])
    assert processing_worker.process_one() is True

    with image_api.session_factory() as session:
        item = session.scalar(
            select(ProcessingJobItem).where(
                ProcessingJobItem.job_id == UUID(job["id"])
            )
        )
        assert item is not None
        assert item.status == "failed"
        assert item.attempt_count == 2


def test_partial_failure_completes_with_errors(image_api: ImageApiContext) -> None:
    first = upload_image(image_api, "red")
    second = upload_image(image_api, "blue")
    job = queue_job(image_api, [first["id"], second["id"]], "partial")
    outputs = iter([VALID_METADATA, "not-json"])
    provider = FakeVisionProvider(VALID_METADATA)
    provider.output = lambda: next(outputs)

    original_analyze = provider.analyze

    def analyze(path, mime_type):
        provider.output = next(outputs)
        return original_analyze(path, mime_type)

    provider.analyze = analyze
    processing_worker = worker(image_api, provider)
    assert processing_worker.process_one() is True
    assert processing_worker.process_one() is True

    with image_api.session_factory() as session:
        persisted_job = session.get(ProcessingJob, UUID(job["id"]))
        assert persisted_job is not None
        assert persisted_job.status == "completed_with_errors"
        assert persisted_job.processed_items == 1
        assert persisted_job.failed_items == 1


def test_budget_exhaustion_prevents_provider_call(
    image_api: ImageApiContext,
) -> None:
    image = upload_image(image_api)
    job = queue_job(image_api, [image["id"]], "budget")
    provider = FakeVisionProvider(VALID_METADATA, estimated_cost_usd=0.6)

    assert worker(image_api, provider, budget=0.5).process_one() is True

    assert provider.call_count == 0
    with image_api.session_factory() as session:
        item = session.scalar(
            select(ProcessingJobItem).where(
                ProcessingJobItem.job_id == UUID(job["id"])
            )
        )
        assert item is not None
        assert item.status == "failed"
        assert item.last_error_code == "budget_exhausted"
        assert session.scalar(select(func.count()).select_from(AiCallLog)) == 0


def test_inaccessible_image_is_permanent_failure_without_ai_call(
    image_api: ImageApiContext,
) -> None:
    image = upload_image(image_api)
    job = queue_job(image_api, [image["id"]], "missing-file")
    (image_api.storage.root / image["storage_key"]).unlink()
    provider = FakeVisionProvider(VALID_METADATA)

    assert worker(image_api, provider).process_one() is True

    assert provider.call_count == 0
    with image_api.session_factory() as session:
        item = session.scalar(
            select(ProcessingJobItem).where(
                ProcessingJobItem.job_id == UUID(job["id"])
            )
        )
        assert item is not None
        assert item.status == "failed"
        assert item.last_error_code == "invalid_image_state"
