import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy import select

from app.api.deps import get_current_member, require_role
from app.core.audit import record_audit
from app.core.errors import NotFoundError
from app.core.rate_limit import rate_limit
from app.core.storage import (
    read_workspace_source_file,
    sanitize_filename,
    save_workspace_source_file,
    validate_guideline_file,
)
from app.db.session import EnforcedUnitOfWorkSession, get_db
from app.models.source import SourceDocument, SourcePassage
from app.models.workspace import WorkspaceMember
from app.schemas.source import (
    SourceDocumentListResponse,
    SourceDocumentResponse,
    SourcePassageResponse,
    SourceProcessResponse,
    SourceRetireResponse,
)
from app.services.extraction import extract_and_persist_candidates
from app.services.ingestion import ingest_document_passages

router = APIRouter(prefix="/workspaces/{workspace_id}/sources", tags=["Guideline Sources"])


@router.post(
    "/upload",
    response_model=SourceDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            rate_limit(
                max_requests=20, window_seconds=60, scope="user", endpoint_name="source_uploads"
            )
        )
    ],
)
async def upload_guideline_source(
    workspace_id: str,
    file: UploadFile = File(...),
    member: WorkspaceMember = Depends(require_role(["brand_owner", "admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> SourceDocumentResponse:
    """
    Uploads a brand guideline document (PDF or DOCX).
    Enforces Brand Owner / Admin authorization, genuine magic byte verification,
    size limits, and workspace-scoped storage.
    IMPORTANT: Uploaded sources remain UNAPPROVED until explicit Brand Owner confirmation.
    """
    raw_content = await file.read()
    filename = file.filename or "uploaded_guideline.pdf"

    # Validate file type via magic bytes and enforce size limits
    file_type = validate_guideline_file(filename=filename, content=raw_content)

    source_id = str(uuid.uuid4())
    clean_filename = sanitize_filename(filename)

    # Persist file bytes to private workspace-scoped storage
    storage_path = save_workspace_source_file(
        workspace_id=workspace_id,
        source_id=source_id,
        filename=clean_filename,
        content=raw_content,
    )

    # Record database entry with status 'uploaded' (unapproved)
    source_doc = SourceDocument(
        id=source_id,
        workspace_id=workspace_id,
        filename=clean_filename,
        file_type=file_type,
        storage_path=storage_path,
        file_size_bytes=len(raw_content),
        status="uploaded",
        uploaded_by=member.user_id,
    )
    db.add(source_doc)
    db.flush()

    # Record append-only audit event
    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="source.uploaded",
        target_type="source_document",
        target_id=source_id,
        details={
            "filename": clean_filename,
            "file_type": file_type,
            "file_size_bytes": len(raw_content),
            "storage_path": storage_path,
        },
    )
    db.flush()
    db.refresh(source_doc)

    return SourceDocumentResponse(
        id=source_doc.id,
        workspace_id=source_doc.workspace_id,
        filename=source_doc.filename,
        file_type=source_doc.file_type,
        storage_path=source_doc.storage_path,
        file_size_bytes=source_doc.file_size_bytes,
        status=source_doc.status,
        error_message=source_doc.error_message,
        uploaded_by=source_doc.uploaded_by,
        created_at=source_doc.created_at,
        is_approved=False,  # Unapproved until explicit confirmation
    )


@router.get("", response_model=SourceDocumentListResponse)
def list_guideline_sources(
    workspace_id: str,
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> SourceDocumentListResponse:
    """Lists all guideline sources belonging to the active workspace."""
    sources = (
        db.execute(
            select(SourceDocument)
            .where(SourceDocument.workspace_id == workspace_id)
            .order_by(SourceDocument.created_at.desc())
        )
        .scalars()
        .all()
    )

    items = [
        SourceDocumentResponse(
            id=s.id,
            workspace_id=s.workspace_id,
            filename=s.filename,
            file_type=s.file_type,
            storage_path=s.storage_path,
            file_size_bytes=s.file_size_bytes,
            status=s.status,
            error_message=s.error_message,
            uploaded_by=s.uploaded_by,
            created_at=s.created_at,
            is_approved=False,
        )
        for s in sources
    ]
    return SourceDocumentListResponse(items=items, total=len(items))


@router.get("/{source_id}", response_model=SourceDocumentResponse)
def get_guideline_source(
    workspace_id: str,
    source_id: str,
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> SourceDocumentResponse:
    """Retrieves metadata for a specific guideline source. Preserves workspace isolation."""
    source_doc = db.execute(
        select(SourceDocument).where(
            SourceDocument.id == source_id,
            SourceDocument.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()

    if not source_doc:
        raise NotFoundError("Guideline source", source_id)

    return SourceDocumentResponse(
        id=source_doc.id,
        workspace_id=source_doc.workspace_id,
        filename=source_doc.filename,
        file_type=source_doc.file_type,
        storage_path=source_doc.storage_path,
        file_size_bytes=source_doc.file_size_bytes,
        status=source_doc.status,
        error_message=source_doc.error_message,
        uploaded_by=source_doc.uploaded_by,
        created_at=source_doc.created_at,
        is_approved=False,
    )


@router.delete("/{source_id}", response_model=SourceRetireResponse)
def retire_guideline_source(
    workspace_id: str,
    source_id: str,
    member: WorkspaceMember = Depends(require_role(["brand_owner", "admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> SourceRetireResponse:
    """
    Retires a guideline source document (soft-deletion).
    Retired sources can no longer be referenced as approved evidence.
    Preserves audit history and compliance logs.
    """
    source_doc = db.execute(
        select(SourceDocument).where(
            SourceDocument.id == source_id,
            SourceDocument.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()

    if not source_doc:
        raise NotFoundError("Guideline source", source_id)

    prev_status = source_doc.status
    source_doc.status = "retired"
    now = datetime.now(timezone.utc)

    # Record retirement audit event
    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="source.retired",
        target_type="source_document",
        target_id=source_id,
        details={"filename": source_doc.filename, "previous_status": prev_status},
    )
    db.flush()

    return SourceRetireResponse(
        id=source_doc.id,
        workspace_id=source_doc.workspace_id,
        status="retired",
        retired_at=now,
    )


@router.post(
    "/{source_id}/process",
    response_model=SourceProcessResponse,
    status_code=status.HTTP_200_OK,
)
async def process_guideline_source(
    workspace_id: str,
    source_id: str,
    member: WorkspaceMember = Depends(require_role(["brand_owner", "admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> SourceProcessResponse:
    """
    Ingests and processes a guideline document.
    1. Extracts structured passages with page/paragraph references.
    2. Extracts candidate rules, facts, and tone attributes.
    3. Persists all extracted items as UNAPPROVED candidates for Brand Owner review.
    """
    source_doc = db.execute(
        select(SourceDocument).where(
            SourceDocument.id == source_id,
            SourceDocument.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()

    if not source_doc:
        raise NotFoundError("Guideline source", source_id)

    if source_doc.status == "retired":
        raise NotFoundError("Guideline source (cannot process retired document)", source_id)

    # Read binary bytes from isolated workspace storage
    file_bytes = read_workspace_source_file(source_doc.storage_path)

    # Ingest passages (persisted to source_passages)
    passages = ingest_document_passages(db=db, document=source_doc, file_bytes=file_bytes)

    # Extract candidate rules, facts, and tone attributes
    extracted_counts = await extract_and_persist_candidates(
        db=db,
        workspace_id=workspace_id,
        passages=passages,
    )

    # Audit the processing
    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="source.processed",
        target_type="source_document",
        target_id=source_id,
        details={
            "filename": source_doc.filename,
            "passages_count": len(passages),
            **extracted_counts,
        },
    )
    db.flush()

    return SourceProcessResponse(
        document_id=source_doc.id,
        workspace_id=source_doc.workspace_id,
        status=source_doc.status,
        passages_count=len(passages),
        candidate_rules_extracted=extracted_counts["candidate_rules"],
        candidate_facts_extracted=extracted_counts["candidate_facts"],
        candidate_tones_extracted=extracted_counts["candidate_tones"],
    )


@router.get("/{source_id}/passages", response_model=list[SourcePassageResponse])
def get_source_passages(
    workspace_id: str,
    source_id: str,
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> list[SourcePassageResponse]:
    """Retrieves extracted passages for a guideline document."""
    passages = (
        db.execute(
            select(SourcePassage)
            .where(
                SourcePassage.workspace_id == workspace_id,
                SourcePassage.document_id == source_id,
            )
            .order_by(
                SourcePassage.page_number.asc().nulls_first(), SourcePassage.start_offset.asc()
            )
        )
        .scalars()
        .all()
    )

    return [
        SourcePassageResponse(
            id=p.id,
            workspace_id=p.workspace_id,
            document_id=p.document_id,
            heading=p.heading,
            clause_ref=p.clause_ref,
            passage_text=p.passage_text,
            page_number=p.page_number,
            start_offset=p.start_offset,
            end_offset=p.end_offset,
            created_at=p.created_at,
        )
        for p in passages
    ]
