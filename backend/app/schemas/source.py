from datetime import datetime

from pydantic import BaseModel


class SourceDocumentResponse(BaseModel):
    """Metadata response for an imported guideline source document."""

    id: str
    workspace_id: str
    filename: str
    file_type: str
    storage_path: str
    file_size_bytes: int
    status: str
    error_message: str | None = None
    uploaded_by: str
    created_at: datetime
    is_approved: bool = (
        False  # Explicit invariant: Raw uploaded documents are unapproved candidate sources
    )


class SourceDocumentListResponse(BaseModel):
    items: list[SourceDocumentResponse]
    total: int


class SourceRetireResponse(BaseModel):
    id: str
    workspace_id: str
    status: str
    retired_at: datetime
    message: str = (
        "Source document successfully retired. It can no longer be referenced as approved evidence."
    )


class SourcePassageResponse(BaseModel):
    id: str
    workspace_id: str
    document_id: str
    heading: str | None = None
    clause_ref: str | None = None
    passage_text: str
    page_number: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    created_at: datetime


class SourceProcessResponse(BaseModel):
    document_id: str
    workspace_id: str
    status: str
    passages_count: int
    candidate_rules_extracted: int
    candidate_facts_extracted: int
    candidate_tones_extracted: int
    message: str = "Document ingested and passages extracted. Extracted rules and facts remain candidate until confirmed by Brand Owner."
