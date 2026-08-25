from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models.image_metadata import AiCallLog
from app.models.recommendation import Recommendation, RecommendationReview
from tests.api.test_image_retrieval import create_image, create_post
from tests.api.test_recommendations import similarity_vector
from tests.conftest import ImageApiContext


def create_guarded_pair(
    image_api: ImageApiContext,
) -> tuple[dict, Recommendation, Recommendation]:
    post = create_post(image_api)
    create_image(image_api, "gray_wolf", similarity_vector(0.93))
    create_image(image_api, "red_fox", similarity_vector(0.90))
    response = image_api.client.post(
        f"/posts/{post['id']}/recommendations?top_k=2"
    )
    assert response.status_code == 200
    run_id = UUID(response.json()["run_id"])
    with image_api.session_factory() as session:
        recommendations = list(
            session.scalars(
                select(Recommendation)
                .where(Recommendation.run_id == run_id)
                .order_by(Recommendation.rank)
            )
        )
        for recommendation in recommendations:
            session.expunge(recommendation)
    return post, recommendations[1], recommendations[0]


def test_detail_starts_pending_and_exposes_immutable_guard_evidence(
    image_api: ImageApiContext,
) -> None:
    post, accepted, rejected = create_guarded_pair(image_api)

    accepted_response = image_api.client.get(f"/recommendations/{accepted.id}")
    rejected_response = image_api.client.get(f"/recommendations/{rejected.id}")

    assert accepted_response.status_code == 200
    body = accepted_response.json()
    assert body["post"]["id"] == post["id"]
    assert body["candidate_image"]["id"] == str(accepted.image_id)
    assert body["rank"] == 2
    assert body["image_subject"] == "red fox"
    assert body["expected_subject"] == "red fox"
    assert body["guard_decision"] == "ACCEPTED"
    assert body["guard_reason_code"] == "ACCEPTED"
    assert body["human_review_permitted"] is True
    assert body["human_review_state"] == "pending"
    assert body["current_review"] is None
    assert rejected_response.status_code == 200
    assert rejected_response.json()["guard_decision"] == "SUBJECT_MISMATCH"
    assert rejected_response.json()["human_review_permitted"] is False
    assert rejected_response.json()["human_review_state"] == "pending"


def test_approve_is_idempotent_and_persists_comment_without_ai_calls(
    image_api: ImageApiContext,
) -> None:
    _, accepted, _ = create_guarded_pair(image_api)
    evidence = (
        accepted.guard_decision,
        accepted.guard_reason_code,
        accepted.similarity_score,
        accepted.vision_confidence,
        accepted.explanation,
    )
    provider_calls = (
        image_api.embedding_provider.call_count,
        image_api.vision_provider.call_count,
    )
    with image_api.session_factory() as session:
        ai_calls_before = session.scalar(select(func.count()).select_from(AiCallLog))

    first = image_api.client.post(
        f"/recommendations/{accepted.id}/approve",
        json={"comment": "Correct image for this article."},
    )
    repeated = image_api.client.post(
        f"/recommendations/{accepted.id}/approve",
        json={"comment": "Correct image for this article."},
    )
    detail = image_api.client.get(f"/recommendations/{accepted.id}")

    assert first.status_code == repeated.status_code == 200
    assert repeated.json()["id"] == first.json()["id"]
    assert first.json()["comment"] == "Correct image for this article."
    assert first.json()["reviewer_id"] is None
    assert detail.json()["human_review_state"] == "approved"
    assert detail.json()["current_review"]["id"] == first.json()["id"]
    with image_api.session_factory() as session:
        persisted = session.get(Recommendation, accepted.id)
        review_count = session.scalar(
            select(func.count()).select_from(RecommendationReview).where(
                RecommendationReview.recommendation_id == accepted.id
            )
        )
        ai_calls_after = session.scalar(select(func.count()).select_from(AiCallLog))
    assert persisted is not None
    assert (
        persisted.guard_decision,
        persisted.guard_reason_code,
        persisted.similarity_score,
        persisted.vision_confidence,
        persisted.explanation,
    ) == evidence
    assert review_count == 1
    assert ai_calls_after == ai_calls_before
    assert (
        image_api.embedding_provider.call_count,
        image_api.vision_provider.call_count,
    ) == provider_calls


def test_conflicting_review_appends_history_and_latest_decision_wins(
    image_api: ImageApiContext,
) -> None:
    _, accepted, _ = create_guarded_pair(image_api)

    approved = image_api.client.post(f"/recommendations/{accepted.id}/approve")
    rejected = image_api.client.post(
        f"/recommendations/{accepted.id}/reject",
        json={"comment": "Not suitable editorially."},
    )
    history = image_api.client.get(f"/recommendations/{accepted.id}/reviews")
    detail = image_api.client.get(f"/recommendations/{accepted.id}")

    assert approved.status_code == rejected.status_code == 200
    assert [item["decision"] for item in history.json()] == ["approved", "rejected"]
    assert history.json()[0]["id"] == approved.json()["id"]
    assert history.json()[1]["id"] == rejected.json()["id"]
    assert detail.json()["human_review_state"] == "rejected"
    assert detail.json()["current_review"]["comment"] == "Not suitable editorially."


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_guard_rejected_candidate_cannot_be_human_reviewed(
    image_api: ImageApiContext, action: str
) -> None:
    _, _, rejected = create_guarded_pair(image_api)

    response = image_api.client.post(f"/recommendations/{rejected.id}/{action}")

    assert response.status_code == 409
    assert "guard-accepted" in response.json()["detail"]
    with image_api.session_factory() as session:
        count = session.scalar(
            select(func.count()).select_from(RecommendationReview).where(
                RecommendationReview.recommendation_id == rejected.id
            )
        )
    assert count == 0


def test_missing_recommendation_endpoints_return_404(
    image_api: ImageApiContext,
) -> None:
    missing = uuid4()

    assert image_api.client.get(f"/recommendations/{missing}").status_code == 404
    reviews = image_api.client.get(f"/recommendations/{missing}/reviews")
    approval = image_api.client.post(f"/recommendations/{missing}/approve")
    assert reviews.status_code == 404
    assert approval.status_code == 404


def test_no_confident_match_has_no_approvable_candidate(
    image_api: ImageApiContext,
) -> None:
    post = create_post(image_api)
    create_image(image_api, "gray_wolf", similarity_vector(0.93))
    response = image_api.client.post(
        f"/posts/{post['id']}/recommendations?top_k=1"
    )
    assert response.json()["status"] == "no_confident_match"
    assert response.json()["recommendation"] is None
    with image_api.session_factory() as session:
        candidate = session.scalar(
            select(Recommendation).where(
                Recommendation.run_id == UUID(response.json()["run_id"])
            )
        )
        assert candidate is not None
        candidate_id = candidate.id

    approval = image_api.client.post(f"/recommendations/{candidate_id}/approve")

    assert approval.status_code == 409
