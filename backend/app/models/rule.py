from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, StringArray, generate_uuid, utc_now


class CatalogueVersion(Base):
    __tablename__ = "catalogue_versions"
    __table_args__ = (
        UniqueConstraint("workspace_id", "version_number", name="uq_catalogue_version"),
    )

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(GUID, ForeignKey("profiles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    catalogue_version_id: Mapped[str | None] = mapped_column(
        GUID, ForeignKey("catalogue_versions.id"), nullable=True
    )
    source_passage_id: Mapped[str | None] = mapped_column(GUID, nullable=True)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="candidate", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(GUID, ForeignKey("profiles.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ApprovedFact(Base):
    __tablename__ = "approved_facts"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    catalogue_version_id: Mapped[str | None] = mapped_column(
        GUID, ForeignKey("catalogue_versions.id"), nullable=True
    )
    source_passage_id: Mapped[str | None] = mapped_column(GUID, nullable=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="candidate", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(GUID, ForeignKey("profiles.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ToneAttribute(Base):
    __tablename__ = "tone_attributes"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    positive_examples: Mapped[list[str]] = mapped_column(StringArray, default=list, nullable=False)
    negative_examples: Mapped[list[str]] = mapped_column(StringArray, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="candidate", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[str] = mapped_column(GUID, ForeignKey("profiles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
