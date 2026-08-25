from fastapi.testclient import TestClient

from app.api.dependencies import get_readiness_service
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
