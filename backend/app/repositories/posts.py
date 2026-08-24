from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.post import Post


class PostRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, post_id: UUID) -> Post | None:
        return self._session.get(Post, post_id)

    def list(self, *, offset: int, limit: int) -> list[Post]:
        return list(
            self._session.scalars(
                select(Post)
                .order_by(Post.created_at.desc(), Post.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )

    def add(self, post: Post) -> None:
        self._session.add(post)

    def commit(self) -> None:
        self._session.commit()

    def refresh(self, post: Post) -> None:
        self._session.refresh(post)
