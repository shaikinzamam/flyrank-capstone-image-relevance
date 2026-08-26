import json
from hashlib import sha256
from math import sqrt
from pathlib import Path

from app.providers.embedding import EmbeddingProvider
from app.providers.vision import ProviderConfigurationError, VisionProvider


class CorpusManifestError(ProviderConfigurationError):
    pass


def load_corpus_records(manifest_path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusManifestError("Licensed corpus manifest could not be read") from exc
    records = payload.get("images") if isinstance(payload, dict) else None
    if not isinstance(records, list) or len(records) != 50:
        raise CorpusManifestError("Licensed corpus manifest must contain 50 images")
    hashes: set[str] = set()
    for record in records:
        digest = record.get("sha256") if isinstance(record, dict) else None
        if not isinstance(digest, str) or len(digest) != 64 or digest in hashes:
            raise CorpusManifestError("Corpus records require unique pinned SHA-256 values")
        hashes.add(digest)
    return records


class CorpusFixtureVisionProvider(VisionProvider):
    """Deterministic metadata for the pinned, licensed acceptance corpus."""

    def __init__(self, manifest_path: Path) -> None:
        self._records = {
            str(record["sha256"]): record
            for record in load_corpus_records(manifest_path)
        }

    @property
    def provider_name(self) -> str:
        return "licensed-corpus-fixture"

    @property
    def model_name(self) -> str:
        return "manifest-ground-truth-v1"

    @property
    def estimated_cost_usd(self) -> float:
        return 0.0

    def analyze(self, image_path: Path, mime_type: str) -> object:
        del mime_type
        digest = sha256(image_path.read_bytes()).hexdigest()
        record = self._records.get(digest)
        if record is None:
            raise CorpusManifestError("Image is not part of the pinned acceptance corpus")
        subject = str(record["subject"])
        image_id = str(record["image_id"])
        return {
            "subject": subject,
            "subject_code": str(record["subject_code"]),
            "category": str(record["category"]),
            "caption": f"Licensed corpus fixture {image_id} showing a {subject}",
            "tags": [subject, "wildlife", "licensed corpus"],
            "attributes": ["reproducible acceptance fixture"],
            "objects": [subject],
            "confidence": 0.55 if image_id == "white_tailed_deer_10" else 0.95,
        }


class CorpusFixtureEmbeddingProvider(EmbeddingProvider):
    """Known normalized vectors used only for reproducible acceptance evidence."""

    _SIMILARITIES = {
        "red fox": 1.0,
        "gray wolf": 0.8,
        "domestic dog": 0.6,
        "brown bear": 0.3,
        "white-tailed deer": 0.1,
    }

    def __init__(self, *, model: str = "licensed-corpus-vectors", version: str = "1") -> None:
        self._model = model
        self._version = version

    @property
    def provider_name(self) -> str:
        return "licensed-corpus-fixture"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def model_version(self) -> str:
        return self._version

    @property
    def dimensions(self) -> int:
        return 384

    def embed(self, text: str) -> list[float]:
        normalized = text.lower()
        similarity = 1.0
        if normalized.startswith("subject:"):
            for subject, score in self._SIMILARITIES.items():
                if f"subject: {subject}." in normalized:
                    similarity = score
                    break
        return [similarity, sqrt(max(0.0, 1.0 - similarity**2))] + [0.0] * 382
