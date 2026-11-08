"""
BrandProof AI — Brand Knowledge Schemas.
Pydantic schemas for Rules, Approved Facts, and Tone Attributes.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class RuleResponse(BaseModel):
    id: str
    workspace_id: str
    rule_type: str
    severity: str
    status: str
    payload: dict[str, Any]
    explanation: str
    source_passage_id: str | None = None
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RuleCreateRequest(BaseModel):
    rule_type: str = Field(
        ..., pattern="^(banned_term|required_wording|terminology|tone_attribute)$"
    )
    severity: str = Field(default="medium", pattern="^(low|medium|high)$")
    payload: dict[str, Any]
    explanation: str = Field(..., min_length=2)
    source_passage_id: str | None = None


class RuleUpdateRequest(BaseModel):
    status: str | None = Field(default=None, pattern="^(candidate|confirmed|rejected|retired)$")
    severity: str | None = Field(default=None, pattern="^(low|medium|high)$")
    payload: dict[str, Any] | None = None
    explanation: str | None = None


class FactResponse(BaseModel):
    id: str
    workspace_id: str
    statement: str
    source_reference: str
    owner: str
    expiry_date: date | None = None
    status: str
    version: int
    source_passage_id: str | None = None
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class FactCreateRequest(BaseModel):
    statement: str = Field(..., min_length=5)
    source_reference: str = Field(default="Brand Manual")
    owner: str = Field(default="Brand Team")
    expiry_date: date | None = None
    source_passage_id: str | None = None


class FactUpdateRequest(BaseModel):
    statement: str | None = None
    source_reference: str | None = None
    owner: str | None = None
    expiry_date: date | None = None
    status: str | None = Field(default=None, pattern="^(candidate|confirmed|rejected|retired)$")


class ToneResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str
    positive_examples: list[str]
    negative_examples: list[str]
    status: str
    created_at: datetime


class ToneCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=5)
    positive_examples: list[str] = Field(default_factory=list)
    negative_examples: list[str] = Field(default_factory=list)


class ToneUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    positive_examples: list[str] | None = None
    negative_examples: list[str] | None = None
    status: str | None = Field(default=None, pattern="^(candidate|confirmed|rejected|retired)$")
