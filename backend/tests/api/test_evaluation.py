from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.models.evaluation import EvaluationRun
from app.models.image_asset import ImageAsset
from app.models.image_metadata import AiCallLog
from app.models.post import Post
from tests.conftest import ImageApiContext


def test_evaluation_api_runs_persists_and_reads_full_report(
    image_api: ImageApiContext,
) -> None:
    missing_latest = image_api.client.get("/evaluation/latest")

    response = image_api.client.post("/evaluation/run")

    assert missing_latest.status_code == 404
    assert response.status_code == 200
    body = response.json()
    assert body["dataset_version"] == "evaluation-v1"
    assert body["config_version"] == "phase8-v1"
    assert body["total_examples"] == 10
    assert body["correct_top1"] == 3
    assert body["correct_no_confident_match"] == 7
    assert body["unsafe_acceptance_count"] == 0
    assert body["top1_precision"] == 1.0
    assert len(body["examples"]) == 10

    latest = image_api.client.get("/evaluation/latest")
    by_id = image_api.client.get(f"/evaluation/{body['run_id']}")
    missing = image_api.client.get(f"/evaluation/{uuid4()}")
    assert latest.status_code == 200 and latest.json() == body
    assert by_id.status_code == 200 and by_id.json() == body
    assert missing.status_code == 404

    with image_api.session_factory() as session:
        persisted = session.get(EvaluationRun, UUID(body["run_id"]))
        count = session.scalar(select(func.count()).select_from(EvaluationRun))
        corpus_counts = (
            session.scalar(select(func.count()).select_from(Post)),
            session.scalar(select(func.count()).select_from(ImageAsset)),
            session.scalar(select(func.count()).select_from(AiCallLog)),
        )
    assert count == 1
    assert persisted is not None
    assert persisted.report_json["examples"][0]["candidates"]
    assert persisted.report_json["minimum_similarity"] == 0.70
    assert corpus_counts == (0, 0, 0)
