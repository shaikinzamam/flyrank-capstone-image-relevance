from io import BytesIO
from math import nan
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy import func, select

from app.models.embedding import ImageEmbedding, PostEmbedding
from app.models.image_metadata import AiCallLog, ImageMetadata
from app.models.post import Post
from app.providers.embedding import EmbeddingProviderError
from app.services.semantic_text import build_image_semantic_text
from tests.conftest import ImageApiContext


def upload_and_analyze(context: ImageApiContext, *, confidence: float = 0.96) -> dict:
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color="red").save(buffer, format="PNG")
    uploaded = context.client.post(
        "/images", files={"file": (f"fox-{uuid4()}.png", buffer.getvalue(), "image/png")}
    )
    assert uploaded.status_code == 201
    context.vision_provider.output = {
        **context.vision_provider.output,
        "confidence": confidence,
    }
    analyzed = context.client.post(f"/images/{uploaded.json()['id']}/analyze")
    assert analyzed.status_code == 200
    return uploaded.json()


def create_post(context: ImageApiContext) -> dict:
    response = context.client.post(
        "/posts",
        json={
            "title": "Winter foxes",
            "body": "A red fox crosses a snowy forest.",
            "expected_subject": "red fox",
            "expected_category": "animal",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_image_semantic_text_is_deterministic(image_api: ImageApiContext) -> None:
    image = upload_and_analyze(image_api)
    with image_api.session_factory() as session:
        metadata = session.scalar(
            select(ImageMetadata).where(ImageMetadata.image_id == UUID(image["id"]))
        )
        assert metadata is not None
        first = build_image_semantic_text(metadata)
        second = build_image_semantic_text(metadata)
    assert first == second
    assert first == (
        "Subject: red fox.\nCategory: animal.\n"
        "Caption: A red fox standing in a snowy forest.\n"
        "Tags: red fox, snow, forest, wildlife.\n"
        "Attributes: orange fur, winter.\nObjects: fox, trees, snow."
    )


def test_valid_image_embedding_is_persisted_and_reused(
    image_api: ImageApiContext,
) -> None:
    image = upload_and_analyze(image_api)
    first = image_api.client.post(f"/images/{image['id']}/embedding")
    second = image_api.client.post(f"/images/{image['id']}/embedding")

    assert first.status_code == second.status_code == 200
    assert first.json()["dimensions"] == 384
    assert second.json()["reused"] is True
    assert second.json()["id"] == first.json()["id"]
    assert image_api.embedding_provider.call_count == 1
    with image_api.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ImageEmbedding)) == 1


def test_post_create_list_get_and_embedding_persistence(
    image_api: ImageApiContext,
) -> None:
    post = create_post(image_api)
    assert image_api.client.get(f"/posts/{post['id']}").json()["title"] == "Winter foxes"
    assert any(item["id"] == post["id"] for item in image_api.client.get("/posts").json())

    embedded = image_api.client.post(f"/posts/{post['id']}/embedding")

    assert embedded.status_code == 200
    assert embedded.json()["resource_type"] == "post"
    with image_api.session_factory() as session:
        value = session.scalar(
            select(PostEmbedding).where(PostEmbedding.post_id == UUID(post["id"]))
        )
        assert value is not None
        assert len(value.vector) == 384


def test_changed_post_content_regenerates_same_model_embedding(
    image_api: ImageApiContext,
) -> None:
    post = create_post(image_api)
    first = image_api.client.post(f"/posts/{post['id']}/embedding").json()
    with image_api.session_factory() as session:
        stored = session.get(Post, UUID(post["id"]))
        assert stored is not None
        stored.body = "The fox now runs across open snow."
        session.commit()

    second = image_api.client.post(f"/posts/{post['id']}/embedding").json()

    assert second["reused"] is False
    assert second["id"] == first["id"]
    assert second["source_text_hash"] != first["source_text_hash"]
    assert image_api.embedding_provider.call_count == 2


def test_model_version_change_creates_compatible_new_embedding(
    image_api: ImageApiContext,
) -> None:
    post = create_post(image_api)
    first = image_api.client.post(f"/posts/{post['id']}/embedding").json()
    image_api.embedding_provider._version = "2"

    second = image_api.client.post(f"/posts/{post['id']}/embedding").json()

    assert second["id"] != first["id"]
    assert second["embedding_version"] == "2"
    with image_api.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PostEmbedding)) == 2


def test_invalid_dimension_and_non_finite_vectors_are_rejected(
    image_api: ImageApiContext,
) -> None:
    first_post = create_post(image_api)
    image_api.embedding_provider.output = [0.1] * 383
    invalid_dimension = image_api.client.post(
        f"/posts/{first_post['id']}/embedding"
    )
    second_post = create_post(image_api)
    image_api.embedding_provider.output = [0.1] * 383 + [nan]
    non_finite = image_api.client.post(f"/posts/{second_post['id']}/embedding")

    assert invalid_dimension.status_code == 502
    assert non_finite.status_code == 502
    with image_api.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PostEmbedding)) == 0
        failed_logs = list(
            session.scalars(
                select(AiCallLog).where(AiCallLog.operation == "embedding_generate")
            )
        )
        assert len(failed_logs) == 2
        assert all(log.error_code == "invalid_vector" for log in failed_logs)


def test_missing_metadata_is_clean_and_low_confidence_remains_flagged(
    image_api: ImageApiContext,
) -> None:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color="blue").save(buffer, format="PNG")
    uploaded = image_api.client.post(
        "/images", files={"file": ("missing.png", buffer.getvalue(), "image/png")}
    ).json()
    missing = image_api.client.post(f"/images/{uploaded['id']}/embedding")
    low = upload_and_analyze(image_api, confidence=0.69)
    embedded = image_api.client.post(f"/images/{low['id']}/embedding")

    assert missing.status_code == 409
    assert missing.json() == {"detail": "Image metadata is missing"}
    assert embedded.status_code == 200
    assert embedded.json()["is_low_confidence"] is True


def test_embedding_call_is_zero_cost_and_provider_failure_persists_no_vector(
    image_api: ImageApiContext,
) -> None:
    successful_post = create_post(image_api)
    assert image_api.client.post(f"/posts/{successful_post['id']}/embedding").status_code == 200
    failing_post = create_post(image_api)
    image_api.embedding_provider.output = EmbeddingProviderError("boom")
    failed = image_api.client.post(f"/posts/{failing_post['id']}/embedding")

    assert failed.status_code == 503
    with image_api.session_factory() as session:
        logs = list(
            session.scalars(
                select(AiCallLog)
                .where(AiCallLog.operation == "embedding_generate")
                .order_by(AiCallLog.created_at)
            )
        )
        assert len(logs) == 2
        assert all(log.estimated_cost_usd == 0.0 for log in logs)
        assert logs[0].status == "succeeded"
        assert logs[1].status == "failed"
        assert session.scalar(select(func.count()).select_from(PostEmbedding)) == 1


def test_missing_post_returns_404(image_api: ImageApiContext) -> None:
    post_id = uuid4()
    response = image_api.client.post(f"/posts/{post_id}/embedding")
    detail = image_api.client.get(f"/posts/{post_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Post not found"}
    assert detail.status_code == 404
    assert detail.json() == {"detail": "Post not found"}
