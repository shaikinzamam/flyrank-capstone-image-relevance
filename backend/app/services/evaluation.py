from hashlib import sha256
from math import sqrt
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.core.matching_config import MatchingConfig
from app.db.base import Base
from app.models.evaluation import EvaluationRun
from app.models.image_asset import ImageAsset
from app.models.image_metadata import ImageMetadata
from app.models.post import Post
from app.models.recommendation import GuardDecision, Recommendation
from app.models.workspace import Workspace
from app.providers.embedding import FakeEmbeddingProvider
from app.repositories.embeddings import EmbeddingRepository
from app.repositories.evaluations import EvaluationRepository
from app.repositories.image_assets import ImageAssetRepository
from app.repositories.image_metadata import ImageMetadataRepository
from app.repositories.image_retrieval import ImageRetrievalRepository
from app.repositories.posts import PostRepository
from app.repositories.recommendations import RecommendationRepository
from app.schemas.evaluation import (
    CandidateEvaluationResult,
    CategoryEvaluationResult,
    EvaluationExample,
    EvaluationReport,
    EvaluationRunResponse,
    ExampleEvaluationResult,
)
from app.services.embeddings import EmbeddingService
from app.services.image_retrieval import ImageRetrievalService
from app.services.recommendations import RecommendationService

EVALUATION_EMBEDDING_MODEL = "deterministic-evaluation-vectors"
EVALUATION_EMBEDDING_VERSION = "1"
EVALUATOR_VERSION = "phase9-v1"


class EvaluationError(Exception):
    pass


class EvaluationDatasetError(EvaluationError):
    pass


class EvaluationRunNotFoundError(EvaluationError):
    pass


def load_evaluation_dataset(path: Path) -> tuple[str, list[EvaluationExample]]:
    examples: list[EvaluationExample] = []
    seen_ids: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvaluationDatasetError("Evaluation dataset could not be read") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            example = EvaluationExample.model_validate_json(line)
        except (ValidationError, ValueError) as exc:
            raise EvaluationDatasetError(
                f"Invalid evaluation label on line {line_number}: {exc}"
            ) from exc
        if example.example_id in seen_ids:
            raise EvaluationDatasetError(
                f"Duplicate evaluation example_id: {example.example_id}"
            )
        seen_ids.add(example.example_id)
        examples.append(example)
    if not examples:
        raise EvaluationDatasetError("Evaluation dataset is empty")
    versions = {example.dataset_version for example in examples}
    if len(versions) != 1:
        raise EvaluationDatasetError("Evaluation dataset versions must be consistent")
    return versions.pop(), examples


