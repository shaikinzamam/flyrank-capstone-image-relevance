import os
from uuid import UUID

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.evaluation import EvaluationRun
from app.repositories.evaluations import EvaluationRepository
from app.services.evaluation import EvaluationService

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_POSTGRES_PGVECTOR") != "1",
    reason="requires an explicitly enabled migrated PostgreSQL database",
)


def test_postgresql_persists_full_evaluation_report() -> None:
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    dataset_path = get_settings().evaluation_dataset_path
    run_id: UUID | None = None
    try:
        with Session(engine) as session:
            result = EvaluationService(
                EvaluationRepository(session), dataset_path
            ).run()
            run_id = result.run_id
            persisted = session.get(EvaluationRun, run_id)

        assert persisted is not None
        assert persisted.dataset_version == "evaluation-v1"
        assert persisted.config_version == "phase8-v1"
        assert persisted.top1_precision == 1.0
        assert persisted.unsafe_acceptances == 0
        assert len(persisted.report_json["examples"]) == 10
        assert persisted.report_json["examples"][0]["candidates"][0][
            "reason_code"
        ] == "SUBJECT_MISMATCH"
    finally:
        if run_id is not None:
            with Session(engine) as session:
                session.execute(delete(EvaluationRun).where(EvaluationRun.id == run_id))
                session.commit()
        engine.dispose()
