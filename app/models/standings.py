"""Computed standings, knockout brackets, medals and department points."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import MedalKind


class Standing(UUIDMixin, TimestampMixin, Base):
    """A standings table for a sport (optionally per group)."""

    __tablename__ = "standings"

    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True
    )
    rows: Mapped[list[StandingRow]] = relationship(
        back_populates="standing", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("sport_id", "group_id"),)


class StandingRow(UUIDMixin, Base):
    __tablename__ = "standing_rows"

    standing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("standings.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    played: Mapped[int] = mapped_column(Integer, default=0)
    won: Mapped[int] = mapped_column(Integer, default=0)
    drawn: Mapped[int] = mapped_column(Integer, default=0)
    lost: Mapped[int] = mapped_column(Integer, default=0)
    goals_for: Mapped[int] = mapped_column(Integer, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, default=0)
    goal_difference: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)

    standing: Mapped[Standing] = relationship(back_populates="rows")


class Bracket(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "brackets"

    sport_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sports.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80), default="Main")
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    nodes: Mapped[list[BracketNode]] = relationship(
        back_populates="bracket", cascade="all, delete-orphan"
    )


class BracketNode(UUIDMixin, Base):
    __tablename__ = "bracket_nodes"

    bracket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brackets.id", ondelete="CASCADE"), index=True
    )
    fixture_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("fixtures.id", ondelete="SET NULL"), nullable=True
    )
    round_name: Mapped[str] = mapped_column(String(40))  # QF / SF / FINAL / 3RD
    position: Mapped[int] = mapped_column(Integer, default=0)
    # Pointers used before fixtures are generated (e.g. "Group A winner")
    home_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    away_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    feeds_into_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bracket_nodes.id", ondelete="SET NULL"), nullable=True
    )

    bracket: Mapped[Bracket] = relationship(back_populates="nodes")


class Medal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "medals"

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True
    )
    sport_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sports.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[MedalKind] = mapped_column(Enum(MedalKind, native_enum=False))
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)


class DepartmentPoints(UUIDMixin, TimestampMixin, Base):
    """Computed medal-table row per department."""

    __tablename__ = "department_points"

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True
    )
    gold: Mapped[int] = mapped_column(Integer, default=0)
    silver: Mapped[int] = mapped_column(Integer, default=0)
    bronze: Mapped[int] = mapped_column(Integer, default=0)
    participation_points: Mapped[float] = mapped_column(Float, default=0.0)
    bonus_points: Mapped[float] = mapped_column(Float, default=0.0)
    penalties: Mapped[float] = mapped_column(Float, default=0.0)
    total_points: Mapped[float] = mapped_column(Float, default=0.0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (UniqueConstraint("tournament_id", "department_id"),)
