"""Core tournament entities: tournament, sport, department, venue, team,
participant, stages and groups."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin, utcnow
from app.models.enums import (
    CompetitionFormat,
    GenderCategory,
    ParticipantKind,
    ScoringType,
)


class Tournament(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tournaments"

    name: Mapped[str] = mapped_column(String(200))
    public_brand: Mapped[str] = mapped_column(String(120), default="BIOLYMPICS LIVE")
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Lagos")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Editable medal-table scoring formula, e.g. {"gold":5,"silver":2,"bronze":1}
    medal_points: Mapped[dict] = mapped_column(
        JSON, default=lambda: {"gold": 5, "silver": 2, "bronze": 1}
    )


class Sport(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sports"

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), index=True)
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    gender_category: Mapped[GenderCategory] = mapped_column(
        Enum(GenderCategory, native_enum=False), default=GenderCategory.OPEN
    )
    competition_format: Mapped[CompetitionFormat] = mapped_column(
        Enum(CompetitionFormat, native_enum=False), default=CompetitionFormat.KNOCKOUT
    )
    scoring_type: Mapped[ScoringType] = mapped_column(
        Enum(ScoringType, native_enum=False), default=ScoringType.GOAL_BASED
    )
    participant_kind: Mapped[ParticipantKind] = mapped_column(
        Enum(ParticipantKind, native_enum=False), default=ParticipantKind.TEAM
    )
    requires_table: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_bracket: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_live: Mapped[bool] = mapped_column(Boolean, default=True)
    uses_timing: Mapped[bool] = mapped_column(Boolean, default=False)
    periods: Mapped[int] = mapped_column(Integer, default=2)
    display_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    rules: Mapped[SportRule | None] = relationship(
        back_populates="sport", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("tournament_id", "slug"),)


class SportRule(UUIDMixin, TimestampMixin, Base):
    """Configurable points and tie-break rules per sport."""

    __tablename__ = "sport_rules"

    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="CASCADE"), unique=True
    )
    points_win: Mapped[int] = mapped_column(Integer, default=3)
    points_draw: Mapped[int] = mapped_column(Integer, default=1)
    points_loss: Mapped[int] = mapped_column(Integer, default=0)
    # Ordered list of tie-break keys, e.g. ["points","gd","gf","head_to_head","admin"]
    tie_breakers: Mapped[list] = mapped_column(
        JSON, default=lambda: ["points", "gd", "gf", "head_to_head", "admin"]
    )
    sets_to_win: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_columns: Mapped[list | None] = mapped_column(JSON, nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    sport: Mapped[Sport] = relationship(back_populates="rules")


class Department(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "departments"

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    abbreviation: Mapped[str] = mapped_column(String(16), index=True)
    short_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    slug: Mapped[str] = mapped_column(String(120), index=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(9), default="#1f6f43")
    secondary_color: Mapped[str] = mapped_column(String(9), default="#0b3d24")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("tournament_id", "abbreviation"),)


class Venue(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "venues"

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Team(UUIDMixin, TimestampMixin, Base):
    """A department's entry in a particular sport."""

    __tablename__ = "teams"

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="CASCADE"), index=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    department: Mapped[Department] = relationship(lazy="selectin")
    sport: Mapped[Sport] = relationship(lazy="selectin")

    __table_args__ = (UniqueConstraint("sport_id", "department_id"),)


class Participant(UUIDMixin, TimestampMixin, Base):
    """An individual competitor (athletics, chess, table tennis, marathon, …)."""

    __tablename__ = "participants"

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    full_name: Mapped[str] = mapped_column(String(160))
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    bib_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TeamMember(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "team_members"

    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), index=True
    )
    shirt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role: Mapped[str | None] = mapped_column(String(40), nullable=True)

    __table_args__ = (UniqueConstraint("team_id", "participant_id"),)


class CompetitionStage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "competition_stages"

    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))  # e.g. "Group Stage", "Semi-Finals"
    kind: Mapped[str] = mapped_column(String(40), default="GROUP")  # GROUP|KNOCKOUT|FINAL
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class Group(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "groups"

    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="CASCADE"), index=True
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("competition_stages.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(40))  # "Group A", "Pot B"
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class GroupMember(UUIDMixin, Base):
    __tablename__ = "group_members"

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("group_id", "team_id"),)
