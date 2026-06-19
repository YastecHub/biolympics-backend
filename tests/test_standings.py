"""Unit tests for the pure standings and medal-table engines."""

from __future__ import annotations

import uuid

from app.services.medal_table import MedalTally, compute_medal_table
from app.services.standings import MatchResult, PointsRules, compute_table

A = uuid.UUID(int=1)
B = uuid.UUID(int=2)
C = uuid.UUID(int=3)
D = uuid.UUID(int=4)


def test_win_draw_loss_points():
    results = [
        MatchResult(A, B, 2, 1),  # A win
        MatchResult(C, D, 0, 0),  # draw
    ]
    table = compute_table([A, B, C, D], results)
    by_id = {r.team_id: r for r in table}
    assert by_id[A].points(PointsRules()) == 3
    assert by_id[B].points(PointsRules()) == 0
    assert by_id[C].points(PointsRules()) == 1
    assert by_id[D].points(PointsRules()) == 1
    assert table[0].team_id == A  # most points first


def test_goal_difference_tiebreak():
    # A and B both win once; A has better GD.
    results = [
        MatchResult(A, C, 5, 0),
        MatchResult(B, D, 2, 0),
        MatchResult(A, B, 0, 0),
        MatchResult(C, D, 0, 0),
    ]
    table = compute_table([A, B, C, D], results)
    assert table[0].team_id == A
    assert table[1].team_id == B


def test_head_to_head_tiebreak():
    # A and B level on points and GD/GF; A beat B head-to-head.
    results = [
        MatchResult(A, B, 1, 0),
        MatchResult(A, C, 1, 1),
        MatchResult(B, C, 1, 1),
    ]
    rules = PointsRules(tie_breakers=["points", "gd", "gf", "head_to_head", "admin"])
    table = compute_table([A, B, C], results, rules)
    a_pos = next(i for i, r in enumerate(table) if r.team_id == A)
    b_pos = next(i for i, r in enumerate(table) if r.team_id == B)
    assert a_pos < b_pos


def test_deterministic_and_idempotent():
    results = [MatchResult(A, B, 1, 1), MatchResult(C, D, 2, 2)]
    first = [r.team_id for r in compute_table([A, B, C, D], results)]
    second = [r.team_id for r in compute_table([A, B, C, D], results)]
    assert first == second  # same input -> same order, every time


def test_medal_table_formula_and_ranking():
    tallies = [
        MedalTally(A, gold=1, silver=0, bronze=1),  # 5 + 1 = 6
        MedalTally(B, gold=0, silver=3, bronze=0),  # 6
        MedalTally(C, gold=2, silver=0, bronze=0),  # 10
    ]
    rows = compute_medal_table(tallies, {"gold": 5, "silver": 2, "bronze": 1})
    assert rows[0].department_id == C
    assert rows[0].position == 1
    assert rows[0].total_points == 10
    # A and B tie on points (6); A ranks higher on gold count.
    a_row = next(r for r in rows if r.department_id == A)
    b_row = next(r for r in rows if r.department_id == B)
    assert a_row.position < b_row.position
