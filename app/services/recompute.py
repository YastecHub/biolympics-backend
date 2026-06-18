"""Database-aware recomputation of group standings from completed fixtures.

Triggered when a fixture is completed, corrected, marked walkover, or a prior
contributor is cancelled. Deterministic and idempotent — it fully rebuilds the
affected standing rows each time.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Group, GroupMember, Sport, SportRule, Team
from app.models.enums import FixtureStatus
from app.models.fixtures import Fixture, LiveMatchState
from app.models.standings import Standing, StandingRow
from app.services.standings import MatchResult, PointsRules, compute_table

# Statuses whose result counts toward standings.
COUNTING_STATUSES = {FixtureStatus.COMPLETED, FixtureStatus.WALKOVER}


async def _rules_for_sport(db: AsyncSession, sport_id: uuid.UUID) -> PointsRules:
    rule = (
        await db.execute(select(SportRule).where(SportRule.sport_id == sport_id))
    ).scalar_one_or_none()
    if rule is None:
        return PointsRules()
    return PointsRules(
        win=rule.points_win,
        draw=rule.points_draw,
        loss=rule.points_loss,
        tie_breakers=list(rule.tie_breakers or PointsRules().tie_breakers),
    )


async def recompute_group_standings(db: AsyncSession, sport_id: uuid.UUID) -> list[Standing]:
    """Rebuild every group standing for a sport. Returns the Standing rows."""
    rules = await _rules_for_sport(db, sport_id)
    groups = (await db.execute(select(Group).where(Group.sport_id == sport_id))).scalars().all()

    result_standings: list[Standing] = []
    for group in groups:
        team_ids = (
            (await db.execute(select(GroupMember.team_id).where(GroupMember.group_id == group.id)))
            .scalars()
            .all()
        )
        if not team_ids:
            continue

        rows = (
            await db.execute(
                select(Fixture, LiveMatchState)
                .join(LiveMatchState, LiveMatchState.fixture_id == Fixture.id)
                .where(
                    Fixture.group_id == group.id,
                    Fixture.status.in_(COUNTING_STATUSES),
                )
            )
        ).all()
        results = [
            MatchResult(
                home=fx.home_team_id,
                away=fx.away_team_id,
                home_score=st.home_score,
                away_score=st.away_score,
            )
            for fx, st in rows
            if fx.home_team_id and fx.away_team_id
        ]

        table = compute_table(list(team_ids), results, rules)

        standing = (
            await db.execute(
                select(Standing).where(Standing.sport_id == sport_id, Standing.group_id == group.id)
            )
        ).scalar_one_or_none()
        if standing is None:
            standing = Standing(sport_id=sport_id, group_id=group.id)
            db.add(standing)
            await db.flush()
        else:
            await db.execute(delete(StandingRow).where(StandingRow.standing_id == standing.id))

        for pos, row in enumerate(table, start=1):
            db.add(
                StandingRow(
                    standing_id=standing.id,
                    team_id=row.team_id,
                    position=pos,
                    played=row.played,
                    won=row.won,
                    drawn=row.drawn,
                    lost=row.lost,
                    goals_for=row.goals_for,
                    goals_against=row.goals_against,
                    goal_difference=row.goal_difference,
                    points=row.points(rules),
                )
            )
        result_standings.append(standing)

    await db.flush()
    return result_standings


async def sport_id_for_slug(db: AsyncSession, slug: str) -> uuid.UUID | None:
    return (await db.execute(select(Sport.id).where(Sport.slug == slug))).scalar_one_or_none()


async def team_label(db: AsyncSession, team_id: uuid.UUID) -> str:
    team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
    if team is None:
        return "?"
    return team.display_name or str(team.department_id)
