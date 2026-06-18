"""Map ORM objects to public response schemas, computing TBD flags."""

from __future__ import annotations

from app.models.core import Team
from app.models.fixtures import Fixture
from app.schemas.public import FixtureOut, LiveStateOut, TeamRef


def team_ref(team: Team | None) -> TeamRef | None:
    if team is None:
        return None
    dept = team.department
    return TeamRef(
        id=team.id,
        department_abbr=dept.abbreviation if dept else None,
        department_name=dept.name if dept else None,
        display_name=team.display_name,
        logo_url=dept.logo_url if dept else None,
        primary_color=dept.primary_color if dept else None,
    )


def fixture_to_out(fx: Fixture) -> FixtureOut:
    live = None
    if fx.live_state is not None:
        live = LiveStateOut.model_validate(fx.live_state)
    return FixtureOut(
        id=fx.id,
        sport_slug=fx.sport.slug,
        sport_name=fx.sport.name,
        status=fx.status,
        round_name=fx.round_name,
        match_day=fx.match_day,
        group_name=fx.group.name if fx.group else None,
        home=team_ref(fx.home_team),
        away=team_ref(fx.away_team),
        venue_name=fx.venue.name if fx.venue else None,
        venue_tbd=fx.venue_id is None,
        scheduled_start=fx.scheduled_start,
        scheduled_end=fx.scheduled_end,
        time_tbd=fx.scheduled_start is None,
        published=fx.published,
        version=fx.version,
        live=live,
    )
