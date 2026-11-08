from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str | None = Field(None, min_length=2, max_length=50)


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str
    created_by: str
    ai_enabled: bool
    ai_enabled_at: datetime | None = None
    retention_days: int
    created_at: datetime


class WorkspaceSettingsUpdate(BaseModel):
    name: str | None = None
    ai_enabled: bool | None = None
    retention_days: int | None = Field(None, ge=1, le=3650)
    ai_disclosure_acknowledged: bool | None = None


class MemberInviteRequest(BaseModel):
    email: str
    roles: list[str] = Field(..., min_length=1)  # admin, brand_owner, manager, reviewer, creator


class MemberRoleUpdateRequest(BaseModel):
    roles: list[str] = Field(..., min_length=1)


class WorkspaceMemberResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    email: str
    full_name: str
    roles: list[str]
    created_at: datetime
