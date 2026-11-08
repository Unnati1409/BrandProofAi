from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.profile import Profile
from app.models.workspace import WorkspaceMember

router = APIRouter(prefix="/workspaces/{workspace_id}/audit-logs", tags=["Audit Trail"])


class AuditLogResponse(BaseModel):
    id: int
    workspace_id: str
    actor_id: str | None = None
    actor_email: str | None = None
    event_type: str
    target_type: str
    target_id: str
    details: dict
    ip_address: str | None = None
    created_at: datetime


@router.get("", response_model=list[AuditLogResponse])
def get_audit_logs(
    workspace_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    event_type: str | None = None,
    member: WorkspaceMember = Depends(require_role(["admin", "manager"])),
    db: Session = Depends(get_db),
):
    """
    Retrieves the tamper-evident append-only audit trail for the active workspace.
    Restricted strictly to Admins and Managers.
    """
    query = (
        select(AuditLog, Profile.email)
        .outerjoin(Profile, AuditLog.actor_id == Profile.id)
        .where(AuditLog.workspace_id == workspace_id)
    )

    if event_type:
        query = query.where(AuditLog.event_type == event_type)

    query = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)

    results = db.execute(query).all()

    return [
        AuditLogResponse(
            id=log.id,
            workspace_id=log.workspace_id,
            actor_id=log.actor_id,
            actor_email=actor_email,
            event_type=log.event_type,
            target_type=log.target_type,
            target_id=log.target_id,
            details=log.details or {},
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log, actor_email in results
    ]
