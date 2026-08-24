from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ProcessingStatusValue = Literal[
    "uploaded",
    "queued",
    "processing",
    "processed",
    "failed",
]


class ImageAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    storage_key: str
    mime_type: str
    byte_size: int
    sha256: str
    processing_status: ProcessingStatusValue
    created_at: datetime
    updated_at: datetime
