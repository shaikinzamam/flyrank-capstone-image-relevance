from types import SimpleNamespace
from uuid import uuid4

import app.api.dependencies as dependencies
from tests.conftest import ImageApiContext


def test_synchronous_provider_endpoints_are_hidden_outside_development(
    image_api: ImageApiContext,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(app_environment="production"),
    )

    resource_id = uuid4()
    for path in (
        f"/images/{resource_id}/analyze",
        f"/images/{resource_id}/embedding/debug-sync",
        f"/posts/{resource_id}/embedding/debug-sync",
    ):
        response = image_api.client.post(path)
        assert response.status_code == 404, path
        assert response.json() == {"detail": "Not found"}
