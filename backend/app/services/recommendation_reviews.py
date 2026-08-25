from uuid import UUID

from app.models.recommendation import (
    GuardDecision,
    HumanReviewDecision,
    Recommendation,
    RecommendationReview,
)
from app.repositories.image_assets import ImageAssetRepository
from app.repositories.posts import PostRepository
from app.repositories.recommendations import RecommendationRepository
from app.schemas.image_asset import ImageAssetResponse
from app.schemas.post import PostResponse
from app.schemas.recommendation import (
    RecommendationDetailResponse,
    RecommendationReviewResponse,
)


class RecommendationNotFoundError(Exception):
    pass


class RecommendationReviewNotPermittedError(Exception):
    pass


class RecommendationReviewService:
    def __init__(
        self,
        recommendations: RecommendationRepository,
        posts: PostRepository,
        images: ImageAssetRepository,
    ) -> None:
        self._recommendations = recommendations
        self._posts = posts
        self._images = images

    def get_detail(self, recommendation_id: UUID) -> RecommendationDetailResponse:
        recommendation = self._get(recommendation_id)
        post = self._posts.get(recommendation.post_id)
        image = self._images.get(recommendation.image_id)
        if post is None or image is None:
            raise RecommendationNotFoundError("Recommendation evidence not found")
        current = self._current_review(recommendation)
        return RecommendationDetailResponse(
            id=recommendation.id,
            run_id=recommendation.run_id,
            post=PostResponse.model_validate(post),
            candidate_image=ImageAssetResponse.model_validate(image),
            rank=recommendation.rank,
            similarity_score=recommendation.similarity_score,
            image_subject=recommendation.candidate_subject,
            image_subject_code=recommendation.candidate_subject_code,
            image_category=recommendation.candidate_category,
            image_tags=list(recommendation.candidate_tags),
            expected_subject=recommendation.expected_subject,
            expected_category=recommendation.expected_category,
            required_tags=list(recommendation.required_tags),
            vision_confidence=recommendation.vision_confidence,
            metadata_valid=recommendation.metadata_valid,
            is_low_confidence=recommendation.is_low_confidence,
            guard_decision=GuardDecision(recommendation.guard_decision),
            guard_reason_code=GuardDecision(recommendation.guard_reason_code),
            explanation=recommendation.explanation,
            human_review_permitted=(
                recommendation.guard_decision == GuardDecision.ACCEPTED
            ),
            human_review_state=current.decision if current else "pending",
            current_review=self._review_response(current) if current else None,
            created_at=recommendation.created_at,
        )

    def list_reviews(
        self, recommendation_id: UUID
    ) -> list[RecommendationReviewResponse]:
        recommendation = self._get(recommendation_id)
        return [self._review_response(review) for review in recommendation.reviews]

    def review(
        self,
        recommendation_id: UUID,
        decision: HumanReviewDecision,
        *,
        comment: str | None,
        reviewer_id: UUID | None = None,
    ) -> RecommendationReviewResponse:
        recommendation = self._get(recommendation_id)
        if recommendation.guard_decision != GuardDecision.ACCEPTED:
            raise RecommendationReviewNotPermittedError(
                "Only guard-accepted recommendations can receive a human decision"
            )
        current = self._current_review(recommendation)
        if (
            current is not None
            and current.decision == decision.value
            and current.comment == comment
            and current.reviewer_id == reviewer_id
        ):
            return self._review_response(current)
        review = RecommendationReview(
            recommendation_id=recommendation.id,
            decision=decision.value,
            comment=comment,
            reviewer_id=reviewer_id,
        )
        return self._review_response(
            self._recommendations.add_review(recommendation, review)
        )

    def _get(self, recommendation_id: UUID) -> Recommendation:
        recommendation = self._recommendations.get(recommendation_id)
        if recommendation is None:
            raise RecommendationNotFoundError("Recommendation not found")
        return recommendation

    @staticmethod
    def _current_review(recommendation: Recommendation) -> RecommendationReview | None:
        return recommendation.reviews[-1] if recommendation.reviews else None

    @staticmethod
    def _review_response(review: RecommendationReview) -> RecommendationReviewResponse:
        return RecommendationReviewResponse.model_validate(review)
