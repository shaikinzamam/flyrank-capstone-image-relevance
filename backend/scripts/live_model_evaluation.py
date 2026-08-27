"""Run a small, honest live-provider evaluation separate from acceptance fixtures."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.image_metadata import AiCallLog
from app.models.recommendation import Recommendation
from app.models.workspace import Workspace
from app.providers.corpus import load_corpus_records
from app.providers.embedding import SentenceTransformerEmbeddingProvider
from app.providers.vision import GeminiVisionProvider
from app.repositories.auth import AuthRepository
from app.repositories.embeddings import EmbeddingRepository
from app.repositories.image_assets import ImageAssetRepository
from app.repositories.image_metadata import ImageMetadataRepository
from app.repositories.image_retrieval import ImageRetrievalRepository
from app.repositories.posts import PostRepository
from app.repositories.recommendations import RecommendationRepository
from app.schemas.post import CreatePostRequest
from app.services.embeddings import EmbeddingService
from app.services.image_analysis import ImageAnalysisService
from app.services.image_assets import ImageAssetService
from app.services.image_retrieval import ImageRetrievalService
from app.services.image_storage import LocalImageStorage
from app.services.posts import PostService
from app.services.recommendations import RecommendationService
from scripts.download_corpus import download_corpus
from scripts.seed import _clear_workspace, _upload

WORKSPACE_NAME = "Live Model Evaluation"
SUBJECT_CODES = (
    "red_fox",
    "gray_wolf",
    "domestic_dog",
    "brown_bear",
    "white_tailed_deer",
)
ARTICLES = {
    "red_fox": (
        "How red foxes survive winter",
        "Red foxes hunt and travel through snowy forests during winter.",
        "red fox",
    ),
    "gray_wolf": (
        "Gray wolf behavior in the wild",
        "Gray wolves live and hunt in social packs across forest habitats.",
        "gray wolf",
    ),
    "domestic_dog": (
        "Understanding domestic dogs",
        "Domestic dogs are companion animals with diverse breeds and behavior.",
        "domestic dog",
    ),
    "brown_bear": (
        "Brown bears in their habitat",
        "Brown bears forage across forests and prepare for winter hibernation.",
        "brown bear",
    ),
    "white_tailed_deer": (
        "White-tailed deer ecology",
        "White-tailed deer browse vegetation along woodland edges.",
        "white-tailed deer",
    ),
}


def _workspace(storage: LocalImageStorage) -> Workspace:
    with SessionLocal() as session:
        repository = AuthRepository(session)
        workspace = repository.get_workspace_by_name(WORKSPACE_NAME)
        if workspace is None:
            workspace = Workspace(name=WORKSPACE_NAME)
            repository.add(workspace)
            repository.commit()
            repository.refresh(workspace)
        session.expunge(workspace)
    _clear_workspace(workspace.id, storage)
    return workspace


def _selected_records(
    records: list[dict[str, object]], per_subject: int
) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for subject_code in SUBJECT_CODES:
        matches = sorted(
            (
                record
                for record in records
                if record.get("subject_code") == subject_code
            ),
            key=lambda record: str(record["image_id"]),
        )
        if len(matches) < per_subject:
            raise RuntimeError(
                f"Corpus has fewer than {per_subject} records for {subject_code}"
            )
        selected.extend(matches[:per_subject])
    return selected


def _call_record(image_id) -> AiCallLog | None:
    with SessionLocal() as session:
        call = session.scalar(
            select(AiCallLog)
            .where(
                AiCallLog.image_id == image_id,
                AiCallLog.operation == "vision_analyze",
            )
            .order_by(AiCallLog.created_at.desc(), AiCallLog.id.desc())
        )
        if call is not None:
            session.expunge(call)
        return call


async def run_live_evaluation(*, per_subject: int) -> dict[str, Any]:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is required for live-model evaluation and must remain server-side"
        )
    if settings.vision_estimated_cost_per_call_usd is None:
        raise RuntimeError(
            "VISION_ESTIMATED_COST_PER_CALL_USD is required for honest live accounting"
        )

    manifest = load_corpus_records(settings.corpus_manifest_path)
    corpus_dir = settings.corpus_manifest_path.parent / "corpus"
    await download_corpus(settings.corpus_manifest_path, corpus_dir)
    records = _selected_records(manifest, per_subject)
    storage = LocalImageStorage(
        settings.image_storage_root,
        max_upload_bytes=settings.max_upload_bytes,
        max_image_pixels=settings.max_image_pixels,
    )
    workspace = _workspace(storage)
    vision = GeminiVisionProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_vision_model,
        timeout_seconds=settings.vision_timeout_seconds,
        estimated_cost_usd=settings.vision_estimated_cost_per_call_usd,
    )
    embedding = SentenceTransformerEmbeddingProvider(
        model=settings.embedding_model,
        version=settings.embedding_version,
        dimensions=settings.embedding_dimensions,
        normalize=settings.embedding_normalize,
    )

    assets: dict[str, Any] = {}
    with SessionLocal() as session:
        service = ImageAssetService(
            ImageAssetRepository(session, workspace.id), storage
        )
        for record in records:
            assets[str(record["image_id"])] = await _upload(
                service, corpus_dir / str(record["local_filename"])
            )

    image_results: list[dict[str, Any]] = []
    image_identity: dict[str, dict[str, object]] = {}
    for record in records:
        fixture_id = str(record["image_id"])
        asset = assets[fixture_id]
        result: dict[str, Any] = {
            "image_id": fixture_id,
            "asset_id": str(asset.id),
            "expected_subject": record["subject"],
            "expected_subject_code": record["subject_code"],
            "schema_valid": False,
            "classification_correct": False,
            "embedding_generated": False,
        }
        with SessionLocal() as session:
            metadata_repository = ImageMetadataRepository(session, workspace.id)
            analysis = ImageAnalysisService(
                ImageAssetRepository(session, workspace.id),
                metadata_repository,
                storage,
                vision,
                low_confidence_threshold=settings.vision_low_confidence_threshold,
                vision_budget_usd=settings.vision_budget_usd,
            )
            try:
                metadata, _ = analysis.analyze(asset.id, reprocess=True)
                result.update(
                    {
                        "schema_valid": True,
                        "gemini_subject": metadata.subject,
                        "gemini_subject_code": metadata.subject_code,
                        "category": metadata.category,
                        "caption": metadata.caption,
                        "tags": list(metadata.tags),
                        "confidence": metadata.confidence,
                        "classification_correct": (
                            metadata.subject_code == record["subject_code"]
                        ),
                    }
                )
                image_identity[str(asset.id)] = {
                    "fixture_image_id": fixture_id,
                    "subject": metadata.subject,
                    "subject_code": metadata.subject_code,
                }
                embeddings = EmbeddingService(
                    EmbeddingRepository(session, workspace.id),
                    ImageAssetRepository(session, workspace.id),
                    metadata_repository,
                    PostRepository(session, workspace.id),
                    embedding,
                )
                embeddings.embed_image(asset.id)
                result["embedding_generated"] = True
            except Exception as exc:  # preserve measured provider/schema failures
                result["error_type"] = type(exc).__name__
                result["error"] = str(exc)

        call = _call_record(asset.id)
        result.update(
            {
                "provider": call.provider if call else vision.provider_name,
                "model": call.model if call else vision.model_name,
                "call_status": call.status if call else "missing",
                "latency_ms": call.latency_ms if call else None,
                "estimated_cost_usd": (
                    call.estimated_cost_usd if call else None
                ),
            }
        )
        image_results.append(result)

    scenario_results: list[dict[str, Any]] = []
    with SessionLocal() as session:
        posts = PostRepository(session, workspace.id)
        embeddings = EmbeddingService(
            EmbeddingRepository(session, workspace.id),
            ImageAssetRepository(session, workspace.id),
            ImageMetadataRepository(session, workspace.id),
            posts,
            embedding,
        )
        retrieval = ImageRetrievalService(
            posts,
            ImageRetrievalRepository(session, workspace.id),
            embedding_model=embedding.model_name,
            embedding_version=embedding.model_version,
            dimensions=embedding.dimensions,
        )
        recommendations = RecommendationService(
            posts,
            retrieval,
            RecommendationRepository(session, workspace.id),
        )
        available = len(image_identity)
        for subject_code, (title, body, expected_subject) in ARTICLES.items():
            scenario: dict[str, Any] = {
                "scenario": subject_code,
                "expected_subject": expected_subject,
                "raw_top_k": [],
                "guard_decisions": [],
            }
            try:
                post = PostService(posts).create(
                    CreatePostRequest(
                        title=title,
                        body=body,
                        expected_subject=expected_subject,
                        expected_category="animal",
                        required_tags=[],
                    )
                )
                embeddings.embed_post(post.id)
                top_k = min(5, available)
                raw = retrieval.retrieve(post.id, top_k=top_k)
                scenario["raw_top_k"] = [
                    {
                        "rank": candidate.rank,
                        "fixture_image_id": image_identity[str(candidate.image_id)][
                            "fixture_image_id"
                        ],
                        "subject": candidate.subject,
                        "similarity_score": candidate.similarity_score,
                    }
                    for candidate in raw.candidates
                ]
                outcome = recommendations.create(post.id, top_k=top_k)
                persisted = list(
                    session.scalars(
                        select(Recommendation)
                        .where(Recommendation.run_id == outcome.run_id)
                        .order_by(Recommendation.rank)
                    )
                )
                scenario["guard_decisions"] = [
                    {
                        "rank": decision.rank,
                        "fixture_image_id": image_identity[str(decision.image_id)][
                            "fixture_image_id"
                        ],
                        "subject": decision.candidate_subject,
                        "similarity_score": decision.similarity_score,
                        "decision": decision.guard_decision,
                        "reason_code": decision.guard_reason_code,
                        "explanation": decision.explanation,
                    }
                    for decision in persisted
                ]
                selected = outcome.recommendation
                scenario["selected_fixture_image_id"] = (
                    image_identity[str(selected.image_id)]["fixture_image_id"]
                    if selected
                    else None
                )
                scenario["selected_subject"] = (
                    image_identity[str(selected.image_id)]["subject"]
                    if selected
                    else None
                )
                scenario["no_confident_match"] = selected is None
                scenario["raw_top1_correct"] = bool(
                    raw.candidates
                    and image_identity[str(raw.candidates[0].image_id)][
                        "subject_code"
                    ]
                    == subject_code
                )
                scenario["recommendation_correct"] = bool(
                    selected
                    and image_identity[str(selected.image_id)]["subject_code"]
                    == subject_code
                )
            except Exception as exc:
                scenario["error_type"] = type(exc).__name__
                scenario["error"] = str(exc)
                scenario["no_confident_match"] = True
                scenario["raw_top1_correct"] = False
                scenario["recommendation_correct"] = False
            scenario_results.append(scenario)

    valid = sum(bool(item["schema_valid"]) for item in image_results)
    correct = sum(bool(item["classification_correct"]) for item in image_results)
    scenario_count = len(scenario_results)
    issued = sum(not item["no_confident_match"] for item in scenario_results)
    correct_issued = sum(
        bool(item["recommendation_correct"]) for item in scenario_results
    )
    unsafe = sum(
        not item["no_confident_match"] and not item["recommendation_correct"]
        for item in scenario_results
    )
    with SessionLocal() as session:
        gemini_calls = session.scalar(
            select(func.count(AiCallLog.id)).where(
                AiCallLog.workspace_id == workspace.id,
                AiCallLog.provider == "gemini",
                AiCallLog.operation == "vision_analyze",
            )
        ) or 0
        estimated_cost = float(
            session.scalar(
                select(func.coalesce(func.sum(AiCallLog.estimated_cost_usd), 0.0)).where(
                    AiCallLog.workspace_id == workspace.id,
                    AiCallLog.provider == "gemini",
                    AiCallLog.operation == "vision_analyze",
                )
            )
            or 0.0
        )
        embedding_calls = session.scalar(
            select(func.count(AiCallLog.id)).where(
                AiCallLog.workspace_id == workspace.id,
                AiCallLog.provider == embedding.provider_name,
                AiCallLog.model == embedding.model_name,
                AiCallLog.operation == "embedding_generate",
            )
        ) or 0
        successful_embedding_calls = session.scalar(
            select(func.count(AiCallLog.id)).where(
                AiCallLog.workspace_id == workspace.id,
                AiCallLog.provider == embedding.provider_name,
                AiCallLog.model == embedding.model_name,
                AiCallLog.operation == "embedding_generate",
                AiCallLog.status == "succeeded",
            )
        ) or 0

    return {
        "report_kind": "live-model-evaluation",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace_id": str(workspace.id),
        "vision_provider": vision.provider_name,
        "vision_model": vision.model_name,
        "embedding_provider": embedding.provider_name,
        "embedding_model": embedding.model_name,
        "embedding_version": embedding.model_version,
        "matching_config": "phase8-v1",
        "images": image_results,
        "scenarios": scenario_results,
        "metrics": {
            "images_evaluated": len(image_results),
            "schema_valid_images": valid,
            "schema_validation_success_rate": valid / len(image_results),
            "vision_classification_correct": correct,
            "vision_classification_accuracy": correct / len(image_results),
            "raw_retrieval_top1_correct": sum(
                bool(item["raw_top1_correct"]) for item in scenario_results
            ),
            "raw_retrieval_top1_accuracy": sum(
                bool(item["raw_top1_correct"]) for item in scenario_results
            )
            / scenario_count,
            "recommendation_coverage": issued / scenario_count,
            "abstention_rate": (scenario_count - issued) / scenario_count,
            "issued_recommendation_precision": (
                correct_issued / issued if issued else 0.0
            ),
            "unsafe_acceptance_count": unsafe,
            "gemini_call_count": gemini_calls,
            "gemini_estimated_cost_usd": estimated_cost,
            "embedding_call_count": embedding_calls,
            "successful_embedding_call_count": successful_embedding_calls,
        },
        "limitations": (
            "This small representative live subset does not establish universal "
            "model accuracy and is separate from the deterministic official evaluation."
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# Live-model evaluation",
        "",
        f"> {report['limitations']}",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Configuration",
        "",
        f"- Vision: `{report['vision_provider']}` / `{report['vision_model']}`",
        f"- Embeddings: `{report['embedding_provider']}` / `{report['embedding_model']}` at `{report['embedding_version']}`",
        f"- Guard configuration: `{report['matching_config']}` (unchanged baseline)",
        "",
        "## Measured metrics",
        "",
        f"- Images evaluated: `{metrics['images_evaluated']}`",
        f"- Schema validation: `{metrics['schema_valid_images']}/{metrics['images_evaluated']}` (`{metrics['schema_validation_success_rate']:.4f}`)",
        f"- Vision classification correctness: `{metrics['vision_classification_correct']}/{metrics['images_evaluated']}` (`{metrics['vision_classification_accuracy']:.4f}`)",
        f"- Raw retrieval top-1: `{metrics['raw_retrieval_top1_correct']}/{len(report['scenarios'])}` (`{metrics['raw_retrieval_top1_accuracy']:.4f}`)",
        f"- Recommendation coverage: `{metrics['recommendation_coverage']:.4f}`",
        f"- Abstention rate: `{metrics['abstention_rate']:.4f}`",
        f"- Issued-recommendation precision: `{metrics['issued_recommendation_precision']:.4f}`",
        f"- Unsafe acceptances: `{metrics['unsafe_acceptance_count']}`",
        f"- Gemini calls: `{metrics['gemini_call_count']}`",
        f"- Estimated Gemini cost: `${metrics['gemini_estimated_cost_usd']:.6f}`",
        "- Real embedding calls: "
        f"`{metrics['successful_embedding_call_count']}/"
        f"{metrics['embedding_call_count']}` succeeded",
        "",
        "## Live vision calls",
        "",
        "| Image | Provider / model | Status | Expected | Gemini subject | Category | Confidence | Schema | Correct | Latency ms | Estimated cost |",
        "|---|---|---|---|---|---|---:|---|---|---:|---:|",
    ]
    for image in report["images"]:
        lines.append(
            f"| {image['image_id']} | {image['provider']} / {image['model']} | "
            f"{image['call_status']} | {image['expected_subject']} | "
            f"{image.get('gemini_subject', 'n/a')} | "
            f"{image.get('category', 'n/a')} | "
            f"{image.get('confidence', 'n/a')} | {image['schema_valid']} | "
            f"{image['classification_correct']} | {image['latency_ms']} | "
            f"{image['estimated_cost_usd']} |"
        )
    lines.extend(["", "### Captions, tags, and failures", ""])
    for image in report["images"]:
        if image.get("schema_valid"):
            lines.extend(
                [
                    f"- `{image['image_id']}` caption: {image['caption']}",
                    f"- `{image['image_id']}` tags: {', '.join(image['tags'])}",
                ]
            )
        elif image.get("error"):
            lines.append(
                f"- `{image['image_id']}` failure: "
                f"{image['error_type']}: {image['error']}"
            )
    lines.extend(["", "## Real retrieval and guard results", ""])
    for scenario in report["scenarios"]:
        lines.extend(
            [
                f"### {scenario['expected_subject']}",
                "",
                f"Raw top-k: `{json.dumps(scenario['raw_top_k'], ensure_ascii=False)}`",
                "",
                f"Guard decisions: `{json.dumps(scenario['guard_decisions'], ensure_ascii=False)}`",
                "",
                f"Selected: `{scenario.get('selected_fixture_image_id') or 'NO_CONFIDENT_MATCH'}`; correct: `{scenario['recommendation_correct']}`.",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Gemini + pinned sentence-transformer on real corpus images"
    )
    parser.add_argument("--per-subject", type=int, default=2, choices=(2, 3))
    parser.add_argument(
        "--json-output", type=Path, default=Path("artifacts/live-model-evaluation.json")
    )
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    try:
        report = asyncio.run(run_live_evaluation(per_subject=args.per_subject))
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
