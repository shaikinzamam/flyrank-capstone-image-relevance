from math import isfinite
from uuid import UUID

from pydantic import ValidationError

from app.core.matching_config import MatchingConfig
from app.models.recommendation import (
    GuardDecision,
    Recommendation,
    RecommendationRun,
    RecommendationRunStatus,
)
from app.models.post import Post
from app.repositories.image_retrieval import RankedImageRecord
from app.repositories.posts import PostRepository
from app.repositories.recommendations import RecommendationRepository
from app.schemas.image_metadata import VisionMetadata
from app.schemas.recommendation import CandidateDecisionResponse, RecommendationResponse
from app.services.image_retrieval import ImageRetrievalService, InvalidSimilarityError
from app.services.mismatch_guard import GuardInput, MismatchGuard
from app.services.posts import PostNotFoundError


class RecommendationService:
    def __init__(
        self,
        posts: PostRepository,
        retrieval: ImageRetrievalService,
        recommendations: RecommendationRepository,
        guard: MismatchGuard | None = None,
    ) -> None:
        self._posts = posts
        self._retrieval = retrieval
        self._recommendations = recommendations
        self._guard = guard or MismatchGuard(MatchingConfig())

    def create(self, post_id: UUID, *, top_k: int) -> RecommendationResponse:
        post = self._posts.get(post_id)
        if post is None:
            raise PostNotFoundError("Post not found")
        records = self._retrieval.rank_records(post_id, top_k=top_k)
        decisions = [
            self._evaluate_record(post, rank, record)
            for rank, record in enumerate(records, start=1)
        ]
        accepted = next(
            (item for item in decisions if item.guard_decision == GuardDecision.ACCEPTED),
            None,
        )
        run_status = (
            RecommendationRunStatus.MATCHED
            if accepted is not None
            else RecommendationRunStatus.NO_CONFIDENT_MATCH
        )
        run = RecommendationRun(
            post_id=post.id,
            matching_config_version=self._guard.config.version,
            embedding_model=self._retrieval.embedding_model,
            embedding_version=self._retrieval.embedding_version,
            status=run_status.value,
        )
        self._recommendations.persist(run, decisions)
        responses = [self._response(item) for item in decisions]
        accepted_response = self._response(accepted) if accepted else None
        return RecommendationResponse(
            run_id=run.id,
            post_id=post.id,
            status=run_status.value,
            matching_config_version=run.matching_config_version,
            embedding_model=run.embedding_model,
            embedding_version=run.embedding_version,
            recommendation=accepted_response,
            reason_code="NO_CONFIDENT_MATCH" if accepted is None else None,
            rejected_candidates=[
                item for item in responses if item.decision != GuardDecision.ACCEPTED
            ],
            created_at=run.created_at,
        )

    def _evaluate_record(
        self, post: Post, rank: int, record: RankedImageRecord
    ) -> Recommendation:
        similarity = 1.0 - record.cosine_distance
        if not isfinite(similarity):
            raise InvalidSimilarityError("Vector search returned a non-finite similarity")
        similarity = min(1.0, max(-1.0, similarity))
        try:
            VisionMetadata.model_validate(
                {
                    "subject": record.subject,
                    "subject_code": record.subject_code,
                    "category": record.category,
                    "caption": record.caption,
                    "tags": record.tags,
                    "attributes": record.attributes,
                    "objects": record.objects,
                    "confidence": record.vision_confidence,
                }
            )
            metadata_valid = True
        except ValidationError:
            metadata_valid = False
        guard_input = GuardInput(
            similarity_score=similarity,
            expected_subject=post.expected_subject,
            expected_category=post.expected_category,
            required_tags=tuple(post.required_tags or []),
            image_subject=record.subject,
            image_subject_code=record.subject_code,
            image_category=record.category,
            image_tags=tuple(record.tags or []),
            vision_confidence=record.vision_confidence,
            is_low_confidence=record.is_low_confidence,
            metadata_status=record.metadata_status,
            metadata_valid=metadata_valid,
        )
        result = self._guard.evaluate(guard_input)
        return Recommendation(
            post_id=post.id,
            image_id=record.image_id,
            rank=rank,
            similarity_score=similarity,
            vision_confidence=record.vision_confidence,
            guard_decision=result.decision.value,
            guard_reason_code=result.decision.value,
            explanation=result.explanation,
            expected_subject=post.expected_subject,
            expected_category=post.expected_category,
            required_tags=list(post.required_tags or []),
            candidate_subject=record.subject,
            candidate_subject_code=record.subject_code,
            candidate_category=record.category,
            candidate_tags=list(record.tags or []),
            metadata_valid=metadata_valid,
            is_low_confidence=record.is_low_confidence,
        )

    @staticmethod
    def _response(item: Recommendation) -> CandidateDecisionResponse:
        return CandidateDecisionResponse(
            recommendation_id=item.id,
            image_id=item.image_id,
            rank=item.rank,
            similarity_score=item.similarity_score,
            vision_confidence=item.vision_confidence,
            decision=GuardDecision(item.guard_decision),
            reason_code=GuardDecision(item.guard_reason_code),
            explanation=item.explanation,
        )
