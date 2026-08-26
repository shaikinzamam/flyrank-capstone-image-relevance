from io import BytesIO
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models.workspace import ApiCredential, Workspace
from app.services.auth import hash_api_key
from tests.conftest import ImageApiContext


def _png(color: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _create_workspace_b(context: ImageApiContext) -> tuple[UUID, str]:
    api_key = "frk_test_workspace_b_111111111111111111111111"
    with context.session_factory() as session:
        workspace = Workspace(name=f"Test Workspace B {uuid4()}")
        session.add(workspace)
        session.flush()
        session.add(
            ApiCredential(
                workspace_id=workspace.id,
                key_hash=hash_api_key(api_key),
                key_prefix=api_key[:12],
                name="pytest-b",
            )
        )
        session.commit()
        return workspace.id, api_key


def test_missing_and_invalid_credentials_are_401_while_health_is_public(
    image_api: ImageApiContext,
) -> None:
    with TestClient(app) as anonymous:
        assert anonymous.get("/health").status_code == 200
        assert anonymous.get("/ready").status_code == 200
        missing = anonymous.get("/images")
        invalid = anonymous.get(
            "/images", headers=_headers("frk_invalid_credential")
        )
    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"


def test_browser_preflight_allows_bearer_authorization_header(
    image_api: ImageApiContext,
) -> None:
    response = image_api.client.options(
        "/images",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_valid_credential_resolves_workspace_and_duplicate_hash_is_tenant_scoped(
    image_api: ImageApiContext,
) -> None:
    _, key_b = _create_workspace_b(image_api)
    content = _png("purple")
    created_a = image_api.client.post(
        "/images", files={"file": ("same.png", content, "image/png")}
    )
    created_b = image_api.client.post(
        "/images",
        files={"file": ("same.png", content, "image/png")},
        headers=_headers(key_b),
    )
    duplicate_a = image_api.client.post(
        "/images", files={"file": ("same-again.png", content, "image/png")}
    )
    assert created_a.status_code == 201
    assert created_b.status_code == 201
    assert duplicate_a.status_code == 409
    assert {item["id"] for item in image_api.client.get("/images").json()} == {
        created_a.json()["id"]
    }
    assert {
        item["id"]
        for item in image_api.client.get("/images", headers=_headers(key_b)).json()
    } == {created_b.json()["id"]}


def test_workspace_a_cannot_access_or_mutate_workspace_b_resources(
    image_api: ImageApiContext,
) -> None:
    _, key_b = _create_workspace_b(image_api)
    headers_b = _headers(key_b)
    image_b = image_api.client.post(
        "/images",
        files={"file": ("fox-b.png", _png("orange"), "image/png")},
        headers=headers_b,
    ).json()
    assert image_api.client.post(
        f"/images/{image_b['id']}/analyze", headers=headers_b
    ).status_code == 200
    image_api.embedding_provider.output = [1.0] + [0.0] * 383
    assert image_api.client.post(
        f"/images/{image_b['id']}/embedding/debug-sync", headers=headers_b
    ).status_code == 200
    post_b = image_api.client.post(
        "/posts",
        json={
            "title": "Workspace B fox",
            "body": "A red fox in winter.",
            "expected_subject": "red fox",
            "expected_category": "animal",
            "required_tags": [],
        },
        headers=headers_b,
    ).json()
    image_api.embedding_provider.output = [1.0] + [0.0] * 383
    assert image_api.client.post(
        f"/posts/{post_b['id']}/embedding/debug-sync", headers=headers_b
    ).status_code == 200
    candidates_b = image_api.client.get(
        f"/posts/{post_b['id']}/image-candidates", headers=headers_b
    )
    assert candidates_b.status_code == 200
    recommendation_b = image_api.client.post(
        f"/posts/{post_b['id']}/recommendations", headers=headers_b
    ).json()["recommendation"]
    assert recommendation_b is not None
    recommendation_id = recommendation_b["recommendation_id"]
    job_b = image_api.client.post(
        "/images/process",
        json={"image_ids": [image_b["id"]], "idempotency_key": "workspace-b-job"},
        headers=headers_b,
    ).json()
    evaluation_b = image_api.client.post("/evaluation/run", headers=headers_b).json()

    for path in (
        f"/images/{image_b['id']}",
        f"/images/{image_b['id']}/content",
        f"/posts/{post_b['id']}",
        f"/posts/{post_b['id']}/image-candidates",
        f"/recommendations/{recommendation_id}",
        f"/jobs/{job_b['id']}",
        f"/evaluation/{evaluation_b['run_id']}",
    ):
        assert image_api.client.get(path).status_code == 404, path

    assert image_api.client.post(
        f"/posts/{post_b['id']}/recommendations"
    ).status_code == 404
    assert image_api.client.post(
        f"/recommendations/{recommendation_id}/approve", json={"comment": "no"}
    ).status_code == 404
    assert image_api.client.post(
        "/images/process",
        json={"image_ids": [image_b["id"]], "idempotency_key": "cross-tenant"},
    ).status_code == 404
    assert all(item["id"] != image_b["id"] for item in image_api.client.get("/images").json())
    assert all(item["id"] != post_b["id"] for item in image_api.client.get("/posts").json())
    assert image_api.client.get("/evaluation/latest").status_code == 404
