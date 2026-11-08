from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, generate_uuid, utc_now


class ReviewRun(Base):
    __tablename__ = "review_runs"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_version_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False
    )
    catalogue_version_id: Mapped[str | None] = mapped_column(
        GUID, ForeignKey("catalogue_versions.id"), nullable=True
    )
    model_identifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    timings_ms: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(GUID, ForeignKey("profiles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_version_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    basis_label: Mapped[str] = mapped_column(String(16), nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("rules.id"), nullable=True)
    fact_id: Mapped[str | None] = mapped_column(
        GUID, ForeignKey("approved_facts.id"), nullable=True
    )
    quoted_submitted_content: Mapped[str] = mapped_column(Text, nullable=False)
    quoted_approved_source: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    source_document_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence_indicator: Mapped[str | None] = mapped_column(String(16), nullable=True)
    suggestions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    accessibility_result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    not_checked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(GUID, ForeignKey("profiles.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
