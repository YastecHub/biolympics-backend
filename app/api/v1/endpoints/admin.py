"""Authenticated admin + score-official endpoints."""

from __future__ import annotations

import itertools
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, require_roles
from app.db.base import utcnow
from app.models.auth import User
from app.models.content import Announcement
from app.models.core import Group, GroupMember, Sport
from app.models.enums import FixtureStatus, RoleName
from app.models.fixtures import Fixture, MatchEvent
from app.schemas.admin import (
    AnnouncementCreate,
    CompleteRequest,
    CorrectRequest,
    FixtureCreate,
    FixtureUpdate,
    GenerateFixturesRequest,
    MatchEventCreate,
    PeriodUpdate,
    RescheduleRequest,
    ScoreUpdate,
    StatusChange,
    StatusOut,
)
from app.schemas.public import AnnouncementOut, FixtureOut, MatchEventOut
from app.services.audit import record_audit
from app.services.events import publish_event
from app.services.lifecycle import TransitionError, assert_transition
from app.services.recompute import recompute_group_standings
from app.services.scoring import (
    NotEditableError,
    StaleVersionError,
    apply_score_update,
    ensure_live_state,
    live_payload,
)
from app.services.serializers import fixture_to_out

router = APIRouter(prefix="/admin", tags=["admin"])

ADMINS = (RoleName.SUPER_ADMIN.value, RoleName.TOURNAMENT_ADMIN.value)
SCORERS = (*ADMINS, RoleName.SCORE_OFFICIAL.value)
CONTENT = (*ADMINS, RoleName.CONTENT_MANAGER.value)


async def _load_fixture(db: DbDep, fixture_id: uuid.UUID) -> Fixture:
    fx = (await db.execute(select(Fixture).where(Fixture.id == fixture_id))).scalar_one_or_none()
    if fx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fixture not found")
    return fx


def _assert_assigned(fixture: Fixture, user: User) -> None:
    """Score officials may only act on fixtures assigned to them."""
    if set(user.role_names) & set(ADMINS):
        return
    if fixture.score_official_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not assigned to this fixture")


def _req_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


# --------------------------------------------------------------------------- #
# Fixture management (tournament admins)
# --------------------------------------------------------------------------- #
@router.post(
    "/fixtures",
    response_model=FixtureOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*ADMINS))],
)
async def create_fixture(
    payload: FixtureCreate, db: DbDep, user: CurrentUser, request: Request
) -> FixtureOut:
    sport = (
        await db.execute(select(Sport).where(Sport.id == payload.sport_id))
    ).scalar_one_or_none()
    if sport is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown sport")
    fx = Fixture(
        tournament_id=sport.tournament_id,
        sport_id=sport.id,
        home_team_id=payload.home_team_id,
        away_team_id=payload.away_team_id,
        venue_id=payload.venue_id,
        group_id=payload.group_id,
        stage_id=payload.stage_id,
        score_official_id=payload.score_official_id,
        scheduled_start=payload.scheduled_start,
        scheduled_end=payload.scheduled_end,
        round_name=payload.round_name,
        match_day=payload.match_day,
        label=payload.label,
        published=payload.published,
        status=FixtureStatus.SCHEDULED if payload.published else FixtureStatus.DRAFT,
    )
    db.add(fx)
    await db.flush()
    fx.live_state = ensure_live_state(fx)
    await record_audit(
        db,
        action="fixture.created",
        entity_type="fixture",
        entity_id=fx.id,
        actor_id=user.id,
        actor_email=user.email,
        request_id=_req_id(request),
    )
    await db.commit()
    return fixture_to_out(await _load_fixture(db, fx.id))


