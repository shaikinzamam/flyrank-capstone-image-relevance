from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class EmbeddingResponse(BaseModel):
    id: UUID
    resource_id: UUID
    resource_type: Literal["image", "post"]
    embedding_model: str
    embedding_version: str
    dimensions: int
    source_text_hash: str
    reused: bool
    is_low_confidence: bool | None = None
    created_at: datetime
    updated_at: datetime
