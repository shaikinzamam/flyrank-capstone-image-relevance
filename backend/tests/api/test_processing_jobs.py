from io import BytesIO
from uuid import uuid4

from PIL import Image
from sqlalchemy import func, select

from app.models.processing_job import ProcessingJob, ProcessingJobItem
from tests.conftest import ImageApiContext


def upload_image(context: ImageApiContext, color: str) -> dict:
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=color).save(buffer, format="PNG")
    response = context.client.post(
        "/images",
        files={"file": (f"{color}.png", buffer.getvalue(), "image/png")},
    )
    assert response.status_code == 201
    return response.json()


def create_job(context: ImageApiContext, image_ids: list[str], key: str = "job-key"):
    return context.client.post(
        "/images/process",
        json={"image_ids": image_ids, "idempotency_key": key},
    )


def test_job_creation_returns_202_with_multiple_items(
    image_api: ImageApiContext,
) -> None:
    first = upload_image(image_api, "red")
    second = upload_image(image_api, "blue")

    response = create_job(image_api, [first["id"], second["id"]])

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["total_items"] == 2
    assert body["processed_items"] == 0
    assert body["failed_items"] == 0
    assert body["progress"] == 0
    with image_api.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ProcessingJob)) == 1
        assert (
            session.scalar(select(func.count()).select_from(ProcessingJobItem)) == 2
        )


def test_duplicate_idempotency_key_reuses_one_logical_job(
    image_api: ImageApiContext,
) -> None:
    first = upload_image(image_api, "red")
    second = upload_image(image_api, "blue")
    image_ids = [first["id"], second["id"]]

    created = create_job(image_api, image_ids, "same-request")
    repeated = create_job(image_api, list(reversed(image_ids)), "same-request")

    assert created.status_code == 202
    assert repeated.status_code == 202
    assert repeated.json()["id"] == created.json()["id"]
    assert repeated.json()["reused"] is True
    with image_api.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ProcessingJob)) == 1


def test_idempotency_key_rejects_a_different_image_set(
    image_api: ImageApiContext,
) -> None:
    first = upload_image(image_api, "red")
    second = upload_image(image_api, "blue")
    assert create_job(image_api, [first["id"]], "conflict-key").status_code == 202

    response = create_job(image_api, [second["id"]], "conflict-key")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Idempotency key was already used for a different image set"
    }


def test_job_creation_rejects_missing_image(image_api: ImageApiContext) -> None:
    response = create_job(image_api, [str(uuid4())], "missing-image")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "One or more requested image assets were not found"
    }


def test_job_and_item_inspection(image_api: ImageApiContext) -> None:
    image = upload_image(image_api, "red")
    created = create_job(image_api, [image["id"]], "inspect").json()

    job = image_api.client.get(f"/jobs/{created['id']}")
    items = image_api.client.get(f"/jobs/{created['id']}/items")

    assert job.status_code == 200
    assert job.json()["id"] == created["id"]
    assert items.status_code == 200
    assert len(items.json()) == 1
    assert items.json()[0]["image_id"] == image["id"]
    assert items.json()[0]["status"] == "pending"


def test_missing_job_inspection_returns_404(image_api: ImageApiContext) -> None:
    job_id = uuid4()

    assert image_api.client.get(f"/jobs/{job_id}").status_code == 404
    assert image_api.client.get(f"/jobs/{job_id}/items").status_code == 404
