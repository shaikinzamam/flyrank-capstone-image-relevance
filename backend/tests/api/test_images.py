from io import BytesIO
import hashlib
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy import func, select

from app.models.image_asset import ImageAsset
from tests.conftest import ImageApiContext


def image_bytes(image_format: str, color: str = "red") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=color).save(buffer, format=image_format)
    return buffer.getvalue()


def upload(
    context: ImageApiContext,
    *,
    filename: str,
    content: bytes,
    mime_type: str,
):
    return context.client.post(
        "/images",
        files={"file": (filename, content, mime_type)},
    )


def test_valid_jpeg_upload(image_api: ImageApiContext) -> None:
    content = image_bytes("JPEG")

    response = upload(
        image_api,
        filename="original-name.jpg",
        content=content,
        mime_type="image/jpeg",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "original-name.jpg"
    assert body["mime_type"] == "image/jpeg"
    assert body["byte_size"] == len(content)
    assert body["sha256"] == hashlib.sha256(content).hexdigest()
    assert body["processing_status"] == "uploaded"
    assert body["storage_key"].endswith(".jpg")
    assert not body["storage_key"].startswith(("/", "\\"))
    assert (image_api.storage.root / body["storage_key"]).is_file()


def test_valid_png_upload(image_api: ImageApiContext) -> None:
    response = upload(
        image_api,
        filename="pixel.png",
        content=image_bytes("PNG"),
        mime_type="image/png",
    )

    assert response.status_code == 201
    assert response.json()["mime_type"] == "image/png"
    assert response.json()["storage_key"].endswith(".png")


def test_unsupported_file_type_is_rejected(image_api: ImageApiContext) -> None:
    response = upload(
        image_api,
        filename="animation.gif",
        content=image_bytes("GIF"),
        mime_type="image/gif",
    )

    assert response.status_code == 415
    assert response.json() == {
        "detail": "Only JPEG, PNG, and WEBP images are supported"
    }


def test_fake_jpeg_is_rejected(image_api: ImageApiContext) -> None:
    response = upload(
        image_api,
        filename="not-really-an-image.jpg",
        content=b"plain text pretending to be a jpeg",
        mime_type="image/jpeg",
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Uploaded bytes are not a valid image"}


def test_declared_mime_must_match_decoded_format(image_api: ImageApiContext) -> None:
    response = upload(
        image_api,
        filename="mismatch.jpg",
        content=image_bytes("PNG"),
        mime_type="image/jpeg",
    )

    assert response.status_code == 415
    assert response.json() == {
        "detail": "Declared MIME type does not match the decoded image format"
    }


def test_oversized_upload_is_rejected(image_api: ImageApiContext) -> None:
    response = upload(
        image_api,
        filename="too-large.jpg",
        content=b"x" * (image_api.storage.max_upload_bytes + 1),
        mime_type="image/jpeg",
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "Image exceeds the 1024-byte upload limit"
    }


def test_duplicate_upload_returns_conflict_without_duplicate_row(
    image_api: ImageApiContext,
) -> None:
    content = image_bytes("PNG")
    first = upload(
        image_api,
        filename="first.png",
        content=content,
        mime_type="image/png",
    )
    duplicate = upload(
        image_api,
        filename="renamed.png",
        content=content,
        mime_type="image/png",
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": "An image with identical content already exists"
    }
    with image_api.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ImageAsset)) == 1
    stored_files = [
        path for path in image_api.storage.root.rglob("*") if path.is_file()
    ]
    assert len(stored_files) == 1


def test_list_images(image_api: ImageApiContext) -> None:
    upload(
        image_api,
        filename="red.png",
        content=image_bytes("PNG", "red"),
        mime_type="image/png",
    )
    upload(
        image_api,
        filename="blue.png",
        content=image_bytes("PNG", "blue"),
        mime_type="image/png",
    )

    response = image_api.client.get("/images")

    assert response.status_code == 200
    assert {item["filename"] for item in response.json()} == {"red.png", "blue.png"}


def test_get_image_by_id(image_api: ImageApiContext) -> None:
    created = upload(
        image_api,
        filename="detail.png",
        content=image_bytes("PNG"),
        mime_type="image/png",
    ).json()

    response = image_api.client.get(f"/images/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_image_content_is_safely_served_with_stored_mime(
    image_api: ImageApiContext,
) -> None:
    content = image_bytes("PNG")
    created = upload(
        image_api,
        filename="served.png",
        content=content,
        mime_type="image/png",
    ).json()

    response = image_api.client.get(f"/images/{created['id']}/content")

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "private" in response.headers["cache-control"]


def test_image_details_compose_metadata_and_embedding_state(
    image_api: ImageApiContext,
) -> None:
    created = upload(
        image_api,
        filename="details.png",
        content=image_bytes("PNG"),
        mime_type="image/png",
    ).json()
    pending = image_api.client.get(f"/images/{created['id']}/details")
    analyzed = image_api.client.post(f"/images/{created['id']}/analyze")
    embedded = image_api.client.post(f"/images/{created['id']}/embedding/debug-sync")
    details = image_api.client.get(f"/images/{created['id']}/details")

    assert pending.status_code == 200
    assert pending.json()["metadata"] is None
    assert pending.json()["embeddings"] == []
    assert analyzed.status_code == embedded.status_code == 200
    assert details.status_code == 200
    assert details.json()["asset"]["id"] == created["id"]
    assert details.json()["metadata"]["subject_code"] == "red_fox"
    assert details.json()["embeddings"][0]["dimensions"] == 384


def test_tampered_stored_image_content_returns_410(
    image_api: ImageApiContext,
) -> None:
    created = upload(
        image_api,
        filename="tampered.png",
        content=image_bytes("PNG"),
        mime_type="image/png",
    ).json()
    path = image_api.storage.root / created["storage_key"]
    path.write_bytes(b"tampered")

    response = image_api.client.get(f"/images/{created['id']}/content")

    assert response.status_code == 410
    assert "integrity" in response.json()["detail"]


def test_stored_image_size_must_match_trusted_database_state(
    image_api: ImageApiContext,
) -> None:
    created = upload(
        image_api,
        filename="size-mismatch.png",
        content=image_bytes("PNG"),
        mime_type="image/png",
    ).json()
    with image_api.session_factory() as session:
        asset = session.get(ImageAsset, UUID(created["id"]))
        assert asset is not None
        asset.byte_size += 1
        session.commit()

    response = image_api.client.get(f"/images/{created['id']}/content")

    assert response.status_code == 410
    assert response.json() == {
        "detail": "Stored image no longer passes validation"
    }


def test_missing_image_returns_404(image_api: ImageApiContext) -> None:
    response = image_api.client.get(f"/images/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Image asset not found"}


def test_uploaded_image_is_persisted(image_api: ImageApiContext) -> None:
    created = upload(
        image_api,
        filename="persisted.png",
        content=image_bytes("PNG"),
        mime_type="image/png",
    ).json()

    with image_api.session_factory() as session:
        asset = session.get(ImageAsset, UUID(created["id"]))
        assert asset is not None
        assert asset.filename == "persisted.png"
        assert asset.storage_key == created["storage_key"]
        assert asset.sha256 == created["sha256"]
        assert asset.processing_status == "uploaded"
