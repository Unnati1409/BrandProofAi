from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, StringArray, generate_uuid, utc_now


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(
        GUID, ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False
    )
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_enabled_by: Mapped[str | None] = mapped_column(
        GUID, ForeignKey("profiles.id"), nullable=True
    )
    retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    # Relationships
    members = relationship(
        "WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan"
    )


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),)

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    roles: Mapped[list[str]] = mapped_column(StringArray, default=list, nullable=False)
    invited_by: Mapped[str | None] = mapped_column(GUID, ForeignKey("profiles.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationships with explicit foreign_keys specification
    workspace = relationship("Workspace", back_populates="members")
    user = relationship("Profile", back_populates="workspace_memberships", foreign_keys=[user_id])
