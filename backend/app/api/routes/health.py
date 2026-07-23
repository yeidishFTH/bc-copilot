from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.health import database_is_ready
from app.db.session import get_db_session
from app.models.health import DatabaseHealthResponse, HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    settings = get_settings()

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        version="0.2.1",
    )


@router.get("/database", response_model=DatabaseHealthResponse)
async def database_health_check(
    session: AsyncSession = Depends(get_db_session),
) -> DatabaseHealthResponse:
    try:
        ready = await database_is_ready(session)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    if not ready:
        raise HTTPException(status_code=503, detail="Database unavailable")

    return DatabaseHealthResponse(status="ok", database="postgresql")
