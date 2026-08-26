from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import Embeddings, ImageRetrieval, Posts, ProcessingJobs, Recommendations
from app.api.routes.jobs import job_response
from app.schemas.embedding import EmbeddingResponse
from app.schemas.processing_job import CreateEmbeddingJobRequest, ProcessingJobResponse
from app.schemas.post import CreatePostRequest, PostResponse
from app.schemas.retrieval import ImageCandidatesResponse
from app.schemas.recommendation import RecommendationResponse
from app.services.processing_jobs import IdempotencyConflictError, ProcessingPostNotFoundError
from app.services.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingPersistenceError,
    EmbeddingProviderFailureError,
    EmbeddingValidationError,
)
from app.services.posts import PostNotFoundError
from app.services.image_retrieval import (
    IncompatibleEmbeddingError,
    InvalidSimilarityError,
    MissingPostEmbeddingError,
)

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post(
    "/{post_id}/recommendations", response_model=RecommendationResponse
)
def create_recommendation(
    post_id: UUID,
    service: Recommendations,
    top_k: int = Query(default=5, ge=1, le=20),
) -> RecommendationResponse:
    try:
        return service.create(post_id, top_k=top_k)
    except PostNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (MissingPostEmbeddingError, IncompatibleEmbeddingError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidSimilarityError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/{post_id}/image-candidates", response_model=ImageCandidatesResponse
)
def get_image_candidates(
    post_id: UUID,
    service: ImageRetrieval,
    top_k: int = Query(default=5, ge=1, le=20),
) -> ImageCandidatesResponse:
    try:
        result = service.retrieve(post_id, top_k=top_k)
    except PostNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (MissingPostEmbeddingError, IncompatibleEmbeddingError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidSimilarityError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ImageCandidatesResponse(
        post_id=result.post_id,
        embedding_model=result.embedding_model,
        embedding_version=result.embedding_version,
        dimensions=result.dimensions,
        candidates=result.candidates,
    )


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


@router.post(
    "/{post_id}/embedding",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_post_embedding(
    post_id: UUID, request: CreateEmbeddingJobRequest, service: ProcessingJobs
) -> ProcessingJobResponse:
    try:
        job, reused = service.create_post_embedding(
            post_id, idempotency_key=request.idempotency_key
        )
    except ProcessingPostNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return job_response(job, reused=reused)


@router.post(
    "/{post_id}/embedding/debug-sync",
    response_model=EmbeddingResponse,
    deprecated=True,
)
def create_post_embedding_debug(
    post_id: UUID, service: Embeddings
) -> EmbeddingResponse:
    """Development-only synchronous diagnostic; production clients enqueue jobs."""
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
