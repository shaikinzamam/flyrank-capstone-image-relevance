from types import ModuleType
import sys

from app.providers.embedding import SentenceTransformerEmbeddingProvider


def test_local_provider_pins_revision_and_normalizes(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Encoded:
        def tolist(self) -> list[float]:
            return [0.5, -0.5]

    class StubSentenceTransformer:
        def __init__(self, model: str, *, revision: str) -> None:
            captured.update(model=model, revision=revision)

        def encode(self, text: str, **kwargs: object) -> Encoded:
            captured.update(text=text, **kwargs)
            return Encoded()

    module = ModuleType("sentence_transformers")
    module.SentenceTransformer = StubSentenceTransformer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    provider = SentenceTransformerEmbeddingProvider(
        model="test/model",
        version="pinned-revision",
        dimensions=2,
        normalize=True,
    )

    assert provider.embed("semantic text") == [0.5, -0.5]
    assert captured == {
        "model": "test/model",
        "revision": "pinned-revision",
        "text": "semantic text",
        "normalize_embeddings": True,
        "convert_to_numpy": True,
    }
