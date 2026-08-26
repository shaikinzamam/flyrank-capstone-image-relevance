import argparse
import asyncio
import json
import time
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.config import get_settings
from app.services.image_storage import LocalImageStorage


class CorpusDownloadError(Exception):
    pass


def _load_manifest(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusDownloadError("Corpus manifest could not be read") from exc
    images = payload.get("images") if isinstance(payload, dict) else None
    if not isinstance(images, list) or len(images) != payload.get("image_count"):
        raise CorpusDownloadError("Corpus manifest count is invalid")
    required = {
        "image_id",
        "subject",
        "subject_code",
        "category",
        "source_page",
        "download_url",
        "license",
        "creator",
        "local_filename",
        "sha256",
    }
    for item in images:
        if not isinstance(item, dict) or not required <= item.keys():
            raise CorpusDownloadError("Corpus manifest record is invalid")
        if not str(item["download_url"]).startswith("https://upload.wikimedia.org/"):
            raise CorpusDownloadError("Corpus downloads must use frozen Wikimedia URLs")
    return images


def _download(url: str, max_bytes: int) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": "FlyRankCapstone/1.0"})
    for attempt in range(5):
        try:
            with urlopen(request, timeout=30) as response:
                content_type = response.headers.get_content_type()
                content = response.read(max_bytes + 1)
            break
        except HTTPError as exc:
            if exc.code != 429 or attempt == 4:
                raise CorpusDownloadError(f"Download failed: {url}") from exc
            retry_after = exc.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
            time.sleep(min(delay, 15))
        except (URLError, TimeoutError) as exc:
            raise CorpusDownloadError(f"Download failed: {url}") from exc
    else:  # pragma: no cover - loop either succeeds or raises
        raise CorpusDownloadError(f"Download failed: {url}")
    if len(content) > max_bytes:
        raise CorpusDownloadError(f"Downloaded image exceeds size limit: {url}")
    return content, content_type


async def _validate_bytes(
    storage: LocalImageStorage, filename: str, content: bytes, content_type: str
) -> None:
    upload = UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )
    staged = await storage.stage(upload)
    try:
        storage.validate(staged, content_type)
    finally:
        storage.discard(staged)
        await upload.close()


async def download_corpus(manifest_path: Path, output_dir: Path) -> list[dict[str, str]]:
    settings = get_settings()
    records = _load_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    validation = LocalImageStorage(
        output_dir / ".validation",
        max_upload_bytes=settings.max_upload_bytes,
        max_image_pixels=settings.max_image_pixels,
    )
    results: list[dict[str, str]] = []
    for record in records:
        target = output_dir / str(record["local_filename"])
        expected_hash = record["sha256"]
        if target.exists():
            content = target.read_bytes()
            content_type = "image/png" if target.suffix.lower() == ".png" else "image/jpeg"
        else:
            content, content_type = _download(
                str(record["download_url"]), settings.max_upload_bytes
            )
        await _validate_bytes(validation, target.name, content, content_type)
        digest = sha256(content).hexdigest()
        if expected_hash is not None and digest != expected_hash:
            raise CorpusDownloadError(
                f"SHA-256 mismatch for {record['image_id']}; source changed"
            )
        if not target.exists():
            partial = target.with_suffix(target.suffix + ".partial")
            partial.write_bytes(content)
            partial.replace(target)
        results.append(
            {
                "image_id": str(record["image_id"]),
                "filename": target.name,
                "sha256": digest,
            }
        )
        time.sleep(0.25)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download and validate the frozen licensed image corpus"
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("../data/corpus-manifest.json")
    )
    parser.add_argument("--output", type=Path, default=Path("../data/corpus"))
    args = parser.parse_args()
    results = asyncio.run(download_corpus(args.manifest, args.output))
    print(json.dumps({"downloaded_or_verified": len(results), "images": results}, indent=2))


if __name__ == "__main__":
    main()
