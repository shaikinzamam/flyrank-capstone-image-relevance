from hashlib import sha256
from pathlib import Path

import pytest

from app.providers.corpus import (
    CorpusFixtureEmbeddingProvider,
    CorpusFixtureVisionProvider,
    load_corpus_records,
)
from app.core.config import get_settings

MANIFEST = get_settings().corpus_manifest_path
CORPUS = MANIFEST.parent / "corpus"


def test_licensed_corpus_is_complete_pinned_and_locally_reproducible() -> None:
    records = load_corpus_records(MANIFEST)

    assert len(records) == 50
    assert len({record["source_page"] for record in records}) == 50
    assert all(record["license"] and record["creator"] for record in records)
    for record in records:
        content = (CORPUS / str(record["local_filename"])).read_bytes()
        assert sha256(content).hexdigest() == record["sha256"]


def test_corpus_vision_fixture_includes_a_low_confidence_record() -> None:
    provider = CorpusFixtureVisionProvider(MANIFEST)
    ordinary = provider.analyze(CORPUS / "red_fox_01.jpg", "image/jpeg")
    flagged = provider.analyze(CORPUS / "white_tailed_deer_10.jpg", "image/jpeg")

    assert ordinary["subject"] == "red fox"
    assert ordinary["confidence"] == 0.95
    assert flagged["subject"] == "white-tailed deer"
    assert flagged["confidence"] == 0.55


def test_probe_2_vectors_rank_fox_then_wolf_then_dog() -> None:
    provider = CorpusFixtureEmbeddingProvider()
    post = provider.embed("Expected subject: red fox.")
    candidates = {
        subject: provider.embed(f"Subject: {subject}.\nCategory: animal.")
        for subject in ("gray wolf", "red fox", "domestic dog")
    }

    scores = {
        subject: sum(left * right for left, right in zip(post, vector, strict=True))
        for subject, vector in candidates.items()
    }
    assert sorted(scores, key=scores.get, reverse=True) == [
        "red fox",
        "gray wolf",
        "domestic dog",
    ]
    assert scores == pytest.approx(
        {"red fox": 1.0, "gray wolf": 0.8, "domestic dog": 0.6}
    )
