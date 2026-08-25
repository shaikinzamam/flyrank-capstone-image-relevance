import argparse
import asyncio
import json
from io import BytesIO
from math import sqrt
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageDraw
from sqlalchemy import select
from starlette.datastructures import Headers

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.image_asset import ImageAsset
from app.models.post import Post
from app.models.recommendation import HumanReviewDecision
from app.providers.embedding import EmbeddingProvider
from app.providers.fake import FakeVisionProvider
from app.repositories.embeddings import EmbeddingRepository
from app.repositories.evaluations import EvaluationRepository
from app.repositories.image_assets import ImageAssetRepository
from app.repositories.image_metadata import ImageMetadataRepository
from app.repositories.image_retrieval import ImageRetrievalRepository
from app.repositories.posts import PostRepository
from app.repositories.recommendations import RecommendationRepository
from app.services.embeddings import EmbeddingService
from app.services.evaluation import EvaluationService
from app.services.image_analysis import ImageAnalysisService
from app.services.image_assets import ImageAssetService
from app.services.image_retrieval import ImageRetrievalService
from app.services.image_storage import LocalImageStorage
from app.services.posts import PostService
from app.services.recommendations import RecommendationService
from app.services.recommendation_reviews import RecommendationReviewService
from app.schemas.post import CreatePostRequest

DEMO_PREFIX = "phase12-demo-"
DEMO_POST_PREFIX = "[Phase 12 demo]"
DEMO_MODEL = "phase12-deterministic-demo-vectors"
DEMO_VERSION = "1"

SUBJECTS = (
    {
        "code": "gray_wolf",
        "subject": "gray wolf",
        "label": "GRAY WOLF",
        "color": (99, 108, 118),
        "similarity": 0.93,
        "tags": ["gray wolf", "snow", "winter", "wildlife"],
    },
    {
        "code": "red_fox",
        "subject": "red fox",
        "label": "RED FOX",
        "color": (198, 78, 30),
        "similarity": 0.90,
        "tags": ["red fox", "snow", "winter", "wildlife"],
    },
    {
        "code": "domestic_dog",
        "subject": "domestic dog",
        "label": "DOG",
        "color": (126, 88, 51),
        "similarity": 0.82,
        "tags": ["domestic dog", "snow", "winter", "animal"],
    },
)


def _vector(similarity: float) -> list[float]:
    return [similarity, sqrt(1.0 - similarity**2)] + [0.0] * 382


class DemoEmbeddingProvider(EmbeddingProvider):
    """Known vectors for synthetic demo fixtures; never downloads a model."""

    @property
    def provider_name(self) -> str:
        return "deterministic-demo"

    @property
    def model_name(self) -> str:
        return DEMO_MODEL

    @property
    def model_version(self) -> str:
        return DEMO_VERSION

    @property
    def dimensions(self) -> int:
        return 384

    def embed(self, text: str) -> list[float]:
        normalized = text.lower()
        if normalized.startswith("subject:"):
            for fixture in SUBJECTS:
                if f"subject: {fixture['subject']}" in normalized:
                    return _vector(float(fixture["similarity"]))
        return _vector(1.0)


