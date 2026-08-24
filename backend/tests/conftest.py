from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_image_storage
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
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

    def override_database_session() -> Generator[Session, None, None]:
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_database_session
    app.dependency_overrides[get_image_storage] = lambda: storage
    try:
        with TestClient(app) as test_client:
            yield ImageApiContext(test_client, storage, test_session_factory)
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_image_storage, None)
        engine.dispose()
