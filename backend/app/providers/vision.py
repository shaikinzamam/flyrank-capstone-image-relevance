from abc import ABC, abstractmethod
import json
from pathlib import Path

from app.core.vision_taxonomy import VISION_TAXONOMY
from app.schemas.image_metadata import VisionMetadata


class ProviderTimeoutError(Exception):
    pass


class ProviderFailureError(Exception):
    pass


class VisionProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def analyze(self, image_path: Path, mime_type: str) -> object: ...


class GeminiVisionProvider(VisionProvider):
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        timeout_seconds: int,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_ms = timeout_seconds * 1000

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def analyze(self, image_path: Path, mime_type: str) -> object:
        if not self._api_key:
            raise ProviderFailureError("Gemini vision is not configured")
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(
                    timeout=self._timeout_ms,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            response = client.models.generate_content(
                model=self._model,
                contents=[
                    types.Part.from_bytes(
                        data=image_path.read_bytes(),
                        mime_type=mime_type,
                    ),
                    (
                        "Classify this image using exactly one approved subject_code. "
                        "Describe only visible content. Approved taxonomy: "
                        + json.dumps(
                            {
                                code: {
                                    "subject": entry.subject,
                                    "category": entry.category,
                                }
                                for code, entry in VISION_TAXONOMY.items()
                            }
                        )
                    ),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=VisionMetadata.model_json_schema(),
                    temperature=0,
                ),
            )
            return response.text
        except TimeoutError as exc:
            raise ProviderTimeoutError("Vision provider timed out") from exc
        except ProviderTimeoutError:
            raise
        except Exception as exc:
            status_code = getattr(exc, "status_code", None) or getattr(
                exc, "code", None
            )
            if status_code in {408, 504} or "timeout" in type(exc).__name__.lower():
                raise ProviderTimeoutError("Vision provider timed out") from exc
            raise ProviderFailureError("Vision provider request failed") from exc
