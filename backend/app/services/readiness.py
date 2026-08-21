import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DatabaseReadinessService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def is_ready(self) -> bool:
        try:
            self._session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.exception("Database readiness check failed")
            return False
        return True

