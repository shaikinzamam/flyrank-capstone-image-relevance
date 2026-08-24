from copy import deepcopy
from io import BytesIO
from uuid import UUID, uuid4

from PIL import Image
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.models.image_asset import ImageAsset
from app.models.image_metadata import AiCallLog, ImageMetadata
from app.providers.vision import ProviderFailureError, ProviderTimeoutError
from app.schemas.image_metadata import VisionMetadata
from tests.conftest import ImageApiContext


VALID_METADATA = {
    "subject": "red fox",
    "subject_code": "red_fox",
    "category": "animal",
    "caption": "A red fox standing in a snowy forest",
    "tags": ["red fox", "snow", "forest", "wildlife"],
    "attributes": ["orange fur", "winter"],
    "objects": ["fox", "trees", "snow"],
    "confidence": 0.96,
}


def upload_image(context: ImageApiContext) -> dict:
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color="red").save(buffer, format="PNG")
    response = context.client.post(
        "/images",
        files={"file": ("fox.png", buffer.getvalue(), "image/png")},
    )
    assert response.status_code == 201
    return response.json()


def test_valid_structured_metadata_is_accepted(image_api: ImageApiContext) -> None:
    created = upload_image(image_api)

    response = image_api.client.post(f"/images/{created['id']}/analyze")

    assert response.status_code == 200
    body = response.json()
    assert body["processing_status"] == "processed"
    assert body["reused"] is False
    assert body["metadata"]["subject"] == "red fox"
    assert body["metadata"]["metadata_status"] == "trusted"
    assert body["metadata"]["is_low_confidence"] is False


def test_malformed_provider_output_is_rejected(image_api: ImageApiContext) -> None:
    created = upload_image(image_api)
    image_api.vision_provider.output = "not-json"

    response = image_api.client.post(f"/images/{created['id']}/analyze")

    assert response.status_code == 502
    assert response.json() == {"detail": "Vision provider returned malformed JSON"}
    with image_api.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ImageMetadata)) == 0
        asset = session.get(ImageAsset, UUID(created["id"]))
        assert asset is not None
        assert asset.processing_status == "failed"


@pytest.mark.parametrize(
    ("mutation", "expected_detail"),
    [
        (lambda value: value.pop("subject"), "Vision metadata failed schema validation"),
        (
            lambda value: value.update(confidence=1.1),
            "Vision metadata failed schema validation",
        ),
        (
            lambda value: value.update(tags=[]),
            "Vision metadata failed schema validation",
        ),
    ],
    ids=["missing-required-field", "invalid-confidence", "empty-tags"],
)
def test_invalid_metadata_is_rejected(
    image_api: ImageApiContext,
    mutation,
    expected_detail: str,
) -> None:
    created = upload_image(image_api)
    invalid = deepcopy(VALID_METADATA)
    mutation(invalid)
    image_api.vision_provider.output = invalid

    response = image_api.client.post(f"/images/{created['id']}/analyze")

    assert response.status_code == 502
    assert response.json() == {"detail": expected_detail}
    with image_api.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ImageMetadata)) == 0


def test_blank_tags_are_rejected_by_schema() -> None:
    invalid = deepcopy(VALID_METADATA)
    invalid["tags"] = ["   "]

    with pytest.raises(ValidationError):
        VisionMetadata.model_validate(invalid)


def test_duplicate_tags_are_normalized_and_deduplicated() -> None:
    raw = deepcopy(VALID_METADATA)
    raw["tags"] = ["Red Fox", " red fox ", "SNOW", "snow"]

    validated = VisionMetadata.model_validate(raw)

    assert validated.tags == ["red fox", "snow"]


def test_unknown_taxonomy_value_is_rejected() -> None:
    invalid = deepcopy(VALID_METADATA)
    invalid.update(subject="arctic fox", subject_code="arctic_fox")

    with pytest.raises(ValidationError):
        VisionMetadata.model_validate(invalid)


