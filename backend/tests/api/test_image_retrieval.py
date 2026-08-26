from io import BytesIO
from math import sqrt
from uuid import UUID, uuid4

from PIL import Image
import pytest
from sqlalchemy import func, select

from app.models.image_metadata import AiCallLog, ImageMetadata
from tests.conftest import ImageApiContext


SUBJECTS = {
    "red_fox": ("red fox", "fox", (230, 90, 20)),
    "gray_wolf": ("gray wolf", "wolf", (100, 100, 100)),
    "domestic_dog": ("domestic dog", "dog", (120, 80, 30)),
}


def test_oversized_post_body_is_rejected(image_api: ImageApiContext) -> None:
    response = image_api.client.post(
        "/posts",
        json={"title": "Bounded post", "body": "x" * 50_001},
    )

    assert response.status_code == 422
    assert "traceback" not in response.text.lower()


def vector(first: float, second: float = 0.0) -> list[float]:
    return [first, second] + [0.0] * 382


def create_post(
    context: ImageApiContext, *, embed: bool = True, post_vector: list[float] | None = None
) -> dict:
    response = context.client.post(
        "/posts",
        json={
            "title": "How Vulpes vulpes survives winter",
            "body": "Red foxes stay active in snowy forests.",
            "expected_subject": "red fox",
            "expected_category": "animal",
        },
    )
    assert response.status_code == 201
    post = response.json()
    if embed:
        context.embedding_provider.output = post_vector or vector(1.0)
        embedded = context.client.post(f"/posts/{post['id']}/embedding/debug-sync")
        assert embedded.status_code == 200
    return post


def create_image(
    context: ImageApiContext,
    subject_code: str,
    embedding_vector: list[float],
    *,
    confidence: float = 0.95,
) -> dict:
    subject, object_name, color = SUBJECTS[subject_code]
    buffer = BytesIO()
    Image.new("RGB", (16 + len(subject), 16), color=color).save(buffer, format="PNG")
    uploaded = context.client.post(
        "/images",
        files={
            "file": (
                f"{subject_code}-{uuid4()}.png",
                buffer.getvalue(),
                "image/png",
            )
        },
    )
    assert uploaded.status_code == 201
    context.vision_provider.output = {
        "subject": subject,
        "subject_code": subject_code,
        "category": "animal",
        "caption": f"A {subject} in a winter landscape",
        "tags": [subject, "winter", "wildlife"],
        "attributes": ["winter coat"],
        "objects": [object_name, "snow"],
        "confidence": confidence,
    }
    analyzed = context.client.post(f"/images/{uploaded.json()['id']}/analyze")
    assert analyzed.status_code == 200
    context.embedding_provider.output = embedding_vector
    embedded = context.client.post(
        f"/images/{uploaded.json()['id']}/embedding/debug-sync"
    )
    assert embedded.status_code == 200
    return uploaded.json()


def test_candidates_are_ranked_by_descending_cosine_similarity_with_metadata(
    image_api: ImageApiContext,
) -> None:
    post = create_post(image_api)
    fox = create_image(image_api, "red_fox", vector(0.95, 0.05))
    wolf = create_image(
        image_api, "gray_wolf", vector(0.8, 0.6), confidence=0.69
    )
    dog = create_image(image_api, "domestic_dog", vector(0.1, 0.9))
    calls_before = image_api.embedding_provider.call_count

    response = image_api.client.get(
        f"/posts/{post['id']}/image-candidates?top_k=3"
    )

    assert response.status_code == 200
    body = response.json()
    candidates = body["candidates"]
    assert [item["image_id"] for item in candidates] == [
        fox["id"],
        wolf["id"],
        dog["id"],
    ]
    assert [item["rank"] for item in candidates] == [1, 2, 3]
    assert [item["similarity_score"] for item in candidates] == pytest.approx(
        [
            0.95 / sqrt(0.95**2 + 0.05**2),
            0.8,
            0.1 / sqrt(0.1**2 + 0.9**2),
        ]
    )
    assert candidates[0]["subject"] == "red fox"
    assert candidates[0]["category"] == "animal"
    assert candidates[0]["caption"] == "A red fox in a winter landscape"
    assert candidates[0]["tags"] == ["red fox", "winter", "wildlife"]
    assert candidates[0]["vision_confidence"] == 0.95
    assert candidates[1]["subject"] == "gray wolf"
    assert candidates[1]["is_low_confidence"] is True
    assert image_api.embedding_provider.call_count == calls_before


