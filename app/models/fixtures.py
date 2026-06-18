"""Fixtures and live match state, including generic participants for races and
individual events that have no home/away team."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import FixtureStatus, MatchEventType, RaceOutcome


class Fixture(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fixtures"

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="CASCADE"), index=True
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("competition_stages.id", ondelete="SET NULL"), nullable=True
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL"), nullable=True
    )
    # Team sports use home/away; races & individual events use fixture_participants.
    home_team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    away_team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("venues.id", ondelete="SET NULL"), nullable=True
    )
    score_official_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    scheduled_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[FixtureStatus] = mapped_column(
        Enum(FixtureStatus, native_enum=False),
        default=FixtureStatus.DRAFT,
        index=True,
    )
    round_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    match_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bracket_position: Mapped[str | None] = mapped_column(String(40), nullable=True)
    label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Optimistic-concurrency guard for live scoring.
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    live_state: Mapped[LiveMatchState | None] = relationship(
        back_populates="fixture",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    events: Mapped[list[MatchEvent]] = relationship(
        back_populates="fixture", cascade="all, delete-orphan"
    )
    participants: Mapped[list[FixtureParticipant]] = relationship(
        back_populates="fixture", cascade="all, delete-orphan"
    )
    sport: Mapped[Sport] = relationship("Sport", lazy="selectin")  # noqa: F821
    home_team: Mapped[Team | None] = relationship(  # noqa: F821
        "Team", foreign_keys=[home_team_id], lazy="selectin"
    )
    away_team: Mapped[Team | None] = relationship(  # noqa: F821
        "Team", foreign_keys=[away_team_id], lazy="selectin"
    )
    venue: Mapped[Venue | None] = relationship("Venue", lazy="selectin")  # noqa: F821
    group: Mapped[Group | None] = relationship("Group", lazy="selectin")  # noqa: F821

    __table_args__ = (
        Index("ix_fixtures_sport_status", "sport_id", "status"),
        Index("ix_fixtures_start_status", "scheduled_start", "status"),
    )


class FixtureParticipant(UUIDMixin, Base):
    """Generic participant slot for fixtures without home/away teams."""

    __tablename__ = "fixture_participants"

    fixture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("participants.id", ondelete="SET NULL"), nullable=True
    )
    slot: Mapped[int] = mapped_column(Integer, default=0)
    lane: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float | None] = mapped_column(nullable=True)

    fixture: Mapped[Fixture] = relationship(back_populates="participants")


class LiveMatchState(UUIDMixin, TimestampMixin, Base):
    """Materialized public match state — fast to read, one row per fixture."""

    __tablename__ = "live_match_states"

    fixture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"), unique=True, index=True
    )
    home_score: Mapped[int] = mapped_column(Integer, default=0)
    away_score: Mapped[int] = mapped_column(Integer, default=0)
    period: Mapped[str | None] = mapped_column(String(40), nullable=True)
    current_period_number: Mapped[int] = mapped_column(Integer, default=0)
    clock_text: Mapped[str | None] = mapped_column(String(20), nullable=True)
    home_sets: Mapped[int] = mapped_column(Integer, default=0)
    away_sets: Mapped[int] = mapped_column(Integer, default=0)
    status_text: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Free-form per-sport extras (quarter scores, fouls, timeouts, …).
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    fixture: Mapped[Fixture] = relationship(back_populates="live_state")


class MatchPeriod(UUIDMixin, Base):
    __tablename__ = "match_periods"

    fixture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(40))
    home_score: Mapped[int] = mapped_column(Integer, default=0)
    away_score: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SetScore(UUIDMixin, Base):
    """Volleyball / table-tennis set breakdown."""

    __tablename__ = "set_scores"

    fixture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"), index=True
    )
    set_number: Mapped[int] = mapped_column(Integer)
    home_points: Mapped[int] = mapped_column(Integer, default=0)
    away_points: Mapped[int] = mapped_column(Integer, default=0)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)


class MatchEvent(UUIDMixin, Base):
    __tablename__ = "match_events"

    fixture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[MatchEventType] = mapped_column(Enum(MatchEventType, native_enum=False))
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("participants.id", ondelete="SET NULL"), nullable=True
    )
    minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period: Mapped[str | None] = mapped_column(String(40), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    fixture: Mapped[Fixture] = relationship(back_populates="events")

    __table_args__ = (Index("ix_match_events_fixture_created", "fixture_id", "created_at"),)


class RaceHeat(UUIDMixin, Base):
    __tablename__ = "race_heats"

    fixture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(40))  # "Heat 1", "Final"
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class RaceEntry(UUIDMixin, Base):
    __tablename__ = "race_entries"

    heat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("race_heats.id", ondelete="CASCADE"), index=True
    )
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("participants.id", ondelete="SET NULL"), nullable=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    lane: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qualified: Mapped[bool] = mapped_column(Boolean, default=False)


class RaceResult(UUIDMixin, Base):
    __tablename__ = "race_results"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("race_entries.id", ondelete="CASCADE"), index=True
    )
    time_seconds: Mapped[float | None] = mapped_column(nullable=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[RaceOutcome] = mapped_column(
        Enum(RaceOutcome, native_enum=False), default=RaceOutcome.FINISHED
    )
