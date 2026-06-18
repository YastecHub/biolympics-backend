"""Unit tests for the fixture status state machine."""

from __future__ import annotations

import pytest

from app.models.enums import FixtureStatus as S
from app.models.enums import RoleName
from app.services.lifecycle import TransitionError, assert_transition, can_transition

OFFICIAL = [RoleName.SCORE_OFFICIAL.value]
ADMIN = [RoleName.TOURNAMENT_ADMIN.value]


def test_normal_workflow_allowed():
    assert can_transition(S.DRAFT, S.SCHEDULED)
    assert can_transition(S.SCHEDULED, S.LIVE)
    assert can_transition(S.LIVE, S.COMPLETED)


def test_invalid_transition_rejected():
    assert not can_transition(S.DRAFT, S.LIVE)
    with pytest.raises(TransitionError):
        assert_transition(S.DRAFT, S.LIVE, ADMIN)


def test_official_cannot_reopen_completed():
    # COMPLETED -> UNDER_REVIEW is a valid edge, but only for admins.
    with pytest.raises(TransitionError):
        assert_transition(S.COMPLETED, S.UNDER_REVIEW, OFFICIAL)


def test_admin_can_reopen_completed():
    assert_transition(S.COMPLETED, S.UNDER_REVIEW, ADMIN)  # no raise


def test_same_status_is_noop():
    assert_transition(S.LIVE, S.LIVE, OFFICIAL)  # no raise