def test_low_confidence_metadata_is_flagged(image_api: ImageApiContext) -> None:
    created = upload_image(image_api)
    image_api.vision_provider.output = {**VALID_METADATA, "confidence": 0.69}

    response = image_api.client.post(f"/images/{created['id']}/analyze")

    assert response.status_code == 200
    metadata = response.json()["metadata"]
    assert metadata["is_low_confidence"] is True
    assert metadata["metadata_status"] == "flagged"


def test_valid_metadata_and_call_accounting_are_persisted(
    image_api: ImageApiContext,
) -> None:
    created = upload_image(image_api)

    response = image_api.client.post(f"/images/{created['id']}/analyze")

    assert response.status_code == 200
    with image_api.session_factory() as session:
        metadata = session.scalar(
            select(ImageMetadata).where(
                ImageMetadata.image_id == UUID(created["id"])
            )
        )
        assert metadata is not None
        assert metadata.tags == VALID_METADATA["tags"]
        asset = session.get(ImageAsset, UUID(created["id"]))
        assert asset is not None
        assert asset.processing_status == "processed"
        call = session.scalar(select(AiCallLog))
        assert call is not None
        assert call.status == "succeeded"
        assert call.retry_count == 0
        assert call.estimated_cost_usd == 0.0


def test_provider_failure_marks_first_analysis_failed(
    image_api: ImageApiContext,
) -> None:
    created = upload_image(image_api)
    image_api.vision_provider.output = ProviderFailureError("provider exploded")

    response = image_api.client.post(f"/images/{created['id']}/analyze")

    assert response.status_code == 503
    assert response.json() == {"detail": "Vision provider request failed"}
    with image_api.session_factory() as session:
        asset = session.get(ImageAsset, UUID(created["id"]))
        assert asset is not None
        assert asset.processing_status == "failed"
        call = session.scalar(select(AiCallLog))
        assert call is not None
        assert call.error_code == "provider_failure"


def test_provider_timeout_has_distinct_error_and_failed_state(
    image_api: ImageApiContext,
) -> None:
    created = upload_image(image_api)
    image_api.vision_provider.output = ProviderTimeoutError("too slow")

    response = image_api.client.post(f"/images/{created['id']}/analyze")

    assert response.status_code == 504
    assert response.json() == {"detail": "Vision provider timed out"}
    with image_api.session_factory() as session:
        asset = session.get(ImageAsset, UUID(created["id"]))
        assert asset is not None
        assert asset.processing_status == "failed"
        call = session.scalar(select(AiCallLog))
        assert call is not None
        assert call.error_code == "provider_timeout"


def test_analyze_missing_image_returns_404(image_api: ImageApiContext) -> None:
    response = image_api.client.post(f"/images/{uuid4()}/analyze")

    assert response.status_code == 404
    assert response.json() == {"detail": "Image asset not found"}
    assert image_api.vision_provider.call_count == 0


def test_repeated_analyze_reuses_existing_metadata(
    image_api: ImageApiContext,
) -> None:
    created = upload_image(image_api)
    first = image_api.client.post(f"/images/{created['id']}/analyze")
    second = image_api.client.post(f"/images/{created['id']}/analyze")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["reused"] is True
    assert second.json()["metadata"]["id"] == first.json()["metadata"]["id"]
    assert image_api.vision_provider.call_count == 1
    with image_api.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ImageMetadata)) == 1
        assert session.scalar(select(func.count()).select_from(AiCallLog)) == 1


def test_explicit_reprocess_replaces_existing_metadata(
    image_api: ImageApiContext,
) -> None:
    created = upload_image(image_api)
    first = image_api.client.post(f"/images/{created['id']}/analyze")
    image_api.vision_provider.output = {
        **VALID_METADATA,
        "caption": "A red fox looking toward the camera",
    }

    second = image_api.client.post(
        f"/images/{created['id']}/analyze?reprocess=true"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["reused"] is False
    assert second.json()["metadata"]["id"] == first.json()["metadata"]["id"]
    assert second.json()["metadata"]["caption"] == (
        "A red fox looking toward the camera"
    )
    assert image_api.vision_provider.call_count == 2
