"""Idempotent tournament seeding.

Re-running drops the existing current tournament (cascade) and rebuilds it, so
`make seed` is safe to repeat. Admin users/roles are preserved across reseeds.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.auth import Role, User, UserRole
from app.models.content import Announcement, Sponsor
from app.models.core import (
    Department,
    Group,
    GroupMember,
    Sport,
    SportRule,
    Team,
    Tournament,
    Venue,
)
from app.models.enums import AnnouncementType, FixtureStatus, MedalKind, RoleName
from app.models.fixtures import Fixture, LiveMatchState
from app.models.standings import DepartmentPoints, Medal
from app.seeds import data
from app.services.medal_table import MedalTally, compute_medal_table
from app.services.recompute import recompute_group_standings

log = structlog.get_logger("seed")
LAGOS = ZoneInfo("Africa/Lagos")


def _lagos_to_utc(day: str, hour: int, minute: int) -> datetime:
    y, m, d = (int(x) for x in day.split("-"))
    return datetime(y, m, d, hour, minute, tzinfo=LAGOS).astimezone(UTC)


async def ensure_roles(db: AsyncSession) -> dict[str, Role]:
    out: dict[str, Role] = {}
    for rn in RoleName:
        role = (await db.execute(select(Role).where(Role.name == rn))).scalar_one_or_none()
        if role is None:
            role = Role(name=rn, description=rn.value.replace("_", " ").title())
            db.add(role)
            await db.flush()
        out[rn.value] = role
    return out


_PLACEHOLDER_PASSWORD = "ChangeMe!2026"


async def _ensure_super_admin(db: AsyncSession, roles: dict[str, Role]) -> bool:
    """Create the SUPER_ADMIN from INITIAL_ADMIN_EMAIL/PASSWORD if it doesn't
    already exist. Refuses the placeholder password in production."""
    email = settings.initial_admin_email.strip().lower()
    password = settings.initial_admin_password
    if not email or not password:
        log.warning("seed.skip_admin", reason="INITIAL_ADMIN_EMAIL/PASSWORD not set")
        return False
    if settings.is_production and password == _PLACEHOLDER_PASSWORD:
        log.warning("seed.skip_admin", reason="refusing placeholder admin password in production")
        return False

    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        return False
    user = User(
        email=email,
        full_name="Super Admin",
        hashed_password=hash_password(password),
        is_active=True,
        is_dev_account=False,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=roles[RoleName.SUPER_ADMIN.value].id))
    log.info("seed.super_admin_created", email=email)
    return True


async def seed(db: AsyncSession, with_demo: bool = True) -> dict:
    roles = await ensure_roles(db)

    # Fresh tournament each run.
    existing = (
        await db.execute(select(Tournament).where(Tournament.slug == data.TOURNAMENT["slug"]))
    ).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.flush()

    t = Tournament(
        name=data.TOURNAMENT["name"],
        public_brand=data.TOURNAMENT["public_brand"],
        slug=data.TOURNAMENT["slug"],
        timezone=data.TOURNAMENT["timezone"],
        start_date=date.fromisoformat(data.TOURNAMENT["start_date"]),
        end_date=date.fromisoformat(data.TOURNAMENT["end_date"]),
        description=data.TOURNAMENT["description"],
        medal_points=data.TOURNAMENT["medal_points"],
        is_current=True,
    )
    # Only one current tournament.
    for other in (await db.execute(select(Tournament))).scalars().all():
        other.is_current = False
    db.add(t)
    await db.flush()

    # Departments
    depts: dict[str, Department] = {}
    for name, abbr, short, primary, secondary, logo_url in data.DEPARTMENTS:
        d = Department(
            tournament_id=t.id,
            name=name,
            abbreviation=abbr,
            short_name=short,
            slug=abbr.lower().replace(" ", "-"),
            logo_url=logo_url,
            primary_color=primary,
            secondary_color=secondary,
            is_active=True,
        )
        db.add(d)
        depts[abbr] = d
    await db.flush()

    # Venues
    venues: dict[str, Venue] = {}
    for vname, addr in data.VENUES:
        v = Venue(tournament_id=t.id, name=vname, address=addr, is_active=True)
        db.add(v)
        venues[vname] = v
    await db.flush()

    # Sports (+ football rules)
    sports: dict[str, Sport] = {}
    for (
        name,
        slug,
        icon,
        gender,
        fmt,
        scoring,
        kind,
        table,
        bracket,
        live,
        timing,
        periods,
        order,
    ) in data.SPORTS:
        s = Sport(
            tournament_id=t.id,
            name=name,
            slug=slug,
            icon=icon,
            gender_category=gender,
            competition_format=fmt,
            scoring_type=scoring,
            participant_kind=kind,
            requires_table=table,
            requires_bracket=bracket,
            supports_live=live,
            uses_timing=timing,
            periods=periods,
            display_order=order,
            is_active=True,
        )
        db.add(s)
        sports[slug] = s
    await db.flush()
    db.add(
        SportRule(sport_id=sports["male-football"].id, points_win=3, points_draw=1, points_loss=0)
    )
    if "volleyball" in sports:
        db.add(SportRule(sport_id=sports["volleyball"].id, sets_to_win=3))
    await db.flush()

    # Teams + groups for sports with draws
    teams: dict[tuple[str, str], Team] = {}
    groups: dict[tuple[str, str], Group] = {}
    for sport_slug, draw in data.DRAWS.items():
        sport = sports[sport_slug]
        for group_name, abbrs in draw.items():
            grp = Group(sport_id=sport.id, name=group_name)
            db.add(grp)
            await db.flush()
            groups[(sport_slug, group_name)] = grp
            for abbr in abbrs:
                team = teams.get((sport_slug, abbr))
                if team is None:
                    team = Team(
                        tournament_id=t.id,
                        sport_id=sport.id,
                        department_id=depts[abbr].id,
                        display_name=depts[abbr].short_name,
                    )
                    db.add(team)
                    await db.flush()
                    teams[(sport_slug, abbr)] = team
                db.add(GroupMember(group_id=grp.id, team_id=team.id))
    await db.flush()

    fixtures_created = 0

    # Male football round-robin fixtures with the official match-day schedule.
    mf = sports["male-football"]
    for group_name, by_day in data.MALE_FOOTBALL_FIXTURES.items():
        grp = groups[("male-football", group_name)]
        for match_day, pairings in by_day.items():
            day, hour, minute, venue_name = data.MALE_FOOTBALL_SCHEDULE[match_day]
            start = _lagos_to_utc(day, hour, minute)
            for idx, (home_abbr, away_abbr) in enumerate(pairings):
                match_time = data.MALE_FOOTBALL_MATCH_TIMES.get(
                    (match_day, home_abbr, away_abbr)
                ) or data.MALE_FOOTBALL_MATCH_TIMES.get((home_abbr, away_abbr))
                match_start = _lagos_to_utc(*match_time) if match_time else start + timedelta(hours=idx * 2)
                fx = Fixture(
                    tournament_id=t.id,
                    sport_id=mf.id,
                    group_id=grp.id,
                    home_team_id=teams[("male-football", home_abbr)].id,
                    away_team_id=teams[("male-football", away_abbr)].id,
                    venue_id=venues[venue_name].id if venue_name else None,
                    scheduled_start=match_start,
                    scheduled_end=match_start + timedelta(hours=1),
                    match_day=match_day,
                    round_name=f"{group_name} — MD{match_day}",
                    status=FixtureStatus.SCHEDULED,
                    published=True,
                )
                db.add(fx)
                await db.flush()
                fixtures_created += 1

                # Live state / scores are only attached for demo data. In a real
                # seed a fixture has no score until an official records one.
                if not with_demo:
                    continue
                fx.live_state = LiveMatchState(fixture_id=fx.id)
                if group_name == "Group A" and match_day == 1:
                    # Two completed MD1 results so standings populate.
                    if (home_abbr, away_abbr) == ("BTN", "CBG"):
                        _finalize(fx, 2, 1)
                    elif (home_abbr, away_abbr) == ("MSM", "MIC"):
                        _finalize(fx, 1, 1)
                if (
                    group_name == "Group B"
                    and match_day == 1
                    and (home_abbr, away_abbr) == ("ZLY", "BCH")
                ):
                    # One live demo fixture.
                    fx.status = FixtureStatus.LIVE
                    fx.actual_start = datetime.now(UTC)
                    fx.version = 3
                    fx.live_state.home_score = 1
                    fx.live_state.away_score = 0
                    fx.live_state.period = "SECOND_HALF"
                    fx.live_state.clock_text = "63:00"
                    fx.live_state.version = 3
                    fx.live_state.last_updated_at = datetime.now(UTC)
    await db.flush()

    # Standalone scheduled events (knockouts, races) — often TBD.
    for sport_slug, label, day, sh, sm, eh, em, venue_name in data.SCHEDULE_EVENTS:
        sport = sports[sport_slug]
        start = _lagos_to_utc(day, sh, sm) if day and sh is not None else None
        end = _lagos_to_utc(day, eh, em) if day and eh is not None else None
        fx = Fixture(
            tournament_id=t.id,
            sport_id=sport.id,
            round_name=label,
            scheduled_start=start,
            scheduled_end=end,
            venue_id=venues[venue_name].id if venue_name else None,
            status=FixtureStatus.SCHEDULED,
            published=True,
        )
        db.add(fx)
        await db.flush()
        # No live_state: these are scheduled, with no score until played.
        fixtures_created += 1
    await db.flush()

    # Build the (empty until played) group tables.
    await recompute_group_standings(db, mf.id)

    # Official podiums. These are real tournament progress, so keep them in
    # both live and demo seeds while football demo scores remain demo-only.
    medal_kinds = {
        "GOLD": MedalKind.GOLD,
        "SILVER": MedalKind.SILVER,
        "BRONZE": MedalKind.BRONZE,
    }
    medal_counts = {abbr: {"gold": 0, "silver": 0, "bronze": 0} for abbr in depts}
    for abbr, kind in data.LUDO_MEDALS:
        medal_counts[abbr][kind.lower()] += 1
        db.add(
            Medal(
                tournament_id=t.id,
                department_id=depts[abbr].id,
                sport_id=sports["ludo"].id,
                kind=medal_kinds[kind],
                label="Ludo",
            )
        )
    for abbr, kind, label in data.MARATHON_MEDALS:
        medal_counts[abbr][kind.lower()] += 1
        db.add(
            Medal(
                tournament_id=t.id,
                department_id=depts[abbr].id,
                sport_id=sports["marathon"].id,
                kind=medal_kinds[kind],
                label=label,
            )
        )

    medal_rows = compute_medal_table(
        [
            MedalTally(
                department_id=dept.id,
                gold=medal_counts[abbr]["gold"],
                silver=medal_counts[abbr]["silver"],
                bronze=medal_counts[abbr]["bronze"],
            )
            for abbr, dept in depts.items()
            if sum(medal_counts[abbr].values()) > 0
        ],
        t.medal_points,
    )
    for row in medal_rows:
        db.add(
            DepartmentPoints(
                tournament_id=t.id,
                department_id=row.department_id,
                gold=row.gold,
                silver=row.silver,
                bronze=row.bronze,
                participation_points=row.participation_points,
                bonus_points=row.bonus_points,
                penalties=row.penalties,
                total_points=row.total_points,
                position=row.position,
                breakdown=row.breakdown,
            )
        )

    # Announcements + sponsors are sample content — demo only. A real tournament
    # adds these through the admin UI.
    if with_demo:
        for a in data.ANNOUNCEMENTS:
            db.add(
                Announcement(
                    tournament_id=t.id,
                    title=a["title"],
                    body=a["body"],
                    type=AnnouncementType(a["type"]),
                    is_urgent=a["is_urgent"],
                    published_at=datetime.now(UTC),
                )
            )
        for sp in data.SPONSORS:
            db.add(
                Sponsor(
                    tournament_id=t.id,
                    name=sp["name"],
                    tier=sp["tier"],
                    display_order=sp["display_order"],
                    is_active=True,
                )
            )

    admin_created = await _ensure_super_admin(db, roles)
    await db.commit()

    summary = {
        "tournament": t.name,
        "mode": "demo" if with_demo else "live",
        "departments": len(depts),
        "sports": len(sports),
        "venues": len(venues),
        "fixtures": fixtures_created,
        "super_admin": settings.initial_admin_email if admin_created else "(exists / skipped)",
    }
    log.info("seed.complete", **summary)
    return summary


def _finalize(fx: Fixture, home: int, away: int) -> None:
    fx.status = FixtureStatus.COMPLETED
    fx.actual_start = fx.scheduled_start or datetime.now(UTC)
    fx.actual_end = fx.actual_start + timedelta(hours=2)
    fx.version = 5
    fx.live_state.home_score = home
    fx.live_state.away_score = away
    fx.live_state.version = 5
    fx.live_state.last_updated_at = datetime.now(UTC)
