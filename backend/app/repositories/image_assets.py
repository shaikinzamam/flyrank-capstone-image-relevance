from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.image_asset import ImageAsset


class ImageAssetRepository:
    def __init__(self, session: Session, workspace_id: UUID | None = None) -> None:
        self._session = session
        self.workspace_id = workspace_id

    def _scope(self):
        return () if self.workspace_id is None else (ImageAsset.workspace_id == self.workspace_id,)

    def get(self, image_id: UUID) -> ImageAsset | None:
        return self._session.scalar(
            select(ImageAsset).where(ImageAsset.id == image_id, *self._scope())
        )

    def get_by_sha256(self, sha256: str) -> ImageAsset | None:
        return self._session.scalar(
            select(ImageAsset).where(ImageAsset.sha256 == sha256, *self._scope())
        )

    def get_many(self, image_ids: Sequence[UUID]) -> list[ImageAsset]:
        return list(
            self._session.scalars(
                select(ImageAsset).where(ImageAsset.id.in_(image_ids), *self._scope())
            )
        )

    def list(self, *, offset: int, limit: int) -> list[ImageAsset]:
        return list(
            self._session.scalars(
                select(ImageAsset)
                .where(*self._scope())
                .order_by(ImageAsset.created_at.desc(), ImageAsset.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )

    def add(self, asset: ImageAsset) -> None:
        if self.workspace_id is not None:
            asset.workspace_id = self.workspace_id
        self._session.add(asset)

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def refresh(self, asset: ImageAsset) -> None:
        self._session.refresh(asset)
