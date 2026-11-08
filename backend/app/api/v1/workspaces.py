import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select, text

from app.api.deps import get_current_member, get_current_user, require_role
from app.core.audit import record_audit
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.rate_limit import rate_limit
from app.db.session import EnforcedUnitOfWorkSession, get_db
from app.models.profile import Profile
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import (
    MemberInviteRequest,
    MemberRoleUpdateRequest,
    WorkspaceCreateRequest,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceSettingsUpdate,
)

router = APIRouter(prefix="/workspaces", tags=["Workspaces & Membership"])

VALID_ROLES = {"admin", "brand_owner", "manager", "reviewer", "creator"}


def slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", slug)


@router.get("", response_model=list[WorkspaceResponse])
def list_user_workspaces(
    current_user: Profile = Depends(get_current_user),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
):
    """Lists all workspaces in which the authenticated user holds membership."""
    workspaces = (
        db.execute(
            select(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == current_user.id)
            .order_by(Workspace.created_at.desc())
        )
        .scalars()
        .all()
    )

    return [
        WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            created_by=ws.created_by,
            ai_enabled=ws.ai_enabled,
            ai_enabled_at=ws.ai_enabled_at,
            retention_days=ws.retention_days,
            created_at=ws.created_at,
        )
        for ws in workspaces
    ]


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreateRequest,
    current_user: Profile = Depends(get_current_user),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
):
    """
    Creates a new workspace. The creating user is automatically assigned the Admin role.
    """
    slug = payload.slug or slugify(payload.name)

    # Check slug uniqueness
    existing_ws = db.execute(select(Workspace).where(Workspace.slug == slug)).scalar_one_or_none()
    if existing_ws:
        raise ConflictError(
            f"Workspace with slug '{slug}' already exists. Please choose a different name."
        )

    new_workspace = Workspace(
        name=payload.name.strip(),
        slug=slug,
        created_by=current_user.id,
        ai_enabled=False,
        retention_days=90,
    )
    db.add(new_workspace)
    db.flush()

    # Automatically add creator as Admin
    admin_member = WorkspaceMember(
        workspace_id=new_workspace.id,
        user_id=current_user.id,
        roles=["admin"],
    )
    db.add(admin_member)
    db.flush()

    # Record Audit Event via hardened RPC
    record_audit(
        db=db,
        workspace_id=new_workspace.id,
        event_type="workspace.created",
        target_type="workspace",
        target_id=new_workspace.id,
        details={"name": new_workspace.name, "slug": new_workspace.slug},
    )

    db.refresh(new_workspace)

    return WorkspaceResponse(
        id=new_workspace.id,
        name=new_workspace.name,
        slug=new_workspace.slug,
        created_by=new_workspace.created_by,
        ai_enabled=new_workspace.ai_enabled,
        ai_enabled_at=new_workspace.ai_enabled_at,
        retention_days=new_workspace.retention_days,
        created_at=new_workspace.created_at,
    )


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace_details(
    workspace_id: str,
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
):
    """Returns workspace metadata. Caller must be an active workspace member."""
    ws = db.execute(select(Workspace).where(Workspace.id == workspace_id)).scalar_one_or_none()
    if not ws:
        raise NotFoundError("Workspace", workspace_id)

    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        created_by=ws.created_by,
        ai_enabled=ws.ai_enabled,
        ai_enabled_at=ws.ai_enabled_at,
        retention_days=ws.retention_days,
        created_at=ws.created_at,
    )


