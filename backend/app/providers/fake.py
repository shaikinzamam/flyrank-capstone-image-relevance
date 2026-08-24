from copy import deepcopy
from pathlib import Path

from app.providers.vision import VisionProvider


class FakeVisionProvider(VisionProvider):
    def __init__(self, output: object) -> None:
        self.output = output
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "deterministic-test-model"

    def analyze(self, image_path: Path, mime_type: str) -> object:
        self.call_count += 1
        if isinstance(self.output, Exception):
            raise self.output
        return deepcopy(self.output)
