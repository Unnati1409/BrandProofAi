from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import get_current_user
from app.db.session import EnforcedUnitOfWorkSession, get_db
from app.models.profile import Profile
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.auth import (
    UserProfileResponse,
    WorkspaceMembershipInfo,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/me", response_model=UserProfileResponse)
def get_me(
    current_user: Profile = Depends(get_current_user),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
):
    """
    Returns the authenticated profile and associated workspace memberships.
    Caller identity is cryptographically verified from the genuine Supabase JWT.
    """
    memberships = db.execute(
        select(WorkspaceMember, Workspace)
        .join(Workspace, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == current_user.id)
    ).all()

    workspaces_info = [
        WorkspaceMembershipInfo(
            workspace_id=str(ws.id),
            workspace_name=ws.name,
            workspace_slug=ws.slug,
            roles=member.roles or [],
        )
        for member, ws in memberships
    ]

    return UserProfileResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        avatar_url=current_user.avatar_url,
        created_at=current_user.created_at,
        workspaces=workspaces_info,
    )


@router.post("/register", status_code=status.HTTP_410_GONE)
def register_deprecated():
    """
    Direct application password registration is disabled.
    User registration is managed exclusively by Supabase Auth (e.g. supabase.auth.signUp()).
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Direct application-level registration is deprecated. Use Supabase Auth client (supabase.auth.signUp()).",
    )


@router.post("/login", status_code=status.HTTP_410_GONE)
def login_deprecated():
    """
    Direct application password login is disabled.
    Authentication is managed exclusively by Supabase Auth (e.g. supabase.auth.signInWithPassword()).
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Direct application-level login is deprecated. Use Supabase Auth client (supabase.auth.signInWithPassword()).",
    )
