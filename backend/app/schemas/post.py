from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PostBody = Annotated[RequiredText, StringConstraints(max_length=50_000)]
OptionalSubject = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
OptionalCategory = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]
RequiredTag = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]


class CreatePostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[RequiredText, StringConstraints(max_length=300)]
    body: PostBody
    expected_subject: OptionalSubject | None = None
    expected_category: OptionalCategory | None = None
    required_tags: list[RequiredTag] = Field(default_factory=list, max_length=20)


class PostResponse(CreatePostRequest):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_at: datetime
    updated_at: datetime
