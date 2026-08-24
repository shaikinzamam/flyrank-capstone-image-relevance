from copy import deepcopy
from pathlib import Path

from app.providers.vision import VisionProvider


class FakeVisionProvider(VisionProvider):
    def __init__(self, output: object, *, estimated_cost_usd: float = 0.0) -> None:
        self.output = output
        self.call_count = 0
        self._estimated_cost_usd = estimated_cost_usd

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "deterministic-test-model"

    @property
    def estimated_cost_usd(self) -> float:
        return self._estimated_cost_usd

    def analyze(self, image_path: Path, mime_type: str) -> object:
        self.call_count += 1
        if isinstance(self.output, Exception):
            raise self.output
        return deepcopy(self.output)
