from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workspace import ApiCredential, Workspace


class AuthRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active_credential(self, key_hash: str) -> ApiCredential | None:
        return self._session.scalar(
            select(ApiCredential).where(
                ApiCredential.key_hash == key_hash,
                ApiCredential.active.is_(True),
                ApiCredential.revoked_at.is_(None),
            )
        )

    def get_credential(self, key_hash: str) -> ApiCredential | None:
        """Return a credential by its globally unique hash, including revoked rows."""
        return self._session.scalar(
            select(ApiCredential).where(ApiCredential.key_hash == key_hash)
        )

    def get_workspace_credentials_by_name(
        self, workspace_id: UUID, name: str
    ) -> list[ApiCredential]:
        return list(
            self._session.scalars(
                select(ApiCredential).where(
                    ApiCredential.workspace_id == workspace_id,
                    ApiCredential.name == name,
                )
            )
        )

    def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        return self._session.get(Workspace, workspace_id)

    def get_workspace_by_name(self, name: str) -> Workspace | None:
        return self._session.scalar(select(Workspace).where(Workspace.name == name))

    def add(self, value: Workspace | ApiCredential) -> None:
        self._session.add(value)

    def commit(self) -> None:
        self._session.commit()

    def refresh(self, value: Workspace | ApiCredential) -> None:
        self._session.refresh(value)