@router.patch("/{workspace_id}/settings", response_model=WorkspaceResponse)
def update_workspace_settings(
    workspace_id: str,
    payload: WorkspaceSettingsUpdate,
    member: WorkspaceMember = Depends(require_role(["admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
):
    """
    Updates workspace configuration. Restricted to Admins.
    Enabling AI requires explicit acknowledgment of the external AI disclosure.
    """
    ws = db.execute(select(Workspace).where(Workspace.id == workspace_id)).scalar_one_or_none()
    if not ws:
        raise NotFoundError("Workspace", workspace_id)

    if payload.name is not None:
        ws.name = payload.name.strip()

    if payload.retention_days is not None:
        ws.retention_days = payload.retention_days

    if payload.ai_enabled is not None:
        if payload.ai_enabled and not ws.ai_enabled:
            # Enforce external AI disclosure agreement before enabling
            if not payload.ai_disclosure_acknowledged:
                raise ValidationError(
                    "Enabling AI requires acknowledging the Google Gemini external AI disclosure."
                )
            ws.ai_enabled = True
            ws.ai_enabled_at = datetime.now(timezone.utc)
            ws.ai_enabled_by = member.user_id
        elif not payload.ai_enabled:
            ws.ai_enabled = False

    # Record Audit Event via hardened RPC
    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="settings.updated",
        target_type="workspace",
        target_id=workspace_id,
        details={
            "ai_enabled": ws.ai_enabled,
            "retention_days": ws.retention_days,
        },
    )

    db.flush()
    db.refresh(ws)

    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        created_by=ws.created_by,
        ai_enabled=ws.ai_enabled,
        ai_enabled_at=ws.ai_enabled_at,
        retention_days=ws.retention_days,
        created_at=ws.created_at,
    )


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(
    workspace_id: str,
    member: WorkspaceMember = Depends(require_role(["admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
):
    """Permanently deletes a workspace and all associated resources. Admin only."""
    ws = db.execute(select(Workspace).where(Workspace.id == workspace_id)).scalar_one_or_none()
    if not ws:
        raise NotFoundError("Workspace", workspace_id)

    db.delete(ws)
    db.flush()
    return None


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
def list_workspace_members(
    workspace_id: str,
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
):
    """Lists all members of the workspace and their assigned roles."""
    members = db.execute(
        select(WorkspaceMember, Profile)
        .join(Profile, WorkspaceMember.user_id == Profile.id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at.asc())
    ).all()

    return [
        WorkspaceMemberResponse(
            id=m.id,
            workspace_id=m.workspace_id,
            user_id=p.id,
            email=p.email,
            full_name=p.full_name,
            roles=m.roles or [],
            created_at=m.created_at,
        )
        for m, p in members
    ]


@router.post(
    "/{workspace_id}/members/invite",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            rate_limit(
                max_requests=10,
                window_seconds=60,
                scope="workspace",
                endpoint_name="member_invites",
            )
        )
    ],
)
def invite_member(
    workspace_id: str,
    payload: MemberInviteRequest,
    admin_member: WorkspaceMember = Depends(require_role(["admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
):
    """Invites a user to the workspace with specified roles. Restricted to Admins."""
    email_clean = payload.email.strip().lower()

    # Validate roles
    normalized_roles = [r.strip().lower() for r in payload.roles]
    invalid_roles = set(normalized_roles) - VALID_ROLES
    if invalid_roles:
        raise ValidationError(
            f"Invalid role(s) specified: {list(invalid_roles)}. Allowed roles: {list(VALID_ROLES)}"
        )

    # Resolve or create placeholder profile for invitee using security definer RPC
    bind = getattr(db, "bind", None)
    if bind and not str(bind.url).startswith("sqlite"):
        row = db.execute(
            text(
                "SELECT profile_id, profile_email, profile_name FROM public.lookup_or_create_profile(:email, :name)"
            ),
            {"email": email_clean, "name": email_clean.split("@")[0].replace(".", " ").title()},
        ).first()
        target_user_id = str(row[0])
        target_email = row[1]
        target_name = row[2]
    else:
        profile = db.execute(
            select(Profile).where(Profile.email == email_clean)
        ).scalar_one_or_none()
        if not profile:
            profile = Profile(
                email=email_clean,
                full_name=email_clean.split("@")[0].replace(".", " ").title(),
            )
            db.add(profile)
            db.flush()
        target_user_id = profile.id
        target_email = profile.email
        target_name = profile.full_name

    # Check if user is already a member
    existing_membership = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == target_user_id,
        )
    ).scalar_one_or_none()

    if existing_membership:
        raise ConflictError(f"User '{email_clean}' is already a member of this workspace.")

    new_member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=target_user_id,
        roles=normalized_roles,
        invited_by=admin_member.user_id,
    )
    db.add(new_member)

    # Record Audit Event via hardened RPC
    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="member.invited",
        target_type="workspace_member",
        target_id=target_user_id,
        details={"invited_email": email_clean, "roles": normalized_roles},
    )

    db.flush()
    db.refresh(new_member)

    return WorkspaceMemberResponse(
        id=new_member.id,
        workspace_id=workspace_id,
        user_id=target_user_id,
        email=target_email,
        full_name=target_name,
        roles=new_member.roles,
        created_at=new_member.created_at,
    )


@router.patch("/{workspace_id}/members/{user_id}", response_model=WorkspaceMemberResponse)
def update_member_roles(
    workspace_id: str,
    user_id: str,
    payload: MemberRoleUpdateRequest,
    admin_member: WorkspaceMember = Depends(require_role(["admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
):
    """Updates assigned roles for a workspace member. Restricted to Admins."""
    normalized_roles = [r.strip().lower() for r in payload.roles]
    invalid_roles = set(normalized_roles) - VALID_ROLES
    if invalid_roles:
        raise ValidationError(
            f"Invalid role(s): {list(invalid_roles)}. Allowed roles: {list(VALID_ROLES)}"
        )

    target_member = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    ).scalar_one_or_none()

    if not target_member:
        raise NotFoundError("Workspace member", user_id)

    old_roles = target_member.roles
    target_member.roles = normalized_roles

    # Record Audit Event via hardened RPC
    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="member.role_changed",
        target_type="workspace_member",
        target_id=user_id,
        details={"old_roles": old_roles, "new_roles": normalized_roles},
    )

    db.flush()
    db.refresh(target_member)

    profile = db.execute(select(Profile).where(Profile.id == user_id)).scalar_one()

    return WorkspaceMemberResponse(
        id=target_member.id,
        workspace_id=workspace_id,
        user_id=user_id,
        email=profile.email,
        full_name=profile.full_name,
        roles=target_member.roles,
        created_at=target_member.created_at,
    )


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    workspace_id: str,
    user_id: str,
    admin_member: WorkspaceMember = Depends(require_role(["admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
):
    """Removes a user from the workspace. Restricted to Admins."""
    target_member = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    ).scalar_one_or_none()

    if not target_member:
        raise NotFoundError("Workspace member", user_id)

    db.delete(target_member)

    # Record Audit Event via hardened RPC
    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="member.removed",
        target_type="workspace_member",
        target_id=user_id,
        details={},
    )

    db.flush()
    return None
