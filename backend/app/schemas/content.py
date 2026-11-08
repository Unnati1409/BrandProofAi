"""
BrandProof AI — Content, Versioning, Review & Approval Schemas.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ContentCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    file_type: str = Field(default="pasted_text")  # pasted_text, docx, pdf
    raw_text: str = Field(..., min_length=1)
    original_filename: str | None = None


class ContentVersionResponse(BaseModel):
    id: str
    content_id: str
    workspace_id: str
    version_number: int
    raw_text: str
    normalized_text: str
    parsed_metadata: dict[str, Any]
    created_by: str
    created_at: datetime


class ContentVersionCreateRequest(BaseModel):
    raw_text: str = Field(..., min_length=1)


class ContentResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    file_type: str
    original_filename: str | None = None
    created_by: str
    state: str  # draft, checked, in_review, changes_requested, approved, archived
    current_version: int
    created_at: datetime
    updated_at: datetime


class FindingResponse(BaseModel):
    id: str
    workspace_id: str
    run_id: str
    content_version_id: str
    category: str  # terminology, factual_claim, tone, compliance, accessibility
    severity: str  # high, medium, low
    basis_label: str  # supported, contradicted, unsupported, needs_human_review
    start_offset: int
    end_offset: int
    paragraph_index: int | None = None
    page_number: int | None = None
    rule_id: str | None = None
    fact_id: str | None = None
    quoted_submitted_content: str
    quoted_approved_source: str
    source_reference: str
    source_document_name: str | None = None
    explanation: str
    verdict: str | None = None
    confidence_indicator: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    accessibility_result: str | None = None
    not_checked_reason: str | None = None
    decision: str = "open"  # open, resolved, dismissed
    decision_reason: str | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    created_at: datetime


class FindingDecisionRequest(BaseModel):
    decision: str = Field(
        ...,
        pattern="^(applied_suggestion|manual_edit|dismissed|ask_reviewer|resolved)$",
    )
    decision_reason: str = Field(..., min_length=2)


class ContentCommentRequest(BaseModel):
    comment_text: str = Field(..., min_length=1)
    content_version_id: str
    finding_id: str | None = None


class ContentCommentResponse(BaseModel):
    id: str
    workspace_id: str
    content_version_id: str
    finding_id: str | None = None
    author_id: str
    comment_text: str
    created_at: datetime


class ContentDetailResponse(BaseModel):
    item: ContentResponse
    versions: list[ContentVersionResponse]
    latest_findings: list[FindingResponse]
    comments: list[ContentCommentResponse]


class ContentApprovalRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|changes_requested)$")
    notes: str | None = None


class ContentApprovalResponse(BaseModel):
    id: str
    content_id: str
    decision: str
    notes: str | None = None
    decided_by: str
    decided_at: datetime
    new_state: str


class ContentExportResponse(BaseModel):
    content_id: str
    title: str
    version_number: int
    state: str
    content_text: str
    approval_metadata: dict[str, Any] | None = None
    export_timestamp: datetime
    audit_hash: str