@router.patch(
    "/fixtures/{fixture_id}",
    response_model=FixtureOut,
    dependencies=[Depends(require_roles(*ADMINS))],
)
async def update_fixture(
    fixture_id: uuid.UUID,
    payload: FixtureUpdate,
    db: DbDep,
    user: CurrentUser,
    request: Request,
) -> FixtureOut:
    fx = await _load_fixture(db, fixture_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(fx, key, value)
    await record_audit(
        db,
        action="fixture.updated",
        entity_type="fixture",
        entity_id=fx.id,
        actor_id=user.id,
        actor_email=user.email,
        changes=_jsonable(changes),
        request_id=_req_id(request),
    )
    await db.commit()
    return fixture_to_out(await _load_fixture(db, fx.id))


@router.delete(
    "/fixtures/{fixture_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(require_roles(RoleName.SUPER_ADMIN.value, RoleName.TOURNAMENT_ADMIN.value))
    ],
)
async def delete_fixture(
    fixture_id: uuid.UUID, db: DbDep, user: CurrentUser, request: Request
) -> None:
    fx = await _load_fixture(db, fixture_id)
    await record_audit(
        db,
        action="fixture.deleted",
        entity_type="fixture",
        entity_id=fx.id,
        actor_id=user.id,
        actor_email=user.email,
        request_id=_req_id(request),
    )
    await db.delete(fx)
    await db.commit()


@router.post(
    "/fixtures/generate",
    response_model=list[FixtureOut],
    dependencies=[Depends(require_roles(*ADMINS))],
)
async def generate_fixtures(
    payload: GenerateFixturesRequest, db: DbDep, user: CurrentUser, request: Request
) -> list[FixtureOut]:
    sport = (
        await db.execute(select(Sport).where(Sport.id == payload.sport_id))
    ).scalar_one_or_none()
    if sport is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown sport")

    groups_q = select(Group).where(Group.sport_id == sport.id)
    if payload.group_id:
        groups_q = groups_q.where(Group.id == payload.group_id)
    groups = (await db.execute(groups_q)).scalars().all()

    created: list[Fixture] = []
    for group in groups:
        team_ids = (
            (await db.execute(select(GroupMember.team_id).where(GroupMember.group_id == group.id)))
            .scalars()
            .all()
        )
        if payload.mode == "round_robin":
            pairs = list(itertools.combinations(team_ids, 2))
        elif payload.mode == "knockout":
            pairs = list(zip(team_ids[0::2], team_ids[1::2], strict=False))
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "mode must be round_robin|knockout")

        for md, (home, away) in enumerate(pairs, start=1):
            fx = Fixture(
                tournament_id=sport.tournament_id,
                sport_id=sport.id,
                group_id=group.id,
                home_team_id=home,
                away_team_id=away,
                match_day=md if payload.mode == "round_robin" else None,
                round_name=None if payload.mode == "round_robin" else "Knockout",
                status=FixtureStatus.SCHEDULED,
                published=True,
            )
            db.add(fx)
            await db.flush()
            fx.live_state = ensure_live_state(fx)
            created.append(fx)

    await record_audit(
        db,
        action="fixtures.generated",
        entity_type="sport",
        entity_id=sport.id,
        actor_id=user.id,
        actor_email=user.email,
        changes={"mode": payload.mode, "count": len(created)},
        request_id=_req_id(request),
    )
    created_ids = [f.id for f in created]
    await db.commit()
    return [fixture_to_out(await _load_fixture(db, fid)) for fid in created_ids]


# --------------------------------------------------------------------------- #
# Live control (score officials + admins)
# --------------------------------------------------------------------------- #
@router.post(
    "/fixtures/{fixture_id}/start",
    response_model=StatusOut,
    dependencies=[Depends(require_roles(*SCORERS))],
)
async def start_fixture(
    fixture_id: uuid.UUID, db: DbDep, user: CurrentUser, request: Request
) -> StatusOut:
    fx = await _load_fixture(db, fixture_id)
    _assert_assigned(fx, user)
    try:
        assert_transition(fx.status, FixtureStatus.LIVE, user.role_names)
    except TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    fx.status = FixtureStatus.LIVE
    fx.actual_start = utcnow()
    fx.version += 1
    ensure_live_state(fx).version = fx.version
    await record_audit(
        db,
        action="fixture.started",
        entity_type="fixture",
        entity_id=fx.id,
        actor_id=user.id,
        actor_email=user.email,
        request_id=_req_id(request),
    )
    await db.commit()
    await publish_event(
        "fixture.started",
        live_payload(fx),
        fixture_id=fx.id,
        sport=fx.sport.slug,
        version=fx.version,
    )
    return StatusOut(status=fx.status, version=fx.version)


