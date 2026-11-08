"""
BrandProof AI — Content Submissions, Versioning, Review Execution & Approval.
Supports pasted-text and document (PDF/DOCX) content submission by Creators,
evidence-backed hybrid review execution, finding resolution, reviewer comments,
formal multi-party approvals, and tamper-evident audit exports.
"""

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy import select

from app.api.deps import (
    get_current_member,
    require_role,
    verify_can_approve_content,
)
from app.core.audit import record_audit
from app.core.errors import NotFoundError, ValidationError
from app.core.rate_limit import rate_limit
from app.core.security import enforce_creator_separation
from app.core.storage import validate_guideline_file
from app.db.session import EnforcedUnitOfWorkSession, get_db
from app.models.content import ContentApproval, ContentComment, ContentItem, ContentVersion
from app.models.review import Finding
from app.models.workspace import WorkspaceMember
from app.schemas.content import (
    ContentApprovalRequest,
    ContentApprovalResponse,
    ContentCommentRequest,
    ContentCommentResponse,
    ContentCreateRequest,
    ContentDetailResponse,
    ContentExportResponse,
    ContentResponse,
    ContentVersionCreateRequest,
    ContentVersionResponse,
    FindingDecisionRequest,
    FindingResponse,
)
from app.services.ingestion import extract_docx_passages, extract_pdf_passages
from app.services.review_engine import execute_content_review

router = APIRouter(prefix="/workspaces/{workspace_id}/content", tags=["Content & Approvals"])


# ==============================================================================
# CONTENT LISTING & SUBMISSION
# ==============================================================================


