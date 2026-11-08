from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, generate_uuid, utc_now


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    # Relationships with explicit foreign_keys specification to resolve ambiguity with invited_by
    workspace_memberships = relationship(
        "WorkspaceMember",
        back_populates="user",
        primaryjoin="Profile.id==WorkspaceMember.user_id",
        cascade="all, delete-orphan",
    )