class EvaluationEngine:
    """Runs real application services against per-example isolated SQLite data."""

    def __init__(self, config: MatchingConfig | None = None) -> None:
        self._config = config or MatchingConfig()

    def evaluate(
        self, dataset_version: str, examples: list[EvaluationExample]
    ) -> EvaluationReport:
        results = [self._evaluate_example(example) for example in examples]
        acceptable_by_example = {
            example.example_id: set(example.acceptable_image_ids) for example in examples
        }
        expected_no_match = {
            example.example_id: example.expect_no_confident_match
            for example in examples
        }
        correct_top1 = sum(
            result.selected_image_id in acceptable_by_example[result.example_id]
            for result in results
            if result.selected_image_id is not None
        )
        incorrect_top1 = sum(
            result.selected_image_id not in acceptable_by_example[result.example_id]
            for result in results
            if result.selected_image_id is not None
        )
        correct_no_match = sum(
            expected_no_match[result.example_id]
            and result.selected_image_id is None
            for result in results
        )
        incorrect_refusals = sum(
            not expected_no_match[result.example_id]
            and result.selected_image_id is None
            for result in results
        )
        candidate_results = [
            candidate for result in results for candidate in result.candidates
        ]
        accepted = [
            candidate
            for candidate in candidate_results
            if candidate.decision == GuardDecision.ACCEPTED
        ]
        unsafe = [candidate for candidate in candidate_results if candidate.unsafe]
        unsafe_acceptances = sum(
            candidate.decision == GuardDecision.ACCEPTED for candidate in unsafe
        )
        safe_rejections = sum(
            candidate.decision != GuardDecision.ACCEPTED for candidate in unsafe
        )
        issued_recommendations = correct_top1 + incorrect_top1
        top1_precision = correct_top1 / len(examples) if examples else 0.0
        issued_recommendation_precision = (
            correct_top1 / issued_recommendations if issued_recommendations else 0.0
        )
        safe_acceptance_precision = (
            sum(candidate.acceptable for candidate in accepted) / len(accepted)
            if accepted
            else 0.0
        )
        unsafe_rejection_recall = safe_rejections / len(unsafe) if unsafe else 0.0
        per_category: dict[str, CategoryEvaluationResult] = {}
        for example, result in zip(examples, results, strict=True):
            category = example.expected_category or "unspecified"
            current = per_category.get(
                category, CategoryEvaluationResult(examples=0, correct_outcomes=0)
            )
            per_category[category] = CategoryEvaluationResult(
                examples=current.examples + 1,
                correct_outcomes=current.correct_outcomes + int(result.correct),
            )
        return EvaluationReport(
            evaluator_version=EVALUATOR_VERSION,
            dataset_version=dataset_version,
            config_version=self._config.version,
            embedding_model=EVALUATION_EMBEDDING_MODEL,
            embedding_version=EVALUATION_EMBEDDING_VERSION,
            minimum_similarity=self._config.minimum_similarity,
            minimum_vision_confidence=self._config.minimum_vision_confidence,
            total_examples=len(examples),
            eligible_recommendation_examples=sum(
                not example.expect_no_confident_match for example in examples
            ),
            correct_top1=correct_top1,
            incorrect_top1=incorrect_top1,
            correct_no_confident_match=correct_no_match,
            incorrect_refusals=incorrect_refusals,
            unsafe_acceptance_count=unsafe_acceptances,
            correct_safe_rejections=safe_rejections,
            top1_precision=top1_precision,
            issued_recommendation_precision=issued_recommendation_precision,
            safe_acceptance_precision=safe_acceptance_precision,
            unsafe_rejection_recall=unsafe_rejection_recall,
            per_category=per_category,
            examples=results,
        )

    def _evaluate_example(self, example: EvaluationExample) -> ExampleEvaluationResult:
        engine = create_engine("sqlite+pysqlite://")
        Base.metadata.create_all(engine)
        try:
            with Session(engine, expire_on_commit=False) as session:
                result = self._run_pipeline(session, example)
        finally:
            engine.dispose()
        return result

    def _run_pipeline(
        self, session: Session, example: EvaluationExample
    ) -> ExampleEvaluationResult:
        workspace = Workspace(name=f"Evaluation {example.example_id}")
        session.add(workspace)
        session.commit()
        posts = PostRepository(session, workspace.id)
        post = Post(
            title=example.article_title,
            body=example.article_body,
            expected_subject=example.expected_subject,
            expected_category=example.expected_category,
            required_tags=list(example.required_tags),
        )
        posts.add(post)
        posts.commit()
        provider = FakeEmbeddingProvider(
            model=EVALUATION_EMBEDDING_MODEL,
            version=EVALUATION_EMBEDDING_VERSION,
        )
        embeddings = EmbeddingService(
            EmbeddingRepository(session, workspace.id),
            ImageAssetRepository(session, workspace.id),
            ImageMetadataRepository(session, workspace.id),
            posts,
            provider,
        )
        provider.output = self._vector(1.0)
        embeddings.embed_post(post.id)
        fixture_by_uuid: dict[UUID, str] = {}
        for candidate in example.candidates:
            image_id = uuid5(
                NAMESPACE_URL, f"evaluation/{example.example_id}/{candidate.fixture_image_id}"
            )
            fixture_by_uuid[image_id] = candidate.fixture_image_id
            digest = sha256(
                f"{example.example_id}/{candidate.fixture_image_id}".encode()
            ).hexdigest()
            session.add(
                ImageAsset(
                    workspace_id=workspace.id,
                    id=image_id,
                    filename=f"{candidate.fixture_image_id}.png",
                    storage_key=f"evaluation/{digest}.png",
                    mime_type="image/png",
                    byte_size=1,
                    sha256=digest,
                    processing_status="processed",
                )
            )
            session.add(
                ImageMetadata(
                    image_id=image_id,
                    subject=candidate.subject,
                    subject_code=candidate.subject_code,
                    category=candidate.category,
                    caption=f"Evaluation fixture: {candidate.subject}",
                    tags=list(candidate.tags),
                    attributes=[],
                    objects=[candidate.subject],
                    confidence=candidate.vision_confidence,
                    is_low_confidence=candidate.is_low_confidence,
                    metadata_status=candidate.metadata_status,
                    vision_provider="deterministic-evaluation",
                    vision_model="labeled-fixture-v1",
                    schema_version="1.0",
                )
            )
            session.commit()
            provider.output = self._vector(candidate.similarity_score)
            embeddings.embed_image(image_id)
        retrieval = ImageRetrievalService(
            posts,
            ImageRetrievalRepository(session, workspace.id),
            embedding_model=provider.model_name,
            embedding_version=provider.model_version,
            dimensions=provider.dimensions,
        )
        response = RecommendationService(
            posts,
            retrieval,
            RecommendationRepository(session, workspace.id),
        ).create(post.id, top_k=len(example.candidates))
        persisted = list(
            session.scalars(
                select(Recommendation)
                .where(Recommendation.run_id == response.run_id)
                .order_by(Recommendation.rank)
            )
        )
        candidates = []
        for decision in persisted:
            fixture_id = fixture_by_uuid[decision.image_id]
            expected_decision = example.expected_guard_decisions[fixture_id]
            actual_decision = GuardDecision(decision.guard_decision)
            candidates.append(
                CandidateEvaluationResult(
                    fixture_image_id=fixture_id,
                    rank=decision.rank,
                    similarity_score=decision.similarity_score,
                    decision=actual_decision,
                    reason_code=GuardDecision(decision.guard_reason_code),
                    explanation=decision.explanation,
                    expected_decision=expected_decision,
                    decision_correct=actual_decision == expected_decision,
                    acceptable=fixture_id in example.acceptable_image_ids,
                    unsafe=fixture_id in example.unsafe_image_ids,
                )
            )
        selected = (
            fixture_by_uuid[response.recommendation.image_id]
            if response.recommendation is not None
            else None
        )
        correct = (
            selected is None
            if example.expect_no_confident_match
            else selected in example.acceptable_image_ids
        )
        return ExampleEvaluationResult(
            example_id=example.example_id,
            expected_result=(
                "NO_CONFIDENT_MATCH"
                if example.expect_no_confident_match
                else "one of: " + ", ".join(example.acceptable_image_ids)
            ),
            actual_result=selected or "NO_CONFIDENT_MATCH",
            selected_image_id=selected,
            correct=correct,
            expected_subject=example.expected_subject,
            expected_category=example.expected_category,
            candidates=candidates,
        )

    @staticmethod
    def _vector(similarity: float) -> list[float]:
        return [similarity, sqrt(max(0.0, 1.0 - similarity**2))] + [0.0] * 382


