from app.api.routes.auth import router as auth_router
from app.api.routes.approvals import router as approvals_router
from app.api.routes.copilot import router as copilot_router
from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.knowledge import router as knowledge_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(approvals_router)
api_router.include_router(health_router)
api_router.include_router(knowledge_router)
api_router.include_router(copilot_router)
