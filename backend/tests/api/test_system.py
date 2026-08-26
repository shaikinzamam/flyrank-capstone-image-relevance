from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.api.dependencies import get_readiness_service
from app.core.config import Settings
from app.main import app


class StubReadinessService:
    def __init__(self, ready: bool) -> None:
        self._ready = ready

    def is_ready(self) -> bool:
        return self._ready


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_local_frontend_origin_is_allowed_by_cors(client: TestClient) -> None:
    response = client.options(
        "/images",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:3000"
    )


def test_cors_configuration_rejects_wildcards() -> None:
    with pytest.raises(ValidationError, match="explicit origins"):
        Settings(_env_file=None, CORS_ALLOWED_ORIGINS="*")


def test_malformed_uuid_is_a_clean_validation_error(image_api) -> None:
    response = image_api.client.get("/images/not-a-uuid")

    assert response.status_code == 422
    assert "traceback" not in response.text.lower()


def test_ready_returns_database_status(client: TestClient) -> None:
    app.dependency_overrides[get_readiness_service] = lambda: StubReadinessService(True)
    try:
        response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "reachable"}


def test_ready_returns_503_when_database_is_unavailable(client: TestClient) -> None:
    app.dependency_overrides[get_readiness_service] = lambda: StubReadinessService(False)
    try:
        response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}
