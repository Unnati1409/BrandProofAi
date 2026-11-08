from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, generate_uuid, utc_now


class SourceDocument(Base):
    """
    Represents an imported brand guideline or reference policy document.
    Raw uploaded documents remain unapproved candidates until individual
    rules and facts extracted from them are explicitly confirmed by a Brand Owner.
    """

    __tablename__ = "source_documents"
    __table_args__ = (UniqueConstraint("workspace_id", "id", name="uq_source_documents_ws"),)

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(GUID, ForeignKey("profiles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SourcePassage(Base):
    """
    Extracted textual clause or section from an ingested brand guideline.
    Contains precise page/paragraph offsets and serves as the verifiable
    evidence backing candidate rules and approved facts.
    """

    __tablename__ = "source_passages"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    clause_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    passage_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
