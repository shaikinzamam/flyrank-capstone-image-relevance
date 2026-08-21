from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.services.readiness import DatabaseReadinessService

DatabaseSession = Annotated[Session, Depends(get_db_session)]


def get_readiness_service(session: DatabaseSession) -> DatabaseReadinessService:
    return DatabaseReadinessService(session)


ReadinessService = Annotated[
    DatabaseReadinessService,
    Depends(get_readiness_service),
]

