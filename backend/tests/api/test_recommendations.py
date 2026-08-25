from math import sqrt
from uuid import UUID

from sqlalchemy import func, select

from app.models.image_metadata import AiCallLog, ImageMetadata
from app.models.recommendation import Recommendation, RecommendationRun
from tests.api.test_image_retrieval import create_image, create_post, vector
from tests.conftest import ImageApiContext


def similarity_vector(similarity: float) -> list[float]:
    return vector(similarity, sqrt(1.0 - similarity**2))


def test_wolf_rank_one_is_rejected_and_fox_rank_two_is_recommended_and_persisted(
    image_api: ImageApiContext,
) -> None:
    post = create_post(image_api)
    wolf = create_image(image_api, "gray_wolf", similarity_vector(0.93))
    fox = create_image(image_api, "red_fox", similarity_vector(0.90))
    calls_before = (
        image_api.embedding_provider.call_count,
        image_api.vision_provider.call_count,
    )
    with image_api.session_factory() as session:
        ai_calls_before = session.scalar(select(func.count()).select_from(AiCallLog))

    raw_before = image_api.client.get(
        f"/posts/{post['id']}/image-candidates?top_k=2"
    )
    response = image_api.client.post(
        f"/posts/{post['id']}/recommendations?top_k=2"
    )
    raw_after = image_api.client.get(
        f"/posts/{post['id']}/image-candidates?top_k=2"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "matched"
    assert body["reason_code"] is None
    assert body["recommendation"]["image_id"] == fox["id"]
    assert body["recommendation"]["rank"] == 2
    assert body["recommendation"]["decision"] == "ACCEPTED"
    assert body["recommendation"]["reason_code"] == "ACCEPTED"
    assert body["rejected_candidates"] == [
        {
            "image_id": wolf["id"],
            "rank": 1,
            "similarity_score": body["rejected_candidates"][0]["similarity_score"],
            "vision_confidence": 0.95,
            "decision": "SUBJECT_MISMATCH",
            "reason_code": "SUBJECT_MISMATCH",
            "explanation": "Expected red fox, but the image was classified as gray wolf.",
        }
    ]
    assert raw_after.json() == raw_before.json()
    assert (
        image_api.embedding_provider.call_count,
        image_api.vision_provider.call_count,
    ) == calls_before

    with image_api.session_factory() as session:
        run = session.get(RecommendationRun, UUID(body["run_id"]))
        persisted = list(
            session.scalars(
                select(Recommendation)
                .where(Recommendation.run_id == UUID(body["run_id"]))
                .order_by(Recommendation.rank)
            )
        )
        ai_calls = session.scalar(select(func.count()).select_from(AiCallLog))
    assert run is not None
    assert run.status == "matched"
    assert run.matching_config_version == "phase8-v1"
    assert [item.guard_decision for item in persisted] == [
        "SUBJECT_MISMATCH",
        "ACCEPTED",
    ]
    assert persisted[0].similarity_score > persisted[1].similarity_score
    assert persisted[0].candidate_subject_code == "gray_wolf"
    assert persisted[1].metadata_valid is True
    assert ai_calls == ai_calls_before


def test_only_wrong_subjects_returns_and_persists_no_confident_match(
    image_api: ImageApiContext,
) -> None:
    post = create_post(image_api)
    create_image(image_api, "gray_wolf", similarity_vector(0.93))
    create_image(image_api, "domestic_dog", similarity_vector(0.80))

    response = image_api.client.post(
        f"/posts/{post['id']}/recommendations?top_k=2"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_confident_match"
    assert body["recommendation"] is None
    assert body["reason_code"] == "NO_CONFIDENT_MATCH"
    assert [item["decision"] for item in body["rejected_candidates"]] == [
        "SUBJECT_MISMATCH",
        "SUBJECT_MISMATCH",
    ]
    with image_api.session_factory() as session:
        run = session.get(RecommendationRun, UUID(body["run_id"]))
        count = session.scalar(
            select(func.count()).select_from(Recommendation).where(
                Recommendation.run_id == UUID(body["run_id"])
            )
        )
    assert run is not None and run.status == "no_confident_match"
    assert count == 2


def test_low_confidence_and_invalid_metadata_are_rejected_in_guard_order(
    image_api: ImageApiContext,
) -> None:
    post = create_post(image_api)
    low = create_image(
        image_api, "red_fox", similarity_vector(0.95), confidence=0.69
    )
    invalid = create_image(image_api, "gray_wolf", similarity_vector(0.90))
    with image_api.session_factory() as session:
        metadata = session.scalar(
            select(ImageMetadata).where(ImageMetadata.image_id == UUID(invalid["id"]))
        )
        assert metadata is not None
        metadata.tags = []
        session.commit()

    response = image_api.client.post(
        f"/posts/{post['id']}/recommendations?top_k=2"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_confident_match"
    assert {
        item["image_id"]: item["decision"] for item in body["rejected_candidates"]
    } == {low["id"]: "LOW_CONFIDENCE", invalid["id"]: "INVALID_METADATA"}


def test_required_tag_is_enforced_by_recommendation_endpoint(
    image_api: ImageApiContext,
) -> None:
    created = image_api.client.post(
        "/posts",
        json={
            "title": "Red fox in winter snow",
            "body": "A fox adapts to snowy weather.",
            "expected_subject": "Vulpes vulpes",
            "expected_category": "animal",
            "required_tags": ["snow"],
        },
    )
    assert created.status_code == 201
    post = created.json()
    image_api.embedding_provider.output = vector(1.0)
    assert image_api.client.post(f"/posts/{post['id']}/embedding").status_code == 200
    fox = create_image(image_api, "red_fox", similarity_vector(0.90))
    with image_api.session_factory() as session:
        metadata = session.scalar(
            select(ImageMetadata).where(ImageMetadata.image_id == UUID(fox["id"]))
        )
        assert metadata is not None
        metadata.tags = ["red fox", "forest", "summer"]
        session.commit()

    response = image_api.client.post(f"/posts/{post['id']}/recommendations")

    assert response.status_code == 200
    assert response.json()["rejected_candidates"][0]["decision"] == (
        "REQUIRED_TAG_MISSING"
    )
    assert "snow" in response.json()["rejected_candidates"][0]["explanation"]
