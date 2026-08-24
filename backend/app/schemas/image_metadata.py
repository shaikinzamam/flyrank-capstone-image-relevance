from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.vision_taxonomy import VISION_TAXONOMY

BoundedText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
TagText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]


class VisionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    subject: Annotated[BoundedText, StringConstraints(max_length=100)]
    subject_code: Annotated[
        BoundedText,
        StringConstraints(
            max_length=64,
            pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$",
        ),
    ]
    category: Annotated[BoundedText, StringConstraints(max_length=50)]
    caption: Annotated[BoundedText, StringConstraints(max_length=500)]
    tags: Annotated[list[TagText], Field(min_length=1, max_length=20)]
    attributes: Annotated[list[TagText], Field(max_length=20)]
    objects: Annotated[list[TagText], Field(max_length=20)]
    confidence: Annotated[float, Field(ge=0, le=1)]

    @field_validator("subject", "subject_code", "category", mode="before")
    @classmethod
    def normalize_taxonomy_text(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("tags", "attributes", "objects", mode="before")
    @classmethod
    def normalize_collections(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        normalized: list[Any] = []
        seen: set[str] = set()
        for item in value:
            clean = item.strip().lower() if isinstance(item, str) else item
            key = clean if isinstance(clean, str) else repr(clean)
            if key not in seen:
                seen.add(key)
                normalized.append(clean)
        return normalized

    @model_validator(mode="after")
    def validate_taxonomy(self) -> "VisionMetadata":
        entry = VISION_TAXONOMY.get(self.subject_code)
        if entry is None:
            raise ValueError("subject_code is not in the approved vision taxonomy")
        if self.subject != entry.subject or self.category != entry.category:
            raise ValueError(
                "subject and category must match the approved taxonomy entry"
            )
        return self


class ImageMetadataResponse(VisionMetadata):
    model_config = ConfigDict(from_attributes=True, extra="forbid", strict=True)

    id: UUID
    image_id: UUID
    is_low_confidence: bool
    metadata_status: Literal["trusted", "flagged"]
    vision_provider: str
    vision_model: str
    schema_version: str
    created_at: datetime
    updated_at: datetime


class AnalyzeImageResponse(BaseModel):
    image_id: UUID
    processing_status: Literal["processed"]
    reused: bool
    metadata: ImageMetadataResponse
