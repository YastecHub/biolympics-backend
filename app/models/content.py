"""Public content: announcements, sponsors, uploaded files."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import AnnouncementType


class Announcement(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "announcements"

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    type: Mapped[AnnouncementType] = mapped_column(
        Enum(AnnouncementType, native_enum=False), default=AnnouncementType.GENERAL
    )
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    sport_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sports.id", ondelete="SET NULL"), nullable=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    fixture_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("fixtures.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (Index("ix_announcements_published", "published_at"),)


class Sponsor(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sponsors"

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tier: Mapped[str | None] = mapped_column(String(40), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UploadedFile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "uploaded_files"

    key: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
