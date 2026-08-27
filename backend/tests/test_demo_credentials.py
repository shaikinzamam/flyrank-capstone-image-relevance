from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.workspace import ApiCredential, Workspace
from app.services.auth import (
    LOCAL_DEMO_CREDENTIAL_NAME,
    hash_api_key,
    validate_demo_api_key,
)
from scripts import seed


KEY_A = "frk_local_A_8Jw3qD6sK9vN2xF5mR7tY4uP1aC0"
KEY_B = "frk_local_B_4Nz7hQ2kV9sD5xM8pT1cR6yW3uE0"


@pytest.fixture
def demo_sessions(monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(
        bind=engine, class_=Session, autoflush=False, expire_on_commit=False
    )
    monkeypatch.setattr(seed, "SessionLocal", sessions)
    try:
        yield sessions
    finally:
        engine.dispose()


def _use_key(monkeypatch: pytest.MonkeyPatch, api_key: str) -> None:
    monkeypatch.setattr(
        seed, "get_settings", lambda: SimpleNamespace(demo_api_key=api_key)
    )


def test_seed_credential_is_rerunnable_and_reuses_workspace(
    demo_sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_key(monkeypatch, KEY_A)
    first_workspace_id = seed._workspace_for_key()
    second_workspace_id = seed._workspace_for_key()

    assert second_workspace_id == first_workspace_id
    with demo_sessions() as session:
        assert session.scalar(select(func.count(Workspace.id))) == 1
        credentials = list(session.scalars(select(ApiCredential)))
        assert len(credentials) == 1
        assert credentials[0].key_hash == hash_api_key(KEY_A)
        assert credentials[0].active is True
        assert credentials[0].revoked_at is None


def test_seed_reactivates_an_existing_revoked_hash_without_duplicate(
    demo_sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_key(monkeypatch, KEY_A)
    workspace_id = seed._workspace_for_key()
    with demo_sessions() as session:
        credential = session.scalar(select(ApiCredential))
        assert credential is not None
        credential.active = False
        credential.revoked_at = credential.created_at
        session.commit()

    assert seed._workspace_for_key() == workspace_id
    with demo_sessions() as session:
        credentials = list(session.scalars(select(ApiCredential)))
        assert len(credentials) == 1
        assert credentials[0].active is True
        assert credentials[0].revoked_at is None


def test_changed_seed_key_revokes_old_and_leaves_one_active_demo_credential(
    demo_sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_key(monkeypatch, KEY_A)
    workspace_id = seed._workspace_for_key()
    _use_key(monkeypatch, KEY_B)
    assert seed._workspace_for_key() == workspace_id

    with demo_sessions() as session:
        credentials = list(
            session.scalars(
                select(ApiCredential).where(
                    ApiCredential.workspace_id == workspace_id,
                    ApiCredential.name == LOCAL_DEMO_CREDENTIAL_NAME,
                )
            )
        )
        assert len(credentials) == 2
        active = [credential for credential in credentials if credential.active]
        assert len(active) == 1
        assert active[0].key_hash == hash_api_key(KEY_B)
        old = next(
            credential
            for credential in credentials
            if credential.key_hash == hash_api_key(KEY_A)
        )
        assert old.revoked_at is not None


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "YOUR_CURRENT_DEMO_KEY",
        "frk_replace-me_12345678901234567890123456789012",
        "frk_too_short",
        "not_frk_8Jw3qD6sK9vN2xF5mR7tY4uP1aC0",
    ],
)
def test_demo_key_validation_rejects_blank_placeholder_and_invalid_values(
    value: str | None,
) -> None:
    with pytest.raises(ValueError):
        validate_demo_api_key(value)


def test_demo_key_validation_accepts_a_high_entropy_local_key() -> None:
    assert validate_demo_api_key(KEY_A) == KEY_A
