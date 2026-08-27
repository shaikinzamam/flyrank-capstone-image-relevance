import argparse
import asyncio
import json
import time
from io import BytesIO
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import delete, func, select
from starlette.datastructures import Headers

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.evaluation import EvaluationRun
from app.models.image_asset import ImageAsset
from app.models.image_metadata import AiCallLog, ImageMetadata
from app.models.post import Post
from app.models.processing_job import JobStatus, ProcessingJob
from app.models.recommendation import HumanReviewDecision
from app.models.workspace import Workspace
from app.providers.corpus import CorpusFixtureEmbeddingProvider, load_corpus_records
from app.repositories.auth import AuthRepository
from app.repositories.embeddings import EmbeddingRepository
from app.repositories.evaluations import EvaluationRepository
from app.repositories.image_assets import ImageAssetRepository
from app.repositories.image_metadata import ImageMetadataRepository
from app.repositories.image_retrieval import ImageRetrievalRepository
from app.repositories.posts import PostRepository
from app.repositories.processing_jobs import ProcessingJobRepository
from app.repositories.recommendations import RecommendationRepository
from app.schemas.post import CreatePostRequest
from app.services.auth import CredentialService, validate_demo_api_key
from app.services.embeddings import EmbeddingService
from app.services.evaluation import EvaluationService
from app.services.image_assets import ImageAssetService
from app.services.image_retrieval import ImageRetrievalService
from app.services.image_storage import LocalImageStorage
from app.services.posts import PostService
from app.services.processing_jobs import ProcessingJobService
from app.services.recommendation_reviews import RecommendationReviewService
from app.services.recommendations import RecommendationService
from app.workers.image_processing import ImageProcessingWorker
from scripts.download_corpus import download_corpus

WORKSPACE_NAME = "FlyRank Phase 12.5 Demo"
PROBE_MODEL = "acceptance-probe-ranked-vectors"
MISMATCH_MODEL = "acceptance-probe-mismatch-vectors"
VERSION = "1"


async def _upload(service: ImageAssetService, path: Path) -> ImageAsset:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    upload = UploadFile(
        file=BytesIO(path.read_bytes()),
        filename=path.name,
        headers=Headers({"content-type": mime}),
    )
    try:
        return await service.create(upload)
    finally:
        await upload.close()


def _workspace_for_key() -> UUID:
    settings = get_settings()
    try:
        demo_api_key = validate_demo_api_key(settings.demo_api_key)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    with SessionLocal() as session:
        auth = AuthRepository(session)
        workspace = auth.get_workspace_by_name(WORKSPACE_NAME)
        if workspace is None:
            workspace = Workspace(name=WORKSPACE_NAME)
            auth.add(workspace)
            auth.commit()
            auth.refresh(workspace)
        CredentialService(auth).reconcile_local_demo(
            workspace, api_key=demo_api_key
        )
        return workspace.id


def _clear_workspace(workspace_id, storage: LocalImageStorage) -> None:
    with SessionLocal() as session:
        session.execute(delete(ProcessingJob).where(ProcessingJob.workspace_id == workspace_id))
        session.execute(delete(EvaluationRun).where(EvaluationRun.workspace_id == workspace_id))
        session.execute(delete(AiCallLog).where(AiCallLog.workspace_id == workspace_id))
        session.commit()
        for post in session.scalars(select(Post).where(Post.workspace_id == workspace_id)):
            session.delete(post)
        session.commit()
        for asset in session.scalars(
            select(ImageAsset).where(ImageAsset.workspace_id == workspace_id)
        ):
            storage.delete(asset.storage_key)
            session.delete(asset)
        session.commit()


def _wait_for_job(job_id, workspace_id, *, inline_worker: bool) -> ProcessingJob:
    worker = ImageProcessingWorker(worker_id="phase12.5-inline-seed") if inline_worker else None
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        if worker is not None:
            worker.process_one()
        with SessionLocal() as session:
            job = ProcessingJobRepository(session, workspace_id).get(job_id)
            if job is None:
                raise RuntimeError("Queued acceptance job disappeared")
            if job.status in {
                JobStatus.COMPLETED.value,
                JobStatus.COMPLETED_WITH_ERRORS.value,
                JobStatus.FAILED.value,
            }:
                session.expunge(job)
                return job
        time.sleep(0.1 if inline_worker else 0.5)
    raise RuntimeError("Timed out waiting for the durable worker")


