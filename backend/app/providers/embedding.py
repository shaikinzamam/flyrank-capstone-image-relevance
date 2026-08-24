from abc import ABC, abstractmethod
from hashlib import sha256
from math import sqrt


class EmbeddingProviderError(Exception):
    pass


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @property
    @abstractmethod
    def model_version(self) -> str: ...

    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    @property
    def estimated_cost_usd(self) -> float:
        return 0.0

    @abstractmethod
    def embed(self, text: str) -> list[float]: ...


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        model: str,
        version: str,
        dimensions: int,
        normalize: bool,
    ) -> None:
        self._model_name = model
        self._version = version
        self._dimensions = dimensions
        self._normalize = normalize
        self._model = None

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._version

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        try:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(
                    self._model_name, revision=self._version
                )
            encoded = self._model.encode(
                text,
                normalize_embeddings=self._normalize,
                convert_to_numpy=True,
            )
            return [float(value) for value in encoded.tolist()]
        except Exception as exc:
            raise EmbeddingProviderError("Local embedding generation failed") from exc


class FakeEmbeddingProvider(EmbeddingProvider):
    """Stable, normalized embeddings for tests; never downloads a model."""

    def __init__(
        self,
        *,
        dimensions: int = 384,
        model: str = "deterministic-fake-embedding",
        version: str = "1",
        output: list[float] | Exception | None = None,
    ) -> None:
        self._dimensions = dimensions
        self._model = model
        self._version = version
        self.output = output
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def model_version(self) -> str:
        return self._version

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        self.call_count += 1
        if isinstance(self.output, Exception):
            raise self.output
        if self.output is not None:
            return list(self.output)
        values: list[float] = []
        counter = 0
        while len(values) < self._dimensions:
            digest = sha256(f"{text}\0{counter}".encode()).digest()
            values.extend((byte - 127.5) / 127.5 for byte in digest)
            counter += 1
        values = values[: self._dimensions]
        norm = sqrt(sum(value * value for value in values))
        return [value / norm for value in values]
