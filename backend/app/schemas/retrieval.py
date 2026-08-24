from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field


class ImageCandidateResponse(BaseModel):
    rank: Annotated[int, Field(ge=1)]
    image_id: UUID
    similarity_score: Annotated[float, Field(ge=-1, le=1)]
    subject: str
    category: str
    caption: str
    tags: list[str]
    vision_confidence: Annotated[float, Field(ge=0, le=1)]
    is_low_confidence: bool


class ImageCandidatesResponse(BaseModel):
    post_id: UUID
    embedding_model: str
    embedding_version: str
    dimensions: int
    candidates: list[ImageCandidateResponse]
