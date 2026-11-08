from fastapi import APIRouter

from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.content import router as content_router
from app.api.v1.health import router as health_router
from app.api.v1.rules import router as rules_router
from app.api.v1.sources import router as sources_router
from app.api.v1.workspaces import router as workspaces_router

api_v1_router = APIRouter(prefix="/api/v1")

# Mount API endpoints
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(workspaces_router)
api_v1_router.include_router(sources_router)
api_v1_router.include_router(rules_router)
api_v1_router.include_router(content_router)
api_v1_router.include_router(audit_router)
