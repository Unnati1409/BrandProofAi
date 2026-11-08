from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user_id: str
    email: str
    full_name: str


class WorkspaceMembershipInfo(BaseModel):
    workspace_id: str
    workspace_name: str
    workspace_slug: str
    roles: list[str]


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    avatar_url: str | None = None
    created_at: datetime
    workspaces: list[WorkspaceMembershipInfo]
