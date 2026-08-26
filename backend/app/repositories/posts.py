from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.post import Post


class PostRepository:
    def __init__(self, session: Session, workspace_id: UUID | None = None) -> None:
        self._session = session
        self.workspace_id = workspace_id

    def _scope(self):
        return () if self.workspace_id is None else (Post.workspace_id == self.workspace_id,)

    def get(self, post_id: UUID) -> Post | None:
        return self._session.scalar(
            select(Post).where(Post.id == post_id, *self._scope())
        )

    def list(self, *, offset: int, limit: int) -> list[Post]:
        return list(
            self._session.scalars(
                select(Post)
                .where(*self._scope())
                .order_by(Post.created_at.desc(), Post.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )

    def add(self, post: Post) -> None:
        if self.workspace_id is not None:
            post.workspace_id = self.workspace_id
        self._session.add(post)

    def commit(self) -> None:
        self._session.commit()

    def refresh(self, post: Post) -> None:
        self._session.refresh(post)
