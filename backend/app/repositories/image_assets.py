from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.image_asset import ImageAsset


class ImageAssetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, image_id: UUID) -> ImageAsset | None:
        return self._session.get(ImageAsset, image_id)

    def get_by_sha256(self, sha256: str) -> ImageAsset | None:
        return self._session.scalar(
            select(ImageAsset).where(ImageAsset.sha256 == sha256)
        )

    def list(self, *, offset: int, limit: int) -> list[ImageAsset]:
        return list(
            self._session.scalars(
                select(ImageAsset)
                .order_by(ImageAsset.created_at.desc(), ImageAsset.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )

    def add(self, asset: ImageAsset) -> None:
        self._session.add(asset)

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def refresh(self, asset: ImageAsset) -> None:
        self._session.refresh(asset)