@router.post(
    "/fixtures/{fixture_id}/score",
    response_model=StatusOut,
    dependencies=[Depends(require_roles(*SCORERS))],
)
async def update_score(
    fixture_id: uuid.UUID,
    payload: ScoreUpdate,
    db: DbDep,
    user: CurrentUser,
    request: Request,
) -> StatusOut:
    fx = await _load_fixture(db, fixture_id)
    _assert_assigned(fx, user)
    try:
        apply_score_update(fx, payload)
    except StaleVersionError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "stale_version",
                "message": "Score changed since you last loaded it. Refresh and retry.",
                "current_version": exc.current,
            },
        ) from exc
    except NotEditableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await record_audit(
        db,
        action="fixture.score_updated",
        entity_type="fixture",
        entity_id=fx.id,
        actor_id=user.id,
        actor_email=user.email,
        changes={"home": fx.live_state.home_score, "away": fx.live_state.away_score},
        request_id=_req_id(request),
    )
    await db.commit()
    await publish_event(
        "fixture.score_updated",
        live_payload(fx),
        fixture_id=fx.id,
        sport=fx.sport.slug,
        version=fx.version,
    )
    return StatusOut(status=fx.status, version=fx.version)


@router.post(
    "/fixtures/{fixture_id}/events",
    response_model=MatchEventOut,
    dependencies=[Depends(require_roles(*SCORERS))],
)
async def add_event(
    fixture_id: uuid.UUID,
    payload: MatchEventCreate,
    db: DbDep,
    user: CurrentUser,
    request: Request,
) -> MatchEventOut:
    fx = await _load_fixture(db, fixture_id)
    _assert_assigned(fx, user)
    event = MatchEvent(
        fixture_id=fx.id,
        type=payload.type,
        team_id=payload.team_id,
        participant_id=payload.participant_id,
        minute=payload.minute,
        period=payload.period,
        detail=payload.detail,
        created_at=utcnow(),
        created_by_id=user.id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    await publish_event(
        "fixture.event_added",
        {"type": event.type.value, "minute": event.minute, "detail": event.detail},
        fixture_id=fx.id,
        sport=fx.sport.slug,
        version=fx.version,
    )
    return MatchEventOut.model_validate(event)


@router.post(
    "/fixtures/{fixture_id}/period",
    response_model=StatusOut,
    dependencies=[Depends(require_roles(*SCORERS))],
)
async def set_period(
    fixture_id: uuid.UUID,
    payload: PeriodUpdate,
    db: DbDep,
    user: CurrentUser,
    request: Request,
) -> StatusOut:
    fx = await _load_fixture(db, fixture_id)
    _assert_assigned(fx, user)
    if payload.expected_version != fx.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "Stale version")
    state = ensure_live_state(fx)
    state.period = payload.period
    if payload.current_period_number is not None:
        state.current_period_number = payload.current_period_number
    if payload.clock_text is not None:
        state.clock_text = payload.clock_text
    fx.version += 1
    state.version = fx.version
    await db.commit()
    await publish_event(
        "fixture.period_updated",
        live_payload(fx),
        fixture_id=fx.id,
        sport=fx.sport.slug,
        version=fx.version,
    )
    return StatusOut(status=fx.status, version=fx.version)


async def _change_status(
    db: DbDep,
    fx: Fixture,
    user: User,
    target: FixtureStatus,
    event_type: str,
    request: Request,
    reason: str | None = None,
) -> StatusOut:
    try:
        assert_transition(fx.status, target, user.role_names)
    except TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    fx.status = target
    fx.version += 1
    if fx.live_state:
        fx.live_state.version = fx.version
    await record_audit(
        db,
        action=event_type,
        entity_type="fixture",
        entity_id=fx.id,
        actor_id=user.id,
        actor_email=user.email,
        reason=reason,
        request_id=_req_id(request),
    )
    await db.commit()
    await publish_event(
        event_type,
        live_payload(fx),
        fixture_id=fx.id,
        sport=fx.sport.slug,
        version=fx.version,
    )
    return StatusOut(status=fx.status, version=fx.version)


