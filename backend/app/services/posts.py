from uuid import UUID

from app.models.post import Post
from app.repositories.posts import PostRepository
from app.schemas.post import CreatePostRequest


class PostNotFoundError(Exception):
    pass


class PostService:
    def __init__(self, repository: PostRepository) -> None:
        self._posts = repository

    def create(self, request: CreatePostRequest) -> Post:
        post = Post(**request.model_dump())
        self._posts.add(post)
        self._posts.commit()
        self._posts.refresh(post)
        return post

    def get(self, post_id: UUID) -> Post:
        post = self._posts.get(post_id)
        if post is None:
            raise PostNotFoundError("Post not found")
        return post

    def list(self, *, offset: int, limit: int) -> list[Post]:
        return self._posts.list(offset=offset, limit=limit)