class EvaluationService:
    def __init__(
        self,
        repository: EvaluationRepository,
        dataset_path: Path,
        engine: EvaluationEngine | None = None,
    ) -> None:
        self._repository = repository
        self._dataset_path = dataset_path
        self._engine = engine or EvaluationEngine()

    def run(self) -> EvaluationRunResponse:
        dataset_version, examples = load_evaluation_dataset(self._dataset_path)
        report = self._engine.evaluate(dataset_version, examples)
        run = self._repository.add(
            EvaluationRun(
                dataset_version=report.dataset_version,
                config_version=report.config_version,
                embedding_model=report.embedding_model,
                embedding_version=report.embedding_version,
                total_examples=report.total_examples,
                eligible_recommendation_examples=(
                    report.eligible_recommendation_examples
                ),
                correct_top1=report.correct_top1,
                incorrect_top1=report.incorrect_top1,
                correct_no_match=report.correct_no_confident_match,
                incorrect_refusals=report.incorrect_refusals,
                safe_rejections=report.correct_safe_rejections,
                unsafe_acceptances=report.unsafe_acceptance_count,
                top1_precision=report.top1_precision,
                issued_recommendation_precision=(
                    report.issued_recommendation_precision
                ),
                report_json=report.model_dump(mode="json"),
            )
        )
        return self._response(run)

    def latest(self) -> EvaluationRunResponse:
        run = self._repository.latest()
        if run is None:
            raise EvaluationRunNotFoundError("No evaluation run exists")
        return self._response(run)

    def get(self, run_id: UUID) -> EvaluationRunResponse:
        run = self._repository.get(run_id)
        if run is None:
            raise EvaluationRunNotFoundError("Evaluation run not found")
        return self._response(run)

    @staticmethod
    def _response(run: EvaluationRun) -> EvaluationRunResponse:
        payload = dict(run.report_json)
        if "issued_recommendation_precision" not in payload:
            payload["issued_recommendation_precision"] = payload["top1_precision"]
            payload["top1_precision"] = (
                payload["correct_top1"] / payload["total_examples"]
            )
        report = EvaluationReport.model_validate(payload)
        return EvaluationRunResponse(
            **report.model_dump(), run_id=run.id, created_at=run.created_at
        )
