"""Fixture status state machine.

Defines which transitions are valid and who may perform them. A completed match
cannot be edited by a score official; only a tournament/super admin can reopen,
correct or cancel a terminal fixture.
"""

from __future__ import annotations

from app.models.enums import FixtureStatus as S
from app.models.enums import RoleName as R

# Allowed transitions: from-status -> set of to-statuses
TRANSITIONS: dict[S, set[S]] = {
    S.DRAFT: {S.SCHEDULED, S.CANCELLED},
    S.SCHEDULED: {S.WARMUP, S.LIVE, S.DELAYED, S.POSTPONED, S.CANCELLED, S.WALKOVER},
    S.WARMUP: {S.LIVE, S.DELAYED, S.POSTPONED, S.CANCELLED, S.WALKOVER},
    S.LIVE: {S.HALF_TIME, S.PERIOD_BREAK, S.PAUSED, S.COMPLETED, S.UNDER_REVIEW},
    S.HALF_TIME: {S.LIVE, S.PERIOD_BREAK, S.PAUSED},
    S.PERIOD_BREAK: {S.LIVE, S.PAUSED},
    S.PAUSED: {S.LIVE, S.HALF_TIME, S.POSTPONED, S.CANCELLED},
    S.DELAYED: {S.SCHEDULED, S.LIVE, S.POSTPONED, S.CANCELLED},
    S.POSTPONED: {S.SCHEDULED, S.CANCELLED},
    S.UNDER_REVIEW: {S.LIVE, S.COMPLETED, S.CANCELLED},
    # Terminal — only admins reopen these (see ADMIN_ONLY_FROM).
    S.COMPLETED: {S.UNDER_REVIEW, S.LIVE},
    S.WALKOVER: {S.UNDER_REVIEW},
    S.CANCELLED: {S.SCHEDULED},
}

# Transitions that require TOURNAMENT_ADMIN or SUPER_ADMIN regardless of role.
ADMIN_ONLY_FROM: set[S] = {S.COMPLETED, S.WALKOVER, S.CANCELLED}

ADMIN_ROLES = {R.SUPER_ADMIN.value, R.TOURNAMENT_ADMIN.value}


class TransitionError(Exception):
    """Raised when a requested status transition is not allowed."""


def can_transition(current: S, target: S) -> bool:
    return target in TRANSITIONS.get(current, set())


def assert_transition(current: S, target: S, roles: list[str]) -> None:
    """Validate a transition for the actor's roles. Raises TransitionError."""
    if current == target:
        return
    if not can_transition(current, target):
        raise TransitionError(f"Cannot move fixture from {current.value} to {target.value}.")
    if current in ADMIN_ONLY_FROM and not (set(roles) & ADMIN_ROLES):
        raise TransitionError(f"Only a tournament admin may move a {current.value} fixture.")
