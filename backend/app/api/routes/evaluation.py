from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.dependencies import Evaluations
from app.schemas.evaluation import EvaluationRunResponse
from app.services.evaluation import EvaluationDatasetError, EvaluationRunNotFoundError

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/run", response_model=EvaluationRunResponse)
def run_evaluation(service: Evaluations) -> EvaluationRunResponse:
    try:
        return service.run()
    except EvaluationDatasetError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/latest", response_model=EvaluationRunResponse)
def get_latest_evaluation(service: Evaluations) -> EvaluationRunResponse:
    try:
        return service.latest()
    except EvaluationRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}", response_model=EvaluationRunResponse)
def get_evaluation(run_id: UUID, service: Evaluations) -> EvaluationRunResponse:
    try:
        return service.get(run_id)
    except EvaluationRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
