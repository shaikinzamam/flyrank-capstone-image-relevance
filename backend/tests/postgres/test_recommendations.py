import os
from math import sqrt
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.models.embedding import ImageEmbedding, PostEmbedding
from app.models.image_asset import ImageAsset
from app.models.image_metadata import ImageMetadata
from app.models.post import Post
from app.models.recommendation import (
    HumanReviewDecision,
    Recommendation,
    RecommendationReview,
    RecommendationRun,
)
from app.repositories.image_assets import ImageAssetRepository
from app.repositories.image_retrieval import ImageRetrievalRepository
from app.repositories.posts import PostRepository
from app.repositories.recommendations import RecommendationRepository
from app.services.image_retrieval import ImageRetrievalService
from app.services.recommendations import RecommendationService
from app.services.recommendation_reviews import RecommendationReviewService

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_POSTGRES_PGVECTOR") != "1",
    reason="requires an explicitly enabled migrated PostgreSQL database",
)


def vector(similarity: float) -> list[float]:
    return [similarity, sqrt(1.0 - similarity**2)] + [0.0] * 382


def test_postgresql_persists_guarded_fox_over_higher_ranked_wolf() -> None:
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    post_id = uuid4()
    wolf_id = uuid4()
    fox_id = uuid4()
    model = f"guard-persistence-{uuid4().hex}"
    version = "1"
    try:
        with Session(engine) as session:
            session.add(
                Post(
                    id=post_id,
                    title="How red foxes survive winter",
                    body="Red fox winter behavior",
                    expected_subject="Vulpes vulpes",
                    expected_category="animal",
                    required_tags=["winter"],
                )
            )
            session.add(
                PostEmbedding(
                    post_id=post_id,
                    vector=vector(1.0),
                    embedding_model=model,
                    embedding_version=version,
                    dimensions=384,
                    source_text_hash="p" * 64,
                )
            )
            for image_id, code, subject, similarity in [
                (wolf_id, "gray_wolf", "gray wolf", 0.93),
                (fox_id, "red_fox", "red fox", 0.90),
            ]:
                token = uuid4().hex
                session.add(
                    ImageAsset(
                        id=image_id,
                        filename=f"{code}.png",
                        storage_key=f"guard/{token}.png",
                        mime_type="image/png",
                        byte_size=1,
                        sha256=token.ljust(64, "0"),
                        processing_status="processed",
                    )
                )
                session.add(
                    ImageMetadata(
                        image_id=image_id,
                        subject=subject,
                        subject_code=code,
                        category="animal",
                        caption=f"A {subject} in winter",
                        tags=[subject, "winter"],
                        attributes=["winter coat"],
                        objects=[subject],
                        confidence=0.95,
                        is_low_confidence=False,
                        metadata_status="trusted",
                        vision_provider="test",
                        vision_model="test",
                        schema_version="1.0",
                    )
                )
                session.add(
                    ImageEmbedding(
                        image_id=image_id,
                        vector=vector(similarity),
                        embedding_model=model,
                        embedding_version=version,
                        dimensions=384,
                        source_text_hash=code[0] * 64,
                    )
                )
            session.commit()

        with Session(engine) as session:
            retrieval = ImageRetrievalService(
                PostRepository(session),
                ImageRetrievalRepository(session),
                embedding_model=model,
                embedding_version=version,
                dimensions=384,
            )
            result = RecommendationService(
                PostRepository(session),
                retrieval,
                RecommendationRepository(session),
            ).create(post_id, top_k=2)
            persisted_run = session.get(RecommendationRun, result.run_id)
            persisted = list(
                session.scalars(
                    select(Recommendation)
                    .where(Recommendation.run_id == result.run_id)
                    .order_by(Recommendation.rank)
                )
            )
            original_evidence = (
                persisted[1].guard_decision,
                persisted[1].similarity_score,
                persisted[1].vision_confidence,
                persisted[1].guard_reason_code,
                persisted[1].explanation,
            )
            persisted_run_status = persisted_run.status if persisted_run else None
            persisted_decisions = [item.guard_decision for item in persisted]
            persisted_similarities = [item.similarity_score for item in persisted]
            reviewed_recommendation_id = persisted[1].id
            review = RecommendationReviewService(
                RecommendationRepository(session),
                PostRepository(session),
                ImageAssetRepository(session),
            ).review(
                reviewed_recommendation_id,
                HumanReviewDecision.APPROVED,
                comment="PostgreSQL persistence probe",
            )

        with Session(engine) as session:
            persisted_review = session.get(RecommendationReview, review.id)
            reviewed_recommendation = session.get(
                Recommendation, reviewed_recommendation_id
            )

        assert result.status == "matched"
        assert result.recommendation is not None
        assert result.recommendation.image_id == fox_id
        assert persisted_run_status == "matched"
        assert persisted_decisions == [
            "SUBJECT_MISMATCH",
            "ACCEPTED",
        ]
        assert persisted_similarities[0] == pytest.approx(0.93, abs=1e-6)
        assert persisted_similarities[1] == pytest.approx(0.90, abs=1e-6)
        assert persisted_review is not None
        assert persisted_review.decision == "approved"
        assert persisted_review.comment == "PostgreSQL persistence probe"
        assert reviewed_recommendation is not None
        assert (
            reviewed_recommendation.guard_decision,
            reviewed_recommendation.similarity_score,
            reviewed_recommendation.vision_confidence,
            reviewed_recommendation.guard_reason_code,
            reviewed_recommendation.explanation,
        ) == original_evidence
    finally:
        with Session(engine) as session:
            session.execute(delete(Post).where(Post.id == post_id))
            session.execute(delete(ImageAsset).where(ImageAsset.id.in_([wolf_id, fox_id])))
            session.commit()
        engine.dispose()
