from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import Embeddings, Posts
from app.schemas.embedding import EmbeddingResponse
from app.schemas.post import CreatePostRequest, PostResponse
from app.services.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingPersistenceError,
    EmbeddingProviderFailureError,
    EmbeddingValidationError,
)
from app.services.posts import PostNotFoundError

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(request: CreatePostRequest, service: Posts) -> PostResponse:
    return PostResponse.model_validate(service.create(request))


@router.get("", response_model=list[PostResponse])
def list_posts(
    service: Posts,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[PostResponse]:
    return [
        PostResponse.model_validate(post)
        for post in service.list(offset=offset, limit=limit)
    ]


@router.get("/{post_id}", response_model=PostResponse)
def get_post(post_id: UUID, service: Posts) -> PostResponse:
    try:
        return PostResponse.model_validate(service.get(post_id))
    except PostNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{post_id}/embedding", response_model=EmbeddingResponse)
def create_post_embedding(post_id: UUID, service: Embeddings) -> EmbeddingResponse:
    try:
        embedding, reused = service.embed_post(post_id)
    except PostNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (EmbeddingProviderFailureError, EmbeddingPersistenceError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (EmbeddingValidationError, EmbeddingConfigurationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return EmbeddingResponse(
        id=embedding.id,
        resource_id=embedding.post_id,
        resource_type="post",
        embedding_model=embedding.embedding_model,
        embedding_version=embedding.embedding_version,
        dimensions=embedding.dimensions,
        source_text_hash=embedding.source_text_hash,
        reused=reused,
        created_at=embedding.created_at,
        updated_at=embedding.updated_at,
    )