@router.get("", response_model=list[ContentResponse])
def list_workspace_content(
    workspace_id: str,
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> list[ContentResponse]:
    """Lists all content submissions in the active workspace."""
    items = (
        db.execute(
            select(ContentItem)
            .where(ContentItem.workspace_id == workspace_id)
            .order_by(ContentItem.created_at.desc())
        )
        .scalars()
        .all()
    )

    response = []
    for item in items:
        latest_version = (
            db.execute(
                select(ContentVersion.version_number)
                .where(ContentVersion.content_id == item.id)
                .order_by(ContentVersion.version_number.desc())
            )
            .scalars()
            .first()
            or 1
        )

        response.append(
            ContentResponse(
                id=item.id,
                workspace_id=item.workspace_id,
                title=item.title,
                file_type=item.file_type,
                original_filename=item.original_filename,
                created_by=item.created_by,
                state=item.state,
                current_version=latest_version,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )
    return response


@router.post(
    "",
    response_model=ContentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            rate_limit(
                max_requests=20, window_seconds=60, scope="user", endpoint_name="content_uploads"
            )
        )
    ],
)
def submit_pasted_content(
    workspace_id: str,
    payload: ContentCreateRequest,
    member: WorkspaceMember = Depends(require_role(["creator"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> ContentResponse:
    """
    Submits pasted text content for governance review.
    Creates ContentItem and Version 1. State starts in 'draft'.
    """
    new_content = ContentItem(
        workspace_id=workspace_id,
        title=payload.title.strip(),
        file_type="pasted_text",
        original_filename=payload.original_filename,
        created_by=member.user_id,
        state="draft",
    )
    db.add(new_content)
    db.flush()

    version_1 = ContentVersion(
        workspace_id=workspace_id,
        content_id=new_content.id,
        version_number=1,
        raw_text=payload.raw_text,
        normalized_text=payload.raw_text.strip(),
        parsed_metadata={"char_count": len(payload.raw_text), "source": "pasted_text"},
        created_by=member.user_id,
    )
    db.add(version_1)

    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="content.created",
        target_type="content_item",
        target_id=new_content.id,
        details={"title": new_content.title, "file_type": "pasted_text"},
    )

    db.flush()
    db.refresh(new_content)

    return ContentResponse(
        id=new_content.id,
        workspace_id=new_content.workspace_id,
        title=new_content.title,
        file_type=new_content.file_type,
        original_filename=new_content.original_filename,
        created_by=new_content.created_by,
        state=new_content.state,
        current_version=1,
        created_at=new_content.created_at,
        updated_at=new_content.updated_at,
    )


@router.post(
    "/upload",
    response_model=ContentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            rate_limit(
                max_requests=20, window_seconds=60, scope="user", endpoint_name="content_uploads"
            )
        )
    ],
)
async def submit_document_content(
    workspace_id: str,
    title: str,
    file: UploadFile = File(...),
    member: WorkspaceMember = Depends(require_role(["creator"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> ContentResponse:
    """
    Submits content by uploading a PDF or DOCX marketing draft.
    Extracts text and page/paragraph structure into Version 1.
    """
    raw_content = await file.read()
    filename = file.filename or "draft_document.pdf"
    file_type = validate_guideline_file(filename=filename, content=raw_content)

    if file_type == "pdf":
        passages = extract_pdf_passages(raw_content)
    else:
        passages = extract_docx_passages(raw_content)

    full_text = "\n\n".join([p.passage_text for p in passages])
    metadata = {
        "passages_count": len(passages),
        "file_size": len(raw_content),
        "source_type": file_type,
    }

    new_content = ContentItem(
        workspace_id=workspace_id,
        title=title.strip(),
        file_type=file_type,
        original_filename=filename,
        created_by=member.user_id,
        state="draft",
    )
    db.add(new_content)
    db.flush()

    version_1 = ContentVersion(
        workspace_id=workspace_id,
        content_id=new_content.id,
        version_number=1,
        raw_text=full_text,
        normalized_text=full_text.strip(),
        parsed_metadata=metadata,
        created_by=member.user_id,
    )
    db.add(version_1)

    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="content.created_from_file",
        target_type="content_item",
        target_id=new_content.id,
        details={"title": new_content.title, "filename": filename, "file_type": file_type},
    )

    db.flush()
    db.refresh(new_content)

    return ContentResponse(
        id=new_content.id,
        workspace_id=new_content.workspace_id,
        title=new_content.title,
        file_type=new_content.file_type,
        original_filename=new_content.original_filename,
        created_by=new_content.created_by,
        state=new_content.state,
        current_version=1,
        created_at=new_content.created_at,
        updated_at=new_content.updated_at,
    )


# ==============================================================================
# CONTENT DETAILS, VERSIONS & RESOLUTION
# ==============================================================================


@router.get("/{content_id}", response_model=ContentDetailResponse)
def get_content_detail(
    workspace_id: str,
    content_id: str,
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> ContentDetailResponse:
    """Retrieves content item details, all versions, latest findings, and comments."""
    item = db.execute(
        select(ContentItem).where(
            ContentItem.id == content_id,
            ContentItem.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()

    if not item:
        raise NotFoundError("Content item", content_id)

    versions = (
        db.execute(
            select(ContentVersion)
            .where(ContentVersion.content_id == content_id)
            .order_by(ContentVersion.version_number.desc())
        )
        .scalars()
        .all()
    )

    latest_version = versions[0] if versions else None
    latest_findings: list[Finding] = []
    if latest_version:
        latest_findings = (
            db.execute(
                select(Finding)
                .where(Finding.content_version_id == latest_version.id)
                .order_by(Finding.start_offset.asc())
            )
            .scalars()
            .all()
        )

    comments = (
        db.execute(
            select(ContentComment)
            .where(
                ContentComment.workspace_id == workspace_id,
                ContentComment.content_version_id.in_([v.id for v in versions]),
            )
            .order_by(ContentComment.created_at.asc())
        )
        .scalars()
        .all()
    )

    return ContentDetailResponse(
        item=ContentResponse(
            id=item.id,
            workspace_id=item.workspace_id,
            title=item.title,
            file_type=item.file_type,
            original_filename=item.original_filename,
            created_by=item.created_by,
            state=item.state,
            current_version=latest_version.version_number if latest_version else 1,
            created_at=item.created_at,
            updated_at=item.updated_at,
        ),
        versions=[
            ContentVersionResponse(
                id=v.id,
                content_id=v.content_id,
                workspace_id=v.workspace_id,
                version_number=v.version_number,
                raw_text=v.raw_text,
                normalized_text=v.normalized_text,
                parsed_metadata=v.parsed_metadata or {},
                created_by=v.created_by,
                created_at=v.created_at,
            )
            for v in versions
        ],
        latest_findings=[
            FindingResponse(
                id=f.id,
                workspace_id=f.workspace_id,
                run_id=f.run_id,
                content_version_id=f.content_version_id,
                category=f.category,
                severity=f.severity,
                basis_label=f.basis_label,
                start_offset=f.start_offset,
                end_offset=f.end_offset,
                paragraph_index=f.paragraph_index,
                page_number=f.page_number,
                rule_id=f.rule_id,
                fact_id=f.fact_id,
                quoted_submitted_content=f.quoted_submitted_content,
                quoted_approved_source=f.quoted_approved_source,
                source_reference=f.source_reference,
                source_document_name=f.source_document_name,
                explanation=f.explanation,
                verdict=f.verdict,
                confidence_indicator=f.confidence_indicator,
                suggestions=f.suggestions or [],
                accessibility_result=f.accessibility_result,
                not_checked_reason=f.not_checked_reason,
                decision=f.decision,
                decision_reason=f.decision_reason,
                decided_by=f.decided_by,
                decided_at=f.decided_at,
                created_at=f.created_at,
            )
            for f in latest_findings
        ],
        comments=[
            ContentCommentResponse(
                id=c.id,
                workspace_id=c.workspace_id,
                content_version_id=c.content_version_id,
                finding_id=c.finding_id,
                author_id=c.author_id,
                comment_text=c.comment_text,
                created_at=c.created_at,
            )
            for c in comments
        ],
    )


@router.post("/{content_id}/versions", response_model=ContentVersionResponse)
def create_content_version(
    workspace_id: str,
    content_id: str,
    payload: ContentVersionCreateRequest,
    member: WorkspaceMember = Depends(require_role(["creator"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> ContentVersionResponse:
    """
    Submits an edited version of the content (e.g. after resolving findings).
    Increments version number and sets state back to 'in_review'.
    """
    content = db.execute(
        select(ContentItem).where(
            ContentItem.id == content_id,
            ContentItem.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()

    if not content:
        raise NotFoundError("Content item", content_id)

    # Find highest version number
    max_ver = (
        db.execute(
            select(ContentVersion.version_number)
            .where(ContentVersion.content_id == content_id)
            .order_by(ContentVersion.version_number.desc())
        )
        .scalars()
        .first()
        or 1
    )

    new_version = ContentVersion(
        workspace_id=workspace_id,
        content_id=content_id,
        version_number=max_ver + 1,
        raw_text=payload.raw_text,
        normalized_text=payload.raw_text.strip(),
        parsed_metadata={"char_count": len(payload.raw_text), "previous_version": max_ver},
        created_by=member.user_id,
    )
    db.add(new_version)
    db.flush()

    content.state = "in_review"
    content.updated_at = datetime.now(timezone.utc)

    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="content.version_created",
        target_type="content_version",
        target_id=new_version.id,
        details={"version_number": new_version.version_number},
    )

    db.flush()
    db.refresh(new_version)

    return ContentVersionResponse(
        id=new_version.id,
        content_id=new_version.content_id,
        workspace_id=new_version.workspace_id,
        version_number=new_version.version_number,
        raw_text=new_version.raw_text,
        normalized_text=new_version.normalized_text,
        parsed_metadata=new_version.parsed_metadata or {},
        created_by=new_version.created_by,
        created_at=new_version.created_at,
    )


# ==============================================================================
# REVIEW ENGINE EXECUTION
# ==============================================================================


@router.post("/{content_id}/review", response_model=list[FindingResponse])
async def trigger_content_review(
    workspace_id: str,
    content_id: str,
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> list[FindingResponse]:
    """
    Executes the Hybrid Review Engine on the latest version of this content item.
    Evaluates confirmed rules, confirmed facts, tone attributes, and accessibility.
    """
    content = db.execute(
        select(ContentItem).where(
            ContentItem.id == content_id,
            ContentItem.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()

    if not content:
        raise NotFoundError("Content item", content_id)

    latest_version = (
        db.execute(
            select(ContentVersion)
            .where(ContentVersion.content_id == content_id)
            .order_by(ContentVersion.version_number.desc())
        )
        .scalars()
        .first()
    )

    if not latest_version:
        raise NotFoundError("Content version", content_id)

    # Execute review
    run, findings = await execute_content_review(
        db=db,
        content_item=content,
        version=latest_version,
        user_id=member.user_id,
    )

    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="review.executed",
        target_type="review_run",
        target_id=run.id,
        details={"findings_count": len(findings), "version_number": latest_version.version_number},
    )
    db.flush()

    return [
        FindingResponse(
            id=f.id,
            workspace_id=f.workspace_id,
            run_id=f.run_id,
            content_version_id=f.content_version_id,
            category=f.category,
            severity=f.severity,
            basis_label=f.basis_label,
            start_offset=f.start_offset,
            end_offset=f.end_offset,
            paragraph_index=f.paragraph_index,
            page_number=f.page_number,
            rule_id=f.rule_id,
            fact_id=f.fact_id,
            quoted_submitted_content=f.quoted_submitted_content,
            quoted_approved_source=f.quoted_approved_source,
            source_reference=f.source_reference,
            source_document_name=f.source_document_name,
            explanation=f.explanation,
            verdict=f.verdict,
            confidence_indicator=f.confidence_indicator,
            suggestions=f.suggestions or [],
            accessibility_result=f.accessibility_result,
            not_checked_reason=f.not_checked_reason,
            decision=f.decision,
            decision_reason=f.decision_reason,
            decided_by=f.decided_by,
            decided_at=f.decided_at,
            created_at=f.created_at,
        )
        for f in findings
    ]


@router.get("/{content_id}/findings", response_model=list[FindingResponse])
def get_content_findings(
    workspace_id: str,
    content_id: str,
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> list[FindingResponse]:
    """Retrieves all findings for the latest version of the content item."""
    latest_version = (
        db.execute(
            select(ContentVersion.id)
            .where(ContentVersion.content_id == content_id)
            .order_by(ContentVersion.version_number.desc())
        )
        .scalars()
        .first()
    )

    if not latest_version:
        return []

    findings = (
        db.execute(
            select(Finding)
            .where(
                Finding.workspace_id == workspace_id,
                Finding.content_version_id == latest_version,
            )
            .order_by(Finding.start_offset.asc())
        )
        .scalars()
        .all()
    )

    return [
        FindingResponse(
            id=f.id,
            workspace_id=f.workspace_id,
            run_id=f.run_id,
            content_version_id=f.content_version_id,
            category=f.category,
            severity=f.severity,
            basis_label=f.basis_label,
            start_offset=f.start_offset,
            end_offset=f.end_offset,
            paragraph_index=f.paragraph_index,
            page_number=f.page_number,
            rule_id=f.rule_id,
            fact_id=f.fact_id,
            quoted_submitted_content=f.quoted_submitted_content,
            quoted_approved_source=f.quoted_approved_source,
            source_reference=f.source_reference,
            source_document_name=f.source_document_name,
            explanation=f.explanation,
            verdict=f.verdict,
            confidence_indicator=f.confidence_indicator,
            suggestions=f.suggestions or [],
            accessibility_result=f.accessibility_result,
            not_checked_reason=f.not_checked_reason,
            decision=f.decision,
            decision_reason=f.decision_reason,
            decided_by=f.decided_by,
            decided_at=f.decided_at,
            created_at=f.created_at,
        )
        for f in findings
    ]


@router.patch("/findings/{finding_id}", response_model=FindingResponse)
def resolve_finding(
    workspace_id: str,
    finding_id: str,
    payload: FindingDecisionRequest,
    member: WorkspaceMember = Depends(require_role(["creator", "manager", "reviewer"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> FindingResponse:
    """Resolves or dismisses a review finding with an audit-backed reason."""
    finding = db.execute(
        select(Finding).where(
            Finding.id == finding_id,
            Finding.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()

    if not finding:
        raise NotFoundError("Finding", finding_id)

    db_decision = "manual_edit" if payload.decision == "resolved" else payload.decision
    finding.decision = db_decision
    finding.decision_reason = payload.decision_reason
    finding.decided_by = member.user_id
    finding.decided_at = datetime.now(timezone.utc)

    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type=f"finding.{payload.decision}",
        target_type="finding",
        target_id=finding.id,
        details={"decision": payload.decision, "reason": payload.decision_reason},
    )

    db.flush()
    return FindingResponse(
        id=finding.id,
        workspace_id=finding.workspace_id,
        run_id=finding.run_id,
        content_version_id=finding.content_version_id,
        category=finding.category,
        severity=finding.severity,
        basis_label=finding.basis_label,
        start_offset=finding.start_offset,
        end_offset=finding.end_offset,
        paragraph_index=finding.paragraph_index,
        page_number=finding.page_number,
        rule_id=finding.rule_id,
        fact_id=finding.fact_id,
        quoted_submitted_content=finding.quoted_submitted_content,
        quoted_approved_source=finding.quoted_approved_source,
        source_reference=finding.source_reference,
        source_document_name=finding.source_document_name,
        explanation=finding.explanation,
        verdict=finding.verdict,
        confidence_indicator=finding.confidence_indicator,
        suggestions=finding.suggestions or [],
        accessibility_result=finding.accessibility_result,
        not_checked_reason=finding.not_checked_reason,
        decision=finding.decision,
        decision_reason=finding.decision_reason,
        decided_by=finding.decided_by,
        decided_at=finding.decided_at,
        created_at=finding.created_at,
    )


# ==============================================================================
# REVIEWER COMMENTS & FEEDBACK
# ==============================================================================


@router.post("/{content_id}/comments", response_model=ContentCommentResponse)
def add_content_comment(
    workspace_id: str,
    content_id: str,
    payload: ContentCommentRequest,
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> ContentCommentResponse:
    """Adds a reviewer comment to a specific version or finding."""
    comment = ContentComment(
        workspace_id=workspace_id,
        content_version_id=payload.content_version_id,
        finding_id=payload.finding_id,
        author_id=member.user_id,
        comment_text=payload.comment_text.strip(),
    )
    db.add(comment)
    db.flush()

    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="comment.added",
        target_type="content_comment",
        target_id=comment.id,
        details={"comment_preview": comment.comment_text[:50]},
    )

    return ContentCommentResponse(
        id=comment.id,
        workspace_id=comment.workspace_id,
        content_version_id=comment.content_version_id,
        finding_id=comment.finding_id,
        author_id=comment.author_id,
        comment_text=comment.comment_text,
        created_at=comment.created_at,
    )


# ==============================================================================
# APPROVAL & EXPORT WORKFLOW
# ==============================================================================


@router.post("/{content_id}/approve", response_model=ContentApprovalResponse)
def approve_content(
    workspace_id: str,
    content_id: str,
    payload: ContentApprovalRequest,
    content: ContentItem = Depends(verify_can_approve_content),
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> ContentApprovalResponse:
    """
    Approves or requests changes for a content submission.
    SECURITY ENFORCEMENT:
    - Caller must hold Manager or Reviewer role.
    - Caller must NOT be the creator of the content (enforced via verify_can_approve_content & DB constraint).
    """
    enforce_creator_separation(content.created_by, member.user_id)

    latest_version = (
        db.execute(
            select(ContentVersion)
            .where(ContentVersion.content_id == content_id)
            .order_by(ContentVersion.version_number.desc())
        )
        .scalars()
        .first()
    )

    if not latest_version:
        raise NotFoundError("Content version", content_id)

    approval_record = ContentApproval(
        workspace_id=workspace_id,
        content_id=content_id,
        content_version_id=latest_version.id,
        decision=payload.decision,
        notes=payload.notes,
        decided_by=member.user_id,
        decided_at=datetime.now(timezone.utc),
    )
    db.add(approval_record)
    db.flush()

    new_state = "approved" if payload.decision == "approved" else "changes_requested"
    content.state = new_state
    content.updated_at = datetime.now(timezone.utc)

    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type=f"content.{payload.decision}",
        target_type="content_item",
        target_id=content_id,
        details={
            "decision": payload.decision,
            "notes": payload.notes,
            "version_number": latest_version.version_number,
        },
    )

    db.flush()
    db.refresh(approval_record)

    return ContentApprovalResponse(
        id=approval_record.id,
        content_id=content_id,
        decision=approval_record.decision,
        notes=approval_record.notes,
        decided_by=approval_record.decided_by,
        decided_at=approval_record.decided_at,
        new_state=new_state,
    )


@router.get("/{content_id}/export", response_model=ContentExportResponse)
def export_approved_content(
    workspace_id: str,
    content_id: str,
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> ContentExportResponse:
    """
    Exports approved content with a tamper-evident audit hash and approval certificate.
    Only approved content can be exported.
    """
    content = db.execute(
        select(ContentItem).where(
            ContentItem.id == content_id,
            ContentItem.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()

    if not content:
        raise NotFoundError("Content item", content_id)

    if content.state != "approved":
        raise ValidationError(
            f"Cannot export unapproved content. Current status is '{content.state}'. Content must be formally approved by a Manager or Reviewer first."
        )

    latest_version = (
        db.execute(
            select(ContentVersion)
            .where(ContentVersion.content_id == content_id)
            .order_by(ContentVersion.version_number.desc())
        )
        .scalars()
        .first()
    )

    if not latest_version:
        raise NotFoundError("Content version", content_id)

    approval = (
        db.execute(
            select(ContentApproval)
            .where(
                ContentApproval.content_id == content_id,
                ContentApproval.decision == "approved",
            )
            .order_by(ContentApproval.decided_at.desc())
        )
        .scalars()
        .first()
    )

    now = datetime.now(timezone.utc)
    raw_for_hash = f"{content.id}:{latest_version.version_number}:{latest_version.raw_text}:{approval.decided_by if approval else 'unknown'}"
    audit_hash = hashlib.sha256(raw_for_hash.encode()).hexdigest()

    return ContentExportResponse(
        content_id=content.id,
        title=content.title,
        version_number=latest_version.version_number,
        state=content.state,
        content_text=latest_version.raw_text,
        approval_metadata={
            "approved_by": approval.decided_by if approval else None,
            "approved_at": approval.decided_at.isoformat() if approval else None,
            "notes": approval.notes if approval else None,
        },
        export_timestamp=now,
        audit_hash=audit_hash,
    )
