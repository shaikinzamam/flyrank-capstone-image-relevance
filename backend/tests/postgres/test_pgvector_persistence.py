import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.models.embedding import PostEmbedding
from app.models.post import Post

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_POSTGRES_PGVECTOR") != "1",
    reason="requires an explicitly enabled migrated PostgreSQL database",
)


def test_pgvector_value_round_trips_with_expected_dimensions() -> None:
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    post_id = uuid4()
    embedding_id = uuid4()
    vector = [float(index) / 384 for index in range(384)]
    try:
        with Session(engine) as session:
            session.add(Post(id=post_id, title="pgvector check", body="round trip"))
            session.add(
                PostEmbedding(
                    id=embedding_id,
                    post_id=post_id,
                    vector=vector,
                    embedding_model="postgres-test",
                    embedding_version="1",
                    dimensions=384,
                    source_text_hash="a" * 64,
                )
            )
            session.commit()
        with Session(engine) as session:
            stored = session.scalar(
                select(PostEmbedding).where(PostEmbedding.id == embedding_id)
            )
            assert stored is not None
            assert len(stored.vector) == 384
            assert list(stored.vector) == pytest.approx(vector, abs=1e-6)
    finally:
        with Session(engine) as session:
            session.execute(delete(Post).where(Post.id == post_id))
            session.commit()
        engine.dispose()