def test_top_k_limits_candidates_and_invalid_values_are_rejected(
    image_api: ImageApiContext,
) -> None:
    post = create_post(image_api)
    create_image(image_api, "red_fox", vector(1.0))
    create_image(image_api, "gray_wolf", vector(0.8, 0.6))

    limited = image_api.client.get(
        f"/posts/{post['id']}/image-candidates?top_k=1"
    )
    too_small = image_api.client.get(
        f"/posts/{post['id']}/image-candidates?top_k=0"
    )
    too_large = image_api.client.get(
        f"/posts/{post['id']}/image-candidates?top_k=21"
    )

    assert limited.status_code == 200
    assert len(limited.json()["candidates"]) == 1
    assert too_small.status_code == 422
    assert too_large.status_code == 422


def test_missing_post_missing_embedding_and_empty_library_are_clean(
    image_api: ImageApiContext,
) -> None:
    missing = image_api.client.get(f"/posts/{uuid4()}/image-candidates")
    unembedded = create_post(image_api, embed=False)
    no_embedding = image_api.client.get(
        f"/posts/{unembedded['id']}/image-candidates"
    )
    embedded = create_post(image_api)
    empty = image_api.client.get(f"/posts/{embedded['id']}/image-candidates")

    assert missing.status_code == 404
    assert missing.json() == {"detail": "Post not found"}
    assert no_embedding.status_code == 409
    assert no_embedding.json() == {
        "detail": "Post must be embedded before image retrieval"
    }
    assert empty.status_code == 200
    assert empty.json()["candidates"] == []


@pytest.mark.parametrize("identity_field", ["_model", "_version"])
def test_only_incompatible_image_embeddings_return_conflict(
    image_api: ImageApiContext, identity_field: str
) -> None:
    post = create_post(image_api)
    original = getattr(image_api.embedding_provider, identity_field)
    setattr(image_api.embedding_provider, identity_field, f"other-{original}")
    create_image(image_api, "red_fox", vector(1.0))
    setattr(image_api.embedding_provider, identity_field, original)

    response = image_api.client.get(f"/posts/{post['id']}/image-candidates")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "No image embeddings are compatible with the post embedding"
    }


def test_incompatible_post_embedding_and_wrong_configured_dimensions_are_rejected(
    image_api: ImageApiContext,
) -> None:
    post = create_post(image_api)
    image_api.embedding_provider._version = "different-version"
    incompatible = image_api.client.get(
        f"/posts/{post['id']}/image-candidates"
    )
    image_api.embedding_provider._version = "1"
    image_api.embedding_provider._dimensions = 383
    wrong_dimensions = image_api.client.get(
        f"/posts/{post['id']}/image-candidates"
    )

    assert incompatible.status_code == 409
    assert incompatible.json() == {
        "detail": "Post embedding is incompatible with the configured retrieval model"
    }
    assert wrong_dimensions.status_code == 409
    assert wrong_dimensions.json() == {
        "detail": "Configured retrieval dimensions do not match the vector schema"
    }


def test_ties_use_image_id_and_invalid_metadata_is_excluded(
    image_api: ImageApiContext,
) -> None:
    post = create_post(image_api)
    fox = create_image(image_api, "red_fox", vector(0.8, 0.6))
    wolf = create_image(image_api, "gray_wolf", vector(0.8, 0.6))
    dog = create_image(image_api, "domestic_dog", vector(0.7, 0.3))
    with image_api.session_factory() as session:
        invalid = session.scalar(
            select(ImageMetadata).where(
                ImageMetadata.image_id == UUID(dog["id"])
            )
        )
        assert invalid is not None
        invalid.tags = []
        session.commit()

    response = image_api.client.get(
        f"/posts/{post['id']}/image-candidates?top_k=3"
    )

    assert response.status_code == 200
    candidates = response.json()["candidates"]
    tied_ids = sorted([fox["id"], wolf["id"]])
    assert [item["image_id"] for item in candidates] == tied_ids
    assert [item["rank"] for item in candidates] == [1, 2]


def test_retrieval_creates_no_ai_call_log(image_api: ImageApiContext) -> None:
    post = create_post(image_api)
    create_image(image_api, "red_fox", vector(1.0))
    with image_api.session_factory() as session:
        before = session.scalar(select(func.count()).select_from(AiCallLog))

    assert image_api.client.get(
        f"/posts/{post['id']}/image-candidates"
    ).status_code == 200

    with image_api.session_factory() as session:
        after = session.scalar(select(func.count()).select_from(AiCallLog))
    assert after == before
