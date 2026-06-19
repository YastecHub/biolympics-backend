"""Public, read-only endpoints. No authentication required."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.deps import DbDep
from app.models.content import Announcement, Sponsor
from app.models.core import Department, Group, Sport, SportRule, Team, Venue
from app.models.enums import FixtureStatus
from app.models.fixtures import Fixture, MatchEvent
from app.models.standings import (
    DepartmentPoints,
    Standing,
    StandingRow,
)
from app.schemas.public import (
    AnnouncementOut,
    DepartmentOut,
    FixtureOut,
    MatchEventOut,
    MedalRowOut,
    SponsorOut,
    SportOut,
    StandingOut,
    StandingRowOut,
    TournamentOut,
    VenueOut,
)
from app.services.repo import (
    current_tournament,
    department_by_slug,
    sport_by_slug,
)
from app.services.serializers import fixture_to_out
from app.services.medal_table import DEFAULT_MEDAL_POINTS, MedalTally, compute_medal_table

router = APIRouter()


@router.get("/tournaments/current", response_model=TournamentOut, tags=["public"])
async def get_current_tournament(db: DbDep) -> TournamentOut:
    t = await current_tournament(db)
    if t is None:
        raise HTTPException(404, "No current tournament configured")
    return TournamentOut.model_validate(t)


@router.get("/sports", response_model=list[SportOut], tags=["public"])
async def list_sports(db: DbDep) -> list[SportOut]:
    rows = (
        (
            await db.execute(
                select(Sport).where(Sport.is_active.is_(True)).order_by(Sport.display_order)
            )
        )
        .scalars()
        .all()
    )
    return [SportOut.model_validate(s) for s in rows]


@router.get("/sports/{sport_slug}", response_model=SportOut, tags=["public"])
async def get_sport(sport_slug: str, db: DbDep) -> SportOut:
    sport = await sport_by_slug(db, sport_slug)
    if sport is None:
        raise HTTPException(404, "Sport not found")
    return SportOut.model_validate(sport)


@router.get("/departments", response_model=list[DepartmentOut], tags=["public"])
async def list_departments(db: DbDep) -> list[DepartmentOut]:
    rows = (await db.execute(select(Department).order_by(Department.abbreviation))).scalars().all()
    return [DepartmentOut.model_validate(d) for d in rows]


@router.get("/departments/{department_slug}", response_model=DepartmentOut, tags=["public"])
async def get_department(department_slug: str, db: DbDep) -> DepartmentOut:
    dept = await department_by_slug(db, department_slug)
    if dept is None:
        raise HTTPException(404, "Department not found")
    return DepartmentOut.model_validate(dept)


async def _query_fixtures(
    db: DbDep,
    *,
    statuses: list[FixtureStatus] | None = None,
    sport_slug: str | None = None,
    only_published: bool = True,
    order_desc: bool = False,
    limit: int | None = None,
) -> list[Fixture]:
    stmt = select(Fixture)
    if only_published:
        stmt = stmt.where(Fixture.published.is_(True))
    if statuses:
        stmt = stmt.where(Fixture.status.in_(statuses))
    if sport_slug:
        sport = await sport_by_slug(db, sport_slug)
        if sport is None:
            return []
        stmt = stmt.where(Fixture.sport_id == sport.id)
    order = Fixture.scheduled_start.desc() if order_desc else Fixture.scheduled_start.asc()
    stmt = stmt.order_by(order.nullslast())
    if limit:
        stmt = stmt.limit(limit)
    return list((await db.execute(stmt)).scalars().all())


@router.get("/fixtures", response_model=list[FixtureOut], tags=["public"])
async def list_fixtures(
    db: DbDep,
    sport: str | None = Query(default=None),
    status: FixtureStatus | None = Query(default=None),
) -> list[FixtureOut]:
    statuses = [status] if status else None
    fixtures = await _query_fixtures(db, statuses=statuses, sport_slug=sport)
    return [fixture_to_out(f) for f in fixtures]


@router.get("/fixtures/live", response_model=list[FixtureOut], tags=["public"])
async def live_fixtures(db: DbDep) -> list[FixtureOut]:
    live = [
        FixtureStatus.LIVE,
        FixtureStatus.HALF_TIME,
        FixtureStatus.PERIOD_BREAK,
        FixtureStatus.PAUSED,
    ]
    fixtures = await _query_fixtures(db, statuses=live)
    return [fixture_to_out(f) for f in fixtures]


@router.get("/fixtures/upcoming", response_model=list[FixtureOut], tags=["public"])
async def upcoming_fixtures(
    db: DbDep, limit: int = Query(default=20, ge=1, le=100)
) -> list[FixtureOut]:
    stmt = (
        select(Fixture)
        .where(
            Fixture.published.is_(True),
            Fixture.status.in_([FixtureStatus.SCHEDULED, FixtureStatus.WARMUP]),
        )
        .order_by(Fixture.scheduled_start.asc().nullslast())
        .limit(limit)
    )
    fixtures = list((await db.execute(stmt)).scalars().all())
    return [fixture_to_out(f) for f in fixtures]


@router.get("/results", response_model=list[FixtureOut], tags=["public"])
async def results(db: DbDep, sport: str | None = Query(default=None)) -> list[FixtureOut]:
    done = [FixtureStatus.COMPLETED, FixtureStatus.WALKOVER]
    fixtures = await _query_fixtures(db, statuses=done, sport_slug=sport, order_desc=True)
    return [fixture_to_out(f) for f in fixtures]


@router.get("/schedule", response_model=list[FixtureOut], tags=["public"])
async def schedule(db: DbDep) -> list[FixtureOut]:
    fixtures = await _query_fixtures(db)
    return [fixture_to_out(f) for f in fixtures]


@router.get("/fixtures/{fixture_id}", response_model=FixtureOut, tags=["public"])
async def get_fixture(fixture_id: uuid.UUID, db: DbDep) -> FixtureOut:
    fx = (await db.execute(select(Fixture).where(Fixture.id == fixture_id))).scalar_one_or_none()
    if fx is None:
        raise HTTPException(404, "Fixture not found")
    return fixture_to_out(fx)


@router.get(
    "/fixtures/{fixture_id}/events",
    response_model=list[MatchEventOut],
    tags=["public"],
)
async def fixture_events(fixture_id: uuid.UUID, db: DbDep) -> list[MatchEventOut]:
    rows = (
        (
            await db.execute(
                select(MatchEvent)
                .where(MatchEvent.fixture_id == fixture_id)
                .order_by(MatchEvent.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [MatchEventOut.model_validate(e) for e in rows]


async def _standings_for_sport(db: DbDep, sport: Sport) -> list[StandingOut]:
    rule = (
        await db.execute(select(SportRule).where(SportRule.sport_id == sport.id))
    ).scalar_one_or_none()
    tie_breakers = list(rule.tie_breakers) if rule else ["points", "gd", "gf"]

    standings = (
        (await db.execute(select(Standing).where(Standing.sport_id == sport.id))).scalars().all()
    )

    # Pre-load department label per team so rows show abbreviations, not ids.
    label_rows = (
        await db.execute(
            select(Team.id, Department.abbreviation, Department.name)
            .join(Department, Department.id == Team.department_id)
            .where(Team.sport_id == sport.id)
        )
    ).all()
    team_labels: dict = {tid: (abbr, name) for tid, abbr, name in label_rows}

    out: list[StandingOut] = []
    for st in standings:
        group = (
            (await db.execute(select(Group).where(Group.id == st.group_id))).scalar_one_or_none()
            if st.group_id
            else None
        )
        rows = (
            (
                await db.execute(
                    select(StandingRow)
                    .where(StandingRow.standing_id == st.id)
                    .order_by(StandingRow.position.asc())
                )
            )
            .scalars()
            .all()
        )
        row_models: list[StandingRowOut] = []
        for r in rows:
            model = StandingRowOut.model_validate(r)
            abbr, name = team_labels.get(r.team_id, (None, None))
            model.department_abbr = abbr
            model.department_name = name
            row_models.append(model)
        out.append(
            StandingOut(
                sport_slug=sport.slug,
                group_name=group.name if group else None,
                tie_breakers=tie_breakers,
                rows=row_models,
            )
        )
    return out


@router.get("/standings", response_model=list[StandingOut], tags=["public"])
async def all_standings(db: DbDep) -> list[StandingOut]:
    sports = (await db.execute(select(Sport).where(Sport.requires_table.is_(True)))).scalars().all()
    result: list[StandingOut] = []
    for sport in sports:
        result.extend(await _standings_for_sport(db, sport))
    return result


@router.get("/standings/{sport_slug}", response_model=list[StandingOut], tags=["public"])
async def sport_standings(sport_slug: str, db: DbDep) -> list[StandingOut]:
    sport = await sport_by_slug(db, sport_slug)
    if sport is None:
        raise HTTPException(404, "Sport not found")
    return await _standings_for_sport(db, sport)


@router.get("/medal-table", response_model=list[MedalRowOut], tags=["public"])
async def medal_table(db: DbDep) -> list[MedalRowOut]:
    t = await current_tournament(db)
    if t is None:
        return []
    rows = (
        await db.execute(
            select(DepartmentPoints, Department)
            .join(Department, Department.id == DepartmentPoints.department_id)
            .where(DepartmentPoints.tournament_id == t.id)
            .order_by(DepartmentPoints.position.asc())
        )
    ).all()
    recomputed = {
        row.department_id: row
        for row in compute_medal_table(
            [
                MedalTally(
                    department_id=dp.department_id,
                    gold=dp.gold,
                    silver=dp.silver,
                    bronze=dp.bronze,
                    participation_points=dp.participation_points,
                    bonus_points=dp.bonus_points,
                    penalties=dp.penalties,
                )
                for dp, _dept in rows
            ],
            DEFAULT_MEDAL_POINTS,
        )
    }
    return [
        MedalRowOut(
            department_id=dp.department_id,
            department_abbr=dept.abbreviation,
            department_name=dept.name,
            position=recomputed[dp.department_id].position,
            gold=dp.gold,
            silver=dp.silver,
            bronze=dp.bronze,
            participation_points=dp.participation_points,
            bonus_points=dp.bonus_points,
            penalties=dp.penalties,
            total_points=recomputed[dp.department_id].total_points,
        )
        for dp, dept in sorted(rows, key=lambda item: recomputed[item[0].department_id].position)
    ]


@router.get("/announcements", response_model=list[AnnouncementOut], tags=["public"])
async def list_announcements(
    db: DbDep, urgent_only: bool = Query(default=False)
) -> list[AnnouncementOut]:
    now = datetime.now(UTC)
    stmt = select(Announcement).where(Announcement.published_at.is_not(None))
    if urgent_only:
        stmt = stmt.where(Announcement.is_urgent.is_(True))
    stmt = stmt.order_by(Announcement.published_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [
        AnnouncementOut.model_validate(a)
        for a in rows
        if a.expires_at is None or a.expires_at > now
    ]


@router.get("/venues", response_model=list[VenueOut], tags=["public"])
async def list_venues(db: DbDep) -> list[VenueOut]:
    rows = (await db.execute(select(Venue).where(Venue.is_active.is_(True)))).scalars().all()
    return [VenueOut.model_validate(v) for v in rows]


@router.get("/sponsors", response_model=list[SponsorOut], tags=["public"])
async def list_sponsors(db: DbDep) -> list[SponsorOut]:
    rows = (
        (
            await db.execute(
                select(Sponsor).where(Sponsor.is_active.is_(True)).order_by(Sponsor.display_order)
            )
        )
        .scalars()
        .all()
    )
    return [SponsorOut.model_validate(s) for s in rows]