@router.post(
    "/fixtures/{fixture_id}/pause",
    response_model=StatusOut,
    dependencies=[Depends(require_roles(*SCORERS))],
)
async def pause_fixture(
    fixture_id: uuid.UUID, db: DbDep, user: CurrentUser, request: Request
) -> StatusOut:
    fx = await _load_fixture(db, fixture_id)
    _assert_assigned(fx, user)
    return await _change_status(db, fx, user, FixtureStatus.PAUSED, "fixture.paused", request)


@router.post(
    "/fixtures/{fixture_id}/resume",
    response_model=StatusOut,
    dependencies=[Depends(require_roles(*SCORERS))],
)
async def resume_fixture(
    fixture_id: uuid.UUID, db: DbDep, user: CurrentUser, request: Request
) -> StatusOut:
    fx = await _load_fixture(db, fixture_id)
    _assert_assigned(fx, user)
    return await _change_status(db, fx, user, FixtureStatus.LIVE, "fixture.resumed", request)


@router.post(
    "/fixtures/{fixture_id}/complete",
    response_model=StatusOut,
    dependencies=[Depends(require_roles(*SCORERS))],
)
async def complete_fixture(
    fixture_id: uuid.UUID,
    payload: CompleteRequest,
    db: DbDep,
    user: CurrentUser,
    request: Request,
) -> StatusOut:
    fx = await _load_fixture(db, fixture_id)
    _assert_assigned(fx, user)
    if payload.expected_version != fx.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "Stale version")
    try:
        assert_transition(fx.status, FixtureStatus.COMPLETED, user.role_names)
    except TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    fx.status = FixtureStatus.COMPLETED
    fx.actual_end = utcnow()
    fx.version += 1
    if fx.live_state:
        fx.live_state.version = fx.version
    await record_audit(
        db,
        action="fixture.completed",
        entity_type="fixture",
        entity_id=fx.id,
        actor_id=user.id,
        actor_email=user.email,
        request_id=_req_id(request),
    )
    if fx.group_id:
        await recompute_group_standings(db, fx.sport_id)
    await db.commit()
    await publish_event(
        "fixture.completed",
        live_payload(fx),
        fixture_id=fx.id,
        sport=fx.sport.slug,
        version=fx.version,
    )
    if fx.group_id:
        await publish_event("standings.updated", {"sport": fx.sport.slug})
    return StatusOut(status=fx.status, version=fx.version)


# --------------------------------------------------------------------------- #
# Corrections & rescheduling (admins only)
# --------------------------------------------------------------------------- #
@router.post(
    "/fixtures/{fixture_id}/reopen",
    response_model=StatusOut,
    dependencies=[Depends(require_roles(*ADMINS))],
)
async def reopen_fixture(
    fixture_id: uuid.UUID,
    payload: StatusChange,
    db: DbDep,
    user: CurrentUser,
    request: Request,
) -> StatusOut:
    fx = await _load_fixture(db, fixture_id)
    return await _change_status(
        db,
        fx,
        user,
        FixtureStatus.UNDER_REVIEW,
        "fixture.reopened",
        request,
        reason=payload.reason,
    )


@router.post(
    "/fixtures/{fixture_id}/correct",
    response_model=StatusOut,
    dependencies=[Depends(require_roles(*ADMINS))],
)
async def correct_fixture(
    fixture_id: uuid.UUID,
    payload: CorrectRequest,
    db: DbDep,
    user: CurrentUser,
    request: Request,
) -> StatusOut:
    fx = await _load_fixture(db, fixture_id)
    state = ensure_live_state(fx)
    before = {"home": state.home_score, "away": state.away_score}
    if payload.home_score is not None:
        state.home_score = payload.home_score
    if payload.away_score is not None:
        state.away_score = payload.away_score
    fx.status = FixtureStatus.COMPLETED
    fx.version += 1
    state.version = fx.version
    await record_audit(
        db,
        action="fixture.corrected",
        entity_type="fixture",
        entity_id=fx.id,
        actor_id=user.id,
        actor_email=user.email,
        reason=payload.reason,
        changes={"before": before, "after": {"home": state.home_score, "away": state.away_score}},
        request_id=_req_id(request),
    )
    if fx.group_id:
        await recompute_group_standings(db, fx.sport_id)
    await db.commit()
    await publish_event(
        "fixture.corrected",
        live_payload(fx),
        fixture_id=fx.id,
        sport=fx.sport.slug,
        version=fx.version,
    )
    if fx.group_id:
        await publish_event("standings.updated", {"sport": fx.sport.slug})
    return StatusOut(status=fx.status, version=fx.version, message="Result corrected")


