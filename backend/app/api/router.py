from fastapi import APIRouter

from app.api.routes.images import router as images_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(images_router)
api_router.include_router(jobs_router)