def _synthetic_png(label: str, color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (640, 420), color=color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((28, 28, 612, 392), outline=(240, 244, 248), width=4)
    draw.text((52, 54), "SYNTHETIC DEMO ASSET", fill=(255, 255, 255))
    draw.text((52, 330), label, fill=(255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


async def _upload(
    service: ImageAssetService,
    *,
    filename: str,
    content: bytes,
) -> ImageAsset:
    upload = UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": "image/png"}),
    )
    try:
        return await service.create(upload)
    finally:
        await upload.close()


def _remove_previous_demo(session, storage: LocalImageStorage) -> None:
    posts = list(
        session.scalars(select(Post).where(Post.title.like(f"{DEMO_POST_PREFIX}%")))
    )
    for post in posts:
        session.delete(post)
    session.commit()

    assets = list(
        session.scalars(
            select(ImageAsset).where(ImageAsset.filename.like(f"{DEMO_PREFIX}%"))
        )
    )
    for asset in assets:
        storage.delete(asset.storage_key)
        session.delete(asset)
    session.commit()


async def seed(json_output: Path) -> dict[str, object]:
    settings = get_settings()
    storage = LocalImageStorage(
        settings.image_storage_root,
        max_upload_bytes=settings.max_upload_bytes,
        max_image_pixels=settings.max_image_pixels,
    )
    provider = DemoEmbeddingProvider()

    with SessionLocal() as session:
        _remove_previous_demo(session, storage)
        images = ImageAssetRepository(session)
        metadata = ImageMetadataRepository(session)
        embeddings = EmbeddingRepository(session)
        posts = PostRepository(session)
        recommendations = RecommendationRepository(session)
        image_service = ImageAssetService(images, storage)
        embedding_service = EmbeddingService(
            embeddings, images, metadata, posts, provider
        )

        assets: dict[str, ImageAsset] = {}
        for fixture in SUBJECTS:
            asset = await _upload(
                image_service,
                filename=f"{DEMO_PREFIX}{fixture['code']}.png",
                content=_synthetic_png(str(fixture["label"]), fixture["color"]),
            )
            vision = FakeVisionProvider(
                {
                    "subject": fixture["subject"],
                    "subject_code": fixture["code"],
                    "category": "animal",
                    "caption": (
                        f"Synthetic Phase 12 fixture representing a {fixture['subject']} "
                        "in a winter scene"
                    ),
                    "tags": fixture["tags"],
                    "attributes": ["synthetic", "winter scene"],
                    "objects": [fixture["subject"], "snow"],
                    "confidence": 0.95,
                }
            )
            ImageAnalysisService(
                images,
                metadata,
                storage,
                vision,
                low_confidence_threshold=settings.vision_low_confidence_threshold,
                vision_budget_usd=None,
            ).analyze(asset.id, reprocess=False)
            embedding_service.embed_image(asset.id)
            assets[str(fixture["code"])] = asset

        post_service = PostService(posts)
        fox_post = post_service.create(
            CreatePostRequest(
                title=f"{DEMO_POST_PREFIX} How red foxes survive winter",
                body="Red foxes remain active while moving through snowy forests.",
                expected_subject="red fox",
                expected_category="animal",
                required_tags=["winter"],
            )
        )
        embedding_service.embed_post(fox_post.id)
        retrieval = ImageRetrievalService(
            posts,
            ImageRetrievalRepository(session),
            embedding_model=DEMO_MODEL,
            embedding_version=DEMO_VERSION,
            dimensions=384,
        )
        raw = retrieval.retrieve(fox_post.id, top_k=3)
        recommendation_service = RecommendationService(
            posts, retrieval, recommendations
        )
        matched = recommendation_service.create(fox_post.id, top_k=3)
        assert matched.recommendation is not None
        review = RecommendationReviewService(
            recommendations, posts, images
        ).review(
            matched.recommendation.recommendation_id,
            HumanReviewDecision.APPROVED,
            comment="Deterministic Phase 12 demo approval",
        )

        fox_embedding = embeddings.get_image(
            assets["red_fox"].id, DEMO_MODEL, DEMO_VERSION
        )
        assert fox_embedding is not None
        session.delete(fox_embedding)
        session.commit()
        refusal_post = post_service.create(
            CreatePostRequest(
                title=f"{DEMO_POST_PREFIX} Fox article with wolf and dog only",
                body="A red fox article evaluated without a fox image candidate.",
                expected_subject="red fox",
                expected_category="animal",
                required_tags=["winter"],
            )
        )
        embedding_service.embed_post(refusal_post.id)
        no_match = recommendation_service.create(refusal_post.id, top_k=2)
        embedding_service.embed_image(assets["red_fox"].id)

        evaluation = EvaluationService(
            EvaluationRepository(session), settings.evaluation_dataset_path
        ).run()

        raw_evidence = [
            {
                "rank": candidate.rank,
                "subject": candidate.subject,
                "similarity": round(candidate.similarity_score, 2),
            }
            for candidate in raw.candidates
        ]
        assert raw_evidence == [
            {"rank": 1, "subject": "gray wolf", "similarity": 0.93},
            {"rank": 2, "subject": "red fox", "similarity": 0.90},
            {"rank": 3, "subject": "domestic dog", "similarity": 0.82},
        ]
        assert matched.status == "matched"
        assert matched.recommendation.image_id == assets["red_fox"].id
        assert matched.rejected_candidates[0].reason_code == "SUBJECT_MISMATCH"
        assert no_match.status == "no_confident_match"
        assert no_match.recommendation is None

        report: dict[str, object] = {
            "fixture_kind": "synthetic_generated_demo_data",
            "image_ids": {key: str(value.id) for key, value in assets.items()},
            "fox_post_id": str(fox_post.id),
            "raw_candidates": raw_evidence,
            "matched_run_id": str(matched.run_id),
            "accepted_recommendation_id": str(
                matched.recommendation.recommendation_id
            ),
            "review_id": str(review.id),
            "no_match_post_id": str(refusal_post.id),
            "no_match_run_id": str(no_match.run_id),
            "no_match_reason": no_match.reason_code,
            "no_match_recommendation_ids": [
                str(candidate.recommendation_id)
                for candidate in no_match.rejected_candidates
            ],
            "evaluation_run_id": str(evaluation.run_id),
            "evaluation_dataset": evaluation.dataset_version,
            "top1_precision": evaluation.top1_precision,
            "unsafe_acceptances": evaluation.unsafe_acceptance_count,
        }

    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed reproducible synthetic Phase 12 demo evidence"
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("artifacts/demo/latest.json"),
        help="Generated demo manifest path",
    )
    args = parser.parse_args()
    report = asyncio.run(seed(args.json_output))
    print(json.dumps(report, indent=2))
    print(f"Demo manifest: {args.json_output}")


if __name__ == "__main__":
    main()
