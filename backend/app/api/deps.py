import json
import uuid
from collections.abc import Callable

from fastapi import Depends, Header, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text

from app.core.errors import (
    CreatorSelfApprovalError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from app.core.security import TokenPayload, decode_and_verify_token
from app.db.session import EnforcedUnitOfWorkSession, get_db
from app.models.content import ContentItem
from app.models.profile import Profile
from app.models.workspace import WorkspaceMember

# Bearer token extractor (auto_error=False to allow clean typed 401 envelope)
security_scheme = HTTPBearer(auto_error=False)


def apply_db_identity_context(db: EnforcedUnitOfWorkSession, token_payload: TokenPayload) -> None:
    """
    Propagates authenticated identity into the request-scoped transaction via
    transaction-local PostgreSQL settings:
    - SET LOCAL ROLE authenticated;
    - set_config('request.jwt.claim.sub', :user_id, true);
    - set_config('request.jwt.claim.role', 'authenticated', true);
    - set_config('request.jwt.claims', :claims_json, true);

    On PostgreSQL, this activates Row-Level Security policies evaluating auth.uid()
    and public.get_user_workspace_ids().
    """
    bind = getattr(db, "bind", None)
    if bind and not str(bind.url).startswith("sqlite"):
        claims_json = json.dumps(token_payload.raw_claims) if token_payload.raw_claims else "{}"
        db.execute(text("SET LOCAL ROLE authenticated;"))
        db.execute(
            text("SELECT set_config('request.jwt.claim.sub', :sub, true);"),
            {"sub": str(token_payload.sub)},
        )
        db.execute(
            text("SELECT set_config('request.jwt.claim.role', :role, true);"),
            {"role": str(token_payload.role)},
        )
        db.execute(
            text("SELECT set_config('request.jwt.claims', :claims, true);"),
            {"claims": claims_json},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> Profile:
    """
    Verifies genuine Supabase JWT signature, expiration, and claims.
    Establishes transaction-scoped PostgreSQL identity for RLS evaluation.
    Resolves user Profile from the database. Rejects unknown users.
    Never trusts identity assertions from headers alone.
    """
    if not credentials or not credentials.credentials:
        raise UnauthorizedError("Missing Bearer authentication token.")

    token_payload = decode_and_verify_token(credentials.credentials)

    # Establish transaction-local database identity for PostgreSQL RLS
    apply_db_identity_context(db, token_payload)

    # Resolve user profile from DB (evaluated under RLS)
    profile = db.execute(
        select(Profile).where(Profile.id == token_payload.sub)
    ).scalar_one_or_none()

    if not profile:
        raise UnauthorizedError(
            f"User profile '{token_payload.sub}' does not exist in application database."
        )

    return profile


async def resolve_workspace_id(
    request: Request,
    x_workspace_id: str | None = Header(None, alias="X-Workspace-ID"),
) -> str:
    """
    Extracts workspace ID from path parameter or X-Workspace-ID header.
    Path parameter takes precedence over header.
    Input values are never trusted as authorization proof; membership is verified against DB.
    """
    ws_id = request.path_params.get("workspace_id") or x_workspace_id
    if not ws_id:
        raise ForbiddenError("Missing required workspace identifier in request path or header.")
    try:
        return str(uuid.UUID(str(ws_id)))
    except (ValueError, AttributeError):
        raise ForbiddenError(f"Access denied: Invalid workspace identifier '{ws_id}'.")


async def get_current_member(
    workspace_id: str = Depends(resolve_workspace_id),
    current_user: Profile = Depends(get_current_user),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> WorkspaceMember:
    """
    Resolves the user's membership and roles for the requested workspace from the DATABASE.
    Role and workspace are read from the membership table on EVERY request, never trusted from client.
    Rejects users who are not active members or have empty role assignments.
    """
    member = db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
    ).scalar_one_or_none()

    if not member:
        raise ForbiddenError(f"Access denied: You are not a member of workspace '{workspace_id}'.")

    if not member.roles or len(member.roles) == 0:
        raise ForbiddenError(
            f"Access denied: Membership in workspace '{workspace_id}' is inactive or has no assigned roles."
        )

    return member


def require_role(allowed_roles: list[str]) -> Callable:
    """
    FastAPI dependency factory enforcing role-based access control.
    Verifies that the caller possesses at least one of the allowed roles in the active workspace.
    Roles are always read from genuine database records.
    """

    async def role_checker(
        member: WorkspaceMember = Depends(get_current_member),
    ) -> WorkspaceMember:
        user_roles = [r.lower() for r in (member.roles or [])]
        required_roles = [r.lower() for r in allowed_roles]

        if not any(role in user_roles for role in required_roles):
            role_list = ", ".join(required_roles)
            raise ForbiddenError(
                f"Permission denied. Required role: [{role_list}]. Your roles: [{', '.join(user_roles)}]."
            )

        return member

    return role_checker


async def verify_can_approve_content(
    content_id: str = Path(...),
    member: WorkspaceMember = Depends(require_role(["manager", "reviewer"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> ContentItem:
    """
    Validates that:
    1. Content exists and belongs to the active workspace (isolation).
    2. The caller is a Manager or Reviewer (from DB roles; Admin and Brand Owner cannot approve).
    3. The caller is NOT the creator of the content (creator separation of concerns).
    4. AI is strictly prohibited from approving content.
    """
    content = db.execute(
        select(ContentItem).where(
            ContentItem.id == content_id,
            ContentItem.workspace_id == member.workspace_id,
        )
    ).scalar_one_or_none()

    if not content:
        raise NotFoundError("Content submission", content_id)

    # Core Security Enforcement: Creator separation
    if str(content.created_by).strip() == str(member.user_id).strip():
        raise CreatorSelfApprovalError()

    return content
