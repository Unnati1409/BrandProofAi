import json
from typing import Any

from sqlalchemy import text

from app.db.session import EnforcedUnitOfWorkSession
from app.models.audit import AuditLog


def record_audit(
    db: EnforcedUnitOfWorkSession,
    workspace_id: str,
    event_type: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Records an audit event using the hardened PostgreSQL procedure public.record_audit_event.
    Derives actor identity strictly from auth.uid() within the transaction context.
    """
    bind = getattr(db, "bind", None)
    if bind and not str(bind.url).startswith("sqlite"):
        details_json = json.dumps(details or {})
        db.execute(
            text(
                "SELECT public.record_audit_event("
                "  CAST(:workspace_id AS UUID), :event_type, :target_type, :target_id, CAST(:details AS JSONB), :ip_address"
                ");"
            ),
            {
                "workspace_id": str(workspace_id),
                "event_type": str(event_type),
                "target_type": str(target_type),
                "target_id": str(target_id),
                "details": details_json,
                "ip_address": ip_address,
            },
        )
    else:
        audit_entry = AuditLog(
            workspace_id=workspace_id,
            actor_id=None,
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            ip_address=ip_address,
        )
        db.add(audit_entry)
