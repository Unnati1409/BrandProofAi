from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, generate_uuid, utc_now


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)  # pasted_text, docx, pdf
    created_by: Mapped[str] = mapped_column(GUID, ForeignKey("profiles.id"), nullable=False)
    state: Mapped[str] = mapped_column(
        String(32), default="draft", nullable=False
    )  # draft, checked, in_review, changes_requested, approved, archived
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    # Relationships
    versions = relationship(
        "ContentVersion", back_populates="content", cascade="all, delete-orphan"
    )
    approvals = relationship(
        "ContentApproval", back_populates="content", cascade="all, delete-orphan"
    )


class ContentVersion(Base):
    __tablename__ = "content_versions"
    __table_args__ = (UniqueConstraint("content_id", "version_number", name="uq_content_version"),)

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(GUID, ForeignKey("profiles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationships
    content = relationship("ContentItem", back_populates="versions")


class ContentApproval(Base):
    __tablename__ = "content_approvals"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_version_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)  # approved, changes_requested
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str] = mapped_column(GUID, ForeignKey("profiles.id"), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationships
    content = relationship("ContentItem", back_populates="approvals")


class ContentComment(Base):
    __tablename__ = "content_comments"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_version_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[str | None] = mapped_column(GUID, nullable=True)
    author_id: Mapped[str] = mapped_column(GUID, ForeignKey("profiles.id"), nullable=False)
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
