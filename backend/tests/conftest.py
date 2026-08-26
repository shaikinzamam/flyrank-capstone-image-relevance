from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import (
    get_embedding_provider,
    get_image_storage,
    get_vision_provider,
)
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.providers.fake import FakeVisionProvider
from app.providers.embedding import FakeEmbeddingProvider
from app.models.workspace import ApiCredential, Workspace
from app.services.auth import hash_api_key
from app.services.image_storage import LocalImageStorage


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@dataclass(frozen=True)
class ImageApiContext:
    client: TestClient
    storage: LocalImageStorage
    session_factory: sessionmaker[Session]
    vision_provider: FakeVisionProvider
    embedding_provider: FakeEmbeddingProvider
    workspace_id: UUID
    api_key: str


@pytest.fixture
def image_api(tmp_path: Path) -> Generator[ImageApiContext, None, None]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )
    storage = LocalImageStorage(
        tmp_path / "uploads",
        max_upload_bytes=1024,
        max_image_pixels=10_000,
    )
    vision_provider = FakeVisionProvider(
        {
            "subject": "red fox",
            "subject_code": "red_fox",
            "category": "animal",
            "caption": "A red fox standing in a snowy forest",
            "tags": ["red fox", "snow", "forest", "wildlife"],
            "attributes": ["orange fur", "winter"],
            "objects": ["fox", "trees", "snow"],
            "confidence": 0.96,
        }
    )
    embedding_provider = FakeEmbeddingProvider()
    api_key = "frk_test_workspace_a_000000000000000000000000"
    with test_session_factory() as session:
        workspace = Workspace(name="Test Workspace A")
        session.add(workspace)
        session.flush()
        session.add(
            ApiCredential(
                workspace_id=workspace.id,
                key_hash=hash_api_key(api_key),
                key_prefix=api_key[:12],
                name="pytest",
            )
        )
        session.commit()
        workspace_id = workspace.id

    def override_database_session() -> Generator[Session, None, None]:
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_database_session
    app.dependency_overrides[get_image_storage] = lambda: storage
    app.dependency_overrides[get_vision_provider] = lambda: vision_provider
    app.dependency_overrides[get_embedding_provider] = lambda: embedding_provider
    try:
        with TestClient(app) as test_client:
            test_client.headers.update({"Authorization": f"Bearer {api_key}"})
            yield ImageApiContext(
                test_client,
                storage,
                test_session_factory,
                vision_provider,
                embedding_provider,
                workspace_id,
                api_key,
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_image_storage, None)
        app.dependency_overrides.pop(get_vision_provider, None)
        app.dependency_overrides.pop(get_embedding_provider, None)
        engine.dispose()


def create_postgres_workspace(session: Session, prefix: str) -> UUID:
    workspace = Workspace(name=f"{prefix}-{uuid4().hex}")
    session.add(workspace)
    session.flush()
    return workspace.id