async def seed(json_output: Path, *, inline_worker: bool = False) -> dict[str, object]:
    settings = get_settings()
    manifest = load_corpus_records(settings.corpus_manifest_path)
    corpus_dir = settings.corpus_manifest_path.parent / "corpus"
    await download_corpus(settings.corpus_manifest_path, corpus_dir)
    workspace_id = _workspace_for_key()
    storage = LocalImageStorage(
        settings.image_storage_root,
        max_upload_bytes=settings.max_upload_bytes,
        max_image_pixels=settings.max_image_pixels,
    )
    _clear_workspace(workspace_id, storage)

    with SessionLocal() as session:
        images = ImageAssetRepository(session, workspace_id)
        asset_ids: dict[str, UUID] = {}
        image_service = ImageAssetService(images, storage)
        for record in manifest:
            asset = await _upload(image_service, corpus_dir / str(record["local_filename"]))
            asset_ids[str(record["image_id"])] = asset.id
        job, _ = ProcessingJobService(
            ProcessingJobRepository(session, workspace_id),
            images,
            PostRepository(session, workspace_id),
            max_attempts=settings.processing_max_attempts,
        ).create(
            list(asset_ids.values()),
            idempotency_key="phase12.5-corpus-batch-v1",
        )
        image_job_id = job.id
    image_job = _wait_for_job(image_job_id, workspace_id, inline_worker=inline_worker)
    if image_job.status != JobStatus.COMPLETED.value or image_job.processed_items != 50:
        raise RuntimeError(f"Corpus job did not complete cleanly: {image_job.status}")

    with SessionLocal() as session:
        posts = PostRepository(session, workspace_id)
        fox_post = PostService(posts).create(
            CreatePostRequest(
                title="[Phase 12.5] How red foxes survive winter",
                body="Red foxes remain active while moving through snowy forests.",
                expected_subject="red fox",
                expected_category="animal",
                required_tags=["wildlife"],
            )
        )
        post_job, _ = ProcessingJobService(
            ProcessingJobRepository(session, workspace_id),
            ImageAssetRepository(session, workspace_id),
            posts,
            max_attempts=settings.processing_max_attempts,
        ).create_post_embedding(
            fox_post.id, idempotency_key="phase12.5-fox-post-embedding-v1"
        )
        post_job_id = post_job.id
        fox_post_id = fox_post.id
    completed_post_job = _wait_for_job(
        post_job_id, workspace_id, inline_worker=inline_worker
    )
    if completed_post_job.status != JobStatus.COMPLETED.value:
        raise RuntimeError("Asynchronous post embedding did not complete")

    with SessionLocal() as session:
        posts = PostRepository(session, workspace_id)
        images = ImageAssetRepository(session, workspace_id)
        metadata = ImageMetadataRepository(session, workspace_id)
        embeddings = EmbeddingRepository(session, workspace_id)

        ranked_provider = CorpusFixtureEmbeddingProvider(model=PROBE_MODEL, version=VERSION)
        ranked_embeddings = EmbeddingService(embeddings, images, metadata, posts, ranked_provider)
        ranked_embeddings.embed_post(fox_post_id)
        representatives = ["red_fox_01", "gray_wolf_01", "domestic_dog_01"]
        for image_id in representatives:
            ranked_embeddings.embed_image(asset_ids[image_id])
        ranked_retrieval = ImageRetrievalService(
            posts,
            ImageRetrievalRepository(session, workspace_id),
            embedding_model=PROBE_MODEL,
            embedding_version=VERSION,
            dimensions=384,
        )
        ranked = ranked_retrieval.retrieve(fox_post_id, top_k=3)
        ranking = [
            {"rank": item.rank, "subject": item.subject, "similarity": round(item.similarity_score, 2)}
            for item in ranked.candidates
        ]
        assert [item["subject"] for item in ranking] == [
            "red fox", "gray wolf", "domestic dog"
        ]
        matched = RecommendationService(
            posts, ranked_retrieval, RecommendationRepository(session, workspace_id)
        ).create(fox_post_id, top_k=3)
        assert matched.recommendation is not None
        review = RecommendationReviewService(
            RecommendationRepository(session, workspace_id), posts, images
        ).review(
            matched.recommendation.recommendation_id,
            HumanReviewDecision.APPROVED,
            comment="Deterministic Phase 12.5 acceptance review",
        )

        mismatch_post = PostService(posts).create(
            CreatePostRequest(
                title="[Phase 12.5] Forced mismatch probe",
                body="A red fox article with only a gray wolf candidate.",
                expected_subject="red fox",
                expected_category="animal",
                required_tags=["wildlife"],
            )
        )
        mismatch_provider = CorpusFixtureEmbeddingProvider(model=MISMATCH_MODEL, version=VERSION)
        mismatch_embeddings = EmbeddingService(
            embeddings, images, metadata, posts, mismatch_provider
        )
        mismatch_embeddings.embed_post(mismatch_post.id)
        mismatch_embeddings.embed_image(asset_ids["gray_wolf_01"])
        mismatch_retrieval = ImageRetrievalService(
            posts,
            ImageRetrievalRepository(session, workspace_id),
            embedding_model=MISMATCH_MODEL,
            embedding_version=VERSION,
            dimensions=384,
        )
        refused = RecommendationService(
            posts, mismatch_retrieval, RecommendationRepository(session, workspace_id)
        ).create(mismatch_post.id, top_k=1)
        assert refused.recommendation is None
        assert refused.rejected_candidates[0].reason_code == "SUBJECT_MISMATCH"

        evaluation = EvaluationService(
            EvaluationRepository(session, workspace_id), settings.evaluation_dataset_path
        ).run()
        metadata_count = session.scalar(
            select(func.count(ImageMetadata.id)).join(ImageAsset).where(
                ImageAsset.workspace_id == workspace_id
            )
        )
        low_confidence_count = session.scalar(
            select(func.count(ImageMetadata.id)).join(ImageAsset).where(
                ImageAsset.workspace_id == workspace_id,
                ImageMetadata.is_low_confidence.is_(True),
            )
        )
        accounting_count = session.scalar(
            select(func.count(AiCallLog.id)).where(AiCallLog.workspace_id == workspace_id)
        )

        report: dict[str, object] = {
            "fixture_kind": "pinned_licensed_wikimedia_corpus",
            "workspace_id": str(workspace_id),
            "api_key_prefix": settings.demo_api_key[:12],
            "corpus": {"images": 50, "manifest": str(settings.corpus_manifest_path)},
            "probe_1_async_batch": {
                "job_id": str(image_job.id),
                "status": image_job.status,
                "processed": image_job.processed_items,
                "failed": image_job.failed_items,
                "metadata_records": metadata_count,
                "low_confidence_records": low_confidence_count,
            },
            "probe_2_raw_ranking": ranking,
            "probe_3_forced_mismatch": {
                "status": refused.status,
                "reason_code": refused.rejected_candidates[0].reason_code,
                "explanation": refused.rejected_candidates[0].explanation,
            },
            "probe_4_no_safe_candidate": {
                "status": refused.status,
                "recommendation": None,
                "candidate_rejections": [
                    {
                        "subject": "gray wolf",
                        "reason_code": refused.rejected_candidates[0].reason_code,
                        "explanation": refused.rejected_candidates[0].explanation,
                    }
                ],
            },
            "human_review": review.model_dump(mode="json"),
            "ai_accounting_records": accounting_count,
            "evaluation": {
                "run_id": str(evaluation.run_id),
                "top1_precision_all_posts": evaluation.top1_precision,
                "issued_recommendation_precision": evaluation.issued_recommendation_precision,
                "unsafe_acceptance_count": evaluation.unsafe_acceptance_count,
            },
        }
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Phase 12.5 acceptance demo")
    parser.add_argument("--json-output", type=Path, default=Path("phase12-demo.json"))
    parser.add_argument(
        "--inline-worker",
        action="store_true",
        help="Process queued jobs in-process for local verification without Docker",
    )
    args = parser.parse_args()
    report = asyncio.run(seed(args.json_output, inline_worker=args.inline_worker))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
