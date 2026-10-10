from fastapi import APIRouter
from app.api.templates import router as templates_router
from app.api.jobs import router as jobs_router
from app.api.certificates import router as certificates_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(templates_router)
api_router.include_router(jobs_router)
api_router.include_router(certificates_router)