@router.post(
    "/fixtures/{fixture_id}/postpone",
    response_model=StatusOut,
    dependencies=[Depends(require_roles(*ADMINS))],
)
async def postpone_fixture(
    fixture_id: uuid.UUID,
    payload: StatusChange,
    db: DbDep,
    user: CurrentUser,
    request: Request,
) -> StatusOut:
    fx = await _load_fixture(db, fixture_id)
    return await _change_status(
        db,
        fx,
        user,
        FixtureStatus.POSTPONED,
        "fixture.postponed",
        request,
        reason=payload.reason,
    )


@router.post(
    "/fixtures/{fixture_id}/cancel",
    response_model=StatusOut,
    dependencies=[Depends(require_roles(*ADMINS))],
)
async def cancel_fixture(
    fixture_id: uuid.UUID,
    payload: StatusChange,
    db: DbDep,
    user: CurrentUser,
    request: Request,
) -> StatusOut:
    fx = await _load_fixture(db, fixture_id)
    had_group = fx.group_id is not None
    sport_id = fx.sport_id
    result = await _change_status(
        db,
        fx,
        user,
        FixtureStatus.CANCELLED,
        "fixture.cancelled",
        request,
        reason=payload.reason,
    )
    if had_group:
        await recompute_group_standings(db, sport_id)
        await db.commit()
    return result


@router.post(
    "/fixtures/{fixture_id}/reschedule",
    response_model=FixtureOut,
    dependencies=[Depends(require_roles(*ADMINS))],
)
async def reschedule_fixture(
    fixture_id: uuid.UUID,
    payload: RescheduleRequest,
    db: DbDep,
    user: CurrentUser,
    request: Request,
) -> FixtureOut:
    fx = await _load_fixture(db, fixture_id)
    if payload.scheduled_start is not None:
        fx.scheduled_start = payload.scheduled_start
    if payload.scheduled_end is not None:
        fx.scheduled_end = payload.scheduled_end
    if payload.venue_id is not None:
        fx.venue_id = payload.venue_id
    await record_audit(
        db,
        action="fixture.rescheduled",
        entity_type="fixture",
        entity_id=fx.id,
        actor_id=user.id,
        actor_email=user.email,
        reason=payload.reason,
        request_id=_req_id(request),
    )
    sport_slug = fx.sport.slug
    await db.commit()
    fx = await _load_fixture(db, fixture_id)
    await publish_event(
        "schedule.changed",
        {
            "fixture_id": str(fx.id),
            "scheduled_start": fx.scheduled_start.isoformat() if fx.scheduled_start else None,
        },
        fixture_id=fx.id,
        sport=sport_slug,
    )
    return fixture_to_out(fx)


# --------------------------------------------------------------------------- #
# Announcements (content managers + admins)
# --------------------------------------------------------------------------- #
@router.post(
    "/announcements",
    response_model=AnnouncementOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*CONTENT))],
)
async def create_announcement(
    payload: AnnouncementCreate, db: DbDep, user: CurrentUser, request: Request
) -> AnnouncementOut:
    from app.services.repo import current_tournament_id

    ann = Announcement(
        tournament_id=await current_tournament_id(db),
        title=payload.title,
        body=payload.body,
        type=payload.type,
        is_urgent=payload.is_urgent,
        sport_id=payload.sport_id,
        department_id=payload.department_id,
        fixture_id=payload.fixture_id,
        expires_at=payload.expires_at,
        created_by_id=user.id,
        published_at=utcnow() if payload.publish else None,
    )
    db.add(ann)
    await record_audit(
        db,
        action="announcement.published",
        entity_type="announcement",
        actor_id=user.id,
        actor_email=user.email,
        request_id=_req_id(request),
    )
    await db.commit()
    await db.refresh(ann)
    if payload.publish:
        await publish_event(
            "announcement.published",
            {"title": ann.title, "is_urgent": ann.is_urgent, "id": str(ann.id)},
        )
    return AnnouncementOut.model_validate(ann)


def _jsonable(data: dict) -> dict:
    return {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in data.items()}
