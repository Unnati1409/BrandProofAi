from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str
    timestamp: str


@router.get("/health", response_model=HealthResponse)
async def check_health() -> HealthResponse:
    """
    Health check endpoint for container orchestrators and deployment monitors.
    Returns current service status and UTC timestamp.
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        environment=settings.ENVIRONMENT,
        version=settings.APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
