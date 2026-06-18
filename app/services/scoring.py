"""Apply version-guarded score updates to a fixture's live state.

Optimistic concurrency: the caller must send the version it last saw. If another
official has written since, we raise StaleVersionError (HTTP 409) so no update is
silently overwritten.
"""

from __future__ import annotations

from app.db.base import utcnow
from app.models.enums import LIVE_EDITABLE_STATUSES
from app.models.fixtures import Fixture, LiveMatchState
from app.schemas.admin import ScoreUpdate


class StaleVersionError(Exception):
    def __init__(self, current: int, expected: int) -> None:
        self.current = current
        self.expected = expected
        super().__init__(f"stale version: expected {expected}, current {current}")


class NotEditableError(Exception):
    pass


def ensure_live_state(fixture: Fixture) -> LiveMatchState:
    if fixture.live_state is None:
        fixture.live_state = LiveMatchState(fixture_id=fixture.id)
    return fixture.live_state


def apply_score_update(fixture: Fixture, payload: ScoreUpdate) -> LiveMatchState:
    if fixture.status not in LIVE_EDITABLE_STATUSES:
        raise NotEditableError(f"Fixture status {fixture.status.value} does not allow score edits")
    if payload.expected_version != fixture.version:
        raise StaleVersionError(fixture.version, payload.expected_version)

    state = ensure_live_state(fixture)

    if payload.home_score is not None:
        state.home_score = payload.home_score
    if payload.away_score is not None:
        state.away_score = payload.away_score
    if payload.home_delta is not None:
        state.home_score = max(0, state.home_score + payload.home_delta)
    if payload.away_delta is not None:
        state.away_score = max(0, state.away_score + payload.away_delta)
    if payload.period is not None:
        state.period = payload.period
    if payload.clock_text is not None:
        state.clock_text = payload.clock_text
    if payload.home_sets is not None:
        state.home_sets = payload.home_sets
    if payload.away_sets is not None:
        state.away_sets = payload.away_sets
    if payload.extra is not None:
        merged = dict(state.extra or {})
        merged.update(payload.extra)
        state.extra = merged

    now = utcnow()
    state.last_updated_at = now
    fixture.version += 1
    state.version = fixture.version
    return state


def live_payload(fixture: Fixture) -> dict:
    state = fixture.live_state
    return {
        "home_score": state.home_score if state else 0,
        "away_score": state.away_score if state else 0,
        "home_sets": state.home_sets if state else 0,
        "away_sets": state.away_sets if state else 0,
        "status": fixture.status.value,
        "period": state.period if state else None,
        "clock": state.clock_text if state else None,
        "extra": state.extra if state else {},
    }
