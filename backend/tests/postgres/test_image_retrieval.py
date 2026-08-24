import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.models.embedding import ImageEmbedding, PostEmbedding
from app.models.image_asset import ImageAsset
from app.models.image_metadata import ImageMetadata
from app.models.post import Post
from app.repositories.image_retrieval import ImageRetrievalRepository
from app.repositories.posts import PostRepository
from app.services.image_retrieval import ImageRetrievalService

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_POSTGRES_PGVECTOR") != "1",
    reason="requires an explicitly enabled migrated PostgreSQL database",
)


def vector(first: float, second: float) -> list[float]:
    return [first, second] + [0.0] * 382


def test_postgresql_pgvector_cosine_query_ranks_known_vectors() -> None:
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    post_id = uuid4()
    subjects = [
        ("red_fox", "red fox", "fox", vector(0.95, 0.05)),
        ("gray_wolf", "gray wolf", "wolf", vector(0.70, 0.30)),
        ("domestic_dog", "domestic dog", "dog", vector(0.10, 0.90)),
    ]
    image_ids = [uuid4() for _ in subjects]
    model = "known-vector-ranking-test"
    version = "1"
    try:
        with Session(engine) as session:
            session.add(
                Post(id=post_id, title="Winter foxes", body="Red fox survival")
            )
            session.add(
                PostEmbedding(
                    post_id=post_id,
                    vector=vector(1.0, 0.0),
                    embedding_model=model,
                    embedding_version=version,
                    dimensions=384,
                    source_text_hash="p" * 64,
                )
            )
            for index, (subject_code, subject, object_name, embedding) in enumerate(
                subjects
            ):
                image_id = image_ids[index]
                token = uuid4().hex
                session.add(
                    ImageAsset(
                        id=image_id,
                        filename=f"{subject_code}.png",
                        storage_key=f"ranking/{token}.png",
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
                        subject_code=subject_code,
                        category="animal",
                        caption=f"A {subject} in snow",
                        tags=[subject, "snow"],
                        attributes=["winter coat"],
                        objects=[object_name, "snow"],
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
                        vector=embedding,
                        embedding_model=model,
                        embedding_version=version,
                        dimensions=384,
                        source_text_hash=str(index) * 64,
                    )
                )
            session.commit()

        with Session(engine) as session:
            service = ImageRetrievalService(
                PostRepository(session),
                ImageRetrievalRepository(session),
                embedding_model=model,
                embedding_version=version,
                dimensions=384,
            )
            result = service.retrieve(post_id, top_k=3)

        assert [candidate.subject for candidate in result.candidates] == [
            "red fox",
            "gray wolf",
            "domestic dog",
        ]
        assert [candidate.rank for candidate in result.candidates] == [1, 2, 3]
        assert [candidate.similarity_score for candidate in result.candidates] == (
            pytest.approx([0.9986178293, 0.9191450300, 0.1104315261], abs=1e-6)
        )
    finally:
        with Session(engine) as session:
            session.execute(delete(Post).where(Post.id == post_id))
            session.execute(delete(ImageAsset).where(ImageAsset.id.in_(image_ids)))
            session.commit()
        engine.dispose()
