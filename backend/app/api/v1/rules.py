"""
BrandProof AI — Brand Rules, Approved Facts & Tone Management Endpoints.
Enforces the core governance invariant: Only Brand Owners and Admins can confirm
candidate rules and facts. Only CONFIRMED items become active review evidence.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from app.api.deps import get_current_member, require_role
from app.core.audit import record_audit
from app.core.errors import NotFoundError
from app.db.session import EnforcedUnitOfWorkSession, get_db
from app.models.rule import ApprovedFact, Rule, ToneAttribute
from app.models.workspace import WorkspaceMember
from app.schemas.rule import (
    FactCreateRequest,
    FactResponse,
    FactUpdateRequest,
    RuleCreateRequest,
    RuleResponse,
    RuleUpdateRequest,
    ToneCreateRequest,
    ToneResponse,
    ToneUpdateRequest,
)

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["Brand Knowledge"])


# ==============================================================================
# RULES MANAGEMENT
# ==============================================================================


@router.get("/rules", response_model=list[RuleResponse])
def list_rules(
    workspace_id: str,
    status_filter: str | None = Query(None, alias="status"),
    rule_type: str | None = Query(None),
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> list[RuleResponse]:
    """Lists rules for the workspace. Can filter by status (candidate, confirmed, etc.)."""
    query = select(Rule).where(Rule.workspace_id == workspace_id)
    if status_filter:
        query = query.where(Rule.status == status_filter)
    if rule_type:
        query = query.where(Rule.rule_type == rule_type)

    query = query.order_by(Rule.created_at.desc())
    rules = db.execute(query).scalars().all()

    return [
        RuleResponse(
            id=r.id,
            workspace_id=r.workspace_id,
            rule_type=r.rule_type,
            severity=r.severity,
            status=r.status,
            payload=r.payload,
            explanation=r.explanation,
            source_passage_id=r.source_passage_id,
            confirmed_by=r.confirmed_by,
            confirmed_at=r.confirmed_at,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rules
    ]


@router.post(
    "/rules",
    response_model=RuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_rule(
    workspace_id: str,
    req: RuleCreateRequest,
    member: WorkspaceMember = Depends(require_role(["brand_owner", "admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> RuleResponse:
    """Manually creates a new brand rule."""
    rule = Rule(
        workspace_id=workspace_id,
        rule_type=req.rule_type,
        severity=req.severity,
        status="candidate",
        payload=req.payload,
        explanation=req.explanation,
        source_passage_id=req.source_passage_id,
    )
    db.add(rule)
    db.flush()

    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="rule.created",
        target_type="rule",
        target_id=rule.id,
        details={"rule_type": rule.rule_type, "severity": rule.severity},
    )

    return RuleResponse(
        id=rule.id,
        workspace_id=rule.workspace_id,
        rule_type=rule.rule_type,
        severity=rule.severity,
        status=rule.status,
        payload=rule.payload,
        explanation=rule.explanation,
        source_passage_id=rule.source_passage_id,
        confirmed_by=rule.confirmed_by,
        confirmed_at=rule.confirmed_at,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.patch("/rules/{rule_id}", response_model=RuleResponse)
def update_or_confirm_rule(
    workspace_id: str,
    rule_id: str,
    req: RuleUpdateRequest,
    member: WorkspaceMember = Depends(require_role(["brand_owner", "admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> RuleResponse:
    """
    Updates or confirms a candidate rule.
    When a Brand Owner sets status='confirmed', the rule becomes active review evidence.
    """
    rule = db.execute(
        select(Rule).where(Rule.id == rule_id, Rule.workspace_id == workspace_id)
    ).scalar_one_or_none()

    if not rule:
        raise NotFoundError("Rule", rule_id)

    if req.status:
        rule.status = req.status
        if req.status == "confirmed":
            rule.confirmed_by = member.user_id
            rule.confirmed_at = datetime.now(timezone.utc)
        elif req.status in ["rejected", "retired"]:
            rule.confirmed_by = None
            rule.confirmed_at = None

    if req.severity:
        rule.severity = req.severity
    if req.payload is not None:
        rule.payload = req.payload
    if req.explanation is not None:
        rule.explanation = req.explanation

    db.flush()

    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type=f"rule.{rule.status}",
        target_type="rule",
        target_id=rule.id,
        details={"status": rule.status, "severity": rule.severity},
    )

    return RuleResponse(
        id=rule.id,
        workspace_id=rule.workspace_id,
        rule_type=rule.rule_type,
        severity=rule.severity,
        status=rule.status,
        payload=rule.payload,
        explanation=rule.explanation,
        source_passage_id=rule.source_passage_id,
        confirmed_by=rule.confirmed_by,
        confirmed_at=rule.confirmed_at,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


# ==============================================================================
# APPROVED FACTS MANAGEMENT
# ==============================================================================


@router.get("/facts", response_model=list[FactResponse])
def list_facts(
    workspace_id: str,
    status_filter: str | None = Query(None, alias="status"),
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> list[FactResponse]:
    """Lists facts for the workspace. Can filter by candidate vs confirmed."""
    query = select(ApprovedFact).where(ApprovedFact.workspace_id == workspace_id)
    if status_filter:
        query = query.where(ApprovedFact.status == status_filter)

    query = query.order_by(ApprovedFact.created_at.desc())
    facts = db.execute(query).scalars().all()

    return [
        FactResponse(
            id=f.id,
            workspace_id=f.workspace_id,
            statement=f.statement,
            source_reference=f.source_reference,
            owner=f.owner,
            expiry_date=f.expiry_date,
            status=f.status,
            version=f.version,
            source_passage_id=f.source_passage_id,
            confirmed_by=f.confirmed_by,
            confirmed_at=f.confirmed_at,
            created_at=f.created_at,
            updated_at=f.updated_at,
        )
        for f in facts
    ]


@router.post(
    "/facts",
    response_model=FactResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_fact(
    workspace_id: str,
    req: FactCreateRequest,
    member: WorkspaceMember = Depends(require_role(["brand_owner", "admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> FactResponse:
    """Manually creates a candidate approved fact."""
    fact = ApprovedFact(
        workspace_id=workspace_id,
        statement=req.statement,
        source_reference=req.source_reference,
        owner=req.owner,
        expiry_date=req.expiry_date,
        source_passage_id=req.source_passage_id,
        status="candidate",
        version=1,
    )
    db.add(fact)
    db.flush()

    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type="fact.created",
        target_type="approved_fact",
        target_id=fact.id,
        details={"statement_preview": fact.statement[:60]},
    )

    return FactResponse(
        id=fact.id,
        workspace_id=fact.workspace_id,
        statement=fact.statement,
        source_reference=fact.source_reference,
        owner=fact.owner,
        expiry_date=fact.expiry_date,
        status=fact.status,
        version=fact.version,
        source_passage_id=fact.source_passage_id,
        confirmed_by=fact.confirmed_by,
        confirmed_at=fact.confirmed_at,
        created_at=fact.created_at,
        updated_at=fact.updated_at,
    )


@router.patch("/facts/{fact_id}", response_model=FactResponse)
def update_or_confirm_fact(
    workspace_id: str,
    fact_id: str,
    req: FactUpdateRequest,
    member: WorkspaceMember = Depends(require_role(["brand_owner", "admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> FactResponse:
    """
    Updates or confirms a brand fact.
    When set to status='confirmed' by Brand Owner, it becomes active truth evidence.
    """
    fact = db.execute(
        select(ApprovedFact).where(
            ApprovedFact.id == fact_id, ApprovedFact.workspace_id == workspace_id
        )
    ).scalar_one_or_none()

    if not fact:
        raise NotFoundError("Approved fact", fact_id)

    if req.status:
        fact.status = req.status
        if req.status == "confirmed":
            fact.confirmed_by = member.user_id
            fact.confirmed_at = datetime.now(timezone.utc)
        elif req.status in ["rejected", "retired"]:
            fact.confirmed_by = None
            fact.confirmed_at = None

    if req.statement is not None:
        fact.statement = req.statement
    if req.source_reference is not None:
        fact.source_reference = req.source_reference
    if req.owner is not None:
        fact.owner = req.owner
    if req.expiry_date is not None:
        fact.expiry_date = req.expiry_date

    db.flush()

    record_audit(
        db=db,
        workspace_id=workspace_id,
        event_type=f"fact.{fact.status}",
        target_type="approved_fact",
        target_id=fact.id,
        details={"status": fact.status},
    )

    return FactResponse(
        id=fact.id,
        workspace_id=fact.workspace_id,
        statement=fact.statement,
        source_reference=fact.source_reference,
        owner=fact.owner,
        expiry_date=fact.expiry_date,
        status=fact.status,
        version=fact.version,
        source_passage_id=fact.source_passage_id,
        confirmed_by=fact.confirmed_by,
        confirmed_at=fact.confirmed_at,
        created_at=fact.created_at,
        updated_at=fact.updated_at,
    )


# ==============================================================================
# TONE ATTRIBUTES MANAGEMENT
# ==============================================================================


@router.get("/tone", response_model=list[ToneResponse])
def list_tone_attributes(
    workspace_id: str,
    status_filter: str | None = Query(None, alias="status"),
    member: WorkspaceMember = Depends(get_current_member),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> list[ToneResponse]:
    """Lists tone attributes for the workspace."""
    query = select(ToneAttribute).where(ToneAttribute.workspace_id == workspace_id)
    if status_filter:
        query = query.where(ToneAttribute.status == status_filter)

    tones = db.execute(query.order_by(ToneAttribute.created_at.desc())).scalars().all()

    return [
        ToneResponse(
            id=t.id,
            workspace_id=t.workspace_id,
            name=t.name,
            description=t.description,
            positive_examples=t.positive_examples or [],
            negative_examples=t.negative_examples or [],
            status=t.status,
            created_at=t.created_at,
        )
        for t in tones
    ]


@router.post(
    "/tone",
    response_model=ToneResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tone_attribute(
    workspace_id: str,
    req: ToneCreateRequest,
    member: WorkspaceMember = Depends(require_role(["brand_owner", "admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> ToneResponse:
    """Creates a new tone attribute."""
    tone = ToneAttribute(
        workspace_id=workspace_id,
        name=req.name,
        description=req.description,
        positive_examples=req.positive_examples,
        negative_examples=req.negative_examples,
        status="candidate",
    )
    db.add(tone)
    db.flush()

    return ToneResponse(
        id=tone.id,
        workspace_id=tone.workspace_id,
        name=tone.name,
        description=tone.description,
        positive_examples=tone.positive_examples,
        negative_examples=tone.negative_examples,
        status=tone.status,
        created_at=tone.created_at,
    )


@router.patch("/tone/{tone_id}", response_model=ToneResponse)
def update_or_confirm_tone(
    workspace_id: str,
    tone_id: str,
    req: ToneUpdateRequest,
    member: WorkspaceMember = Depends(require_role(["brand_owner", "admin"])),
    db: EnforcedUnitOfWorkSession = Depends(get_db),
) -> ToneResponse:
    """Updates or confirms a tone attribute."""
    tone = db.execute(
        select(ToneAttribute).where(
            ToneAttribute.id == tone_id, ToneAttribute.workspace_id == workspace_id
        )
    ).scalar_one_or_none()

    if not tone:
        raise NotFoundError("Tone attribute", tone_id)

    if req.status:
        tone.status = req.status
    if req.name is not None:
        tone.name = req.name
    if req.description is not None:
        tone.description = req.description
    if req.positive_examples is not None:
        tone.positive_examples = req.positive_examples
    if req.negative_examples is not None:
        tone.negative_examples = req.negative_examples

    db.flush()

    return ToneResponse(
        id=tone.id,
        workspace_id=tone.workspace_id,
        name=tone.name,
        description=tone.description,
        positive_examples=tone.positive_examples,
        negative_examples=tone.negative_examples,
        status=tone.status,
        created_at=tone.created_at,
    )
