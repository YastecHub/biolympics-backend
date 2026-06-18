"""Deterministic, idempotent round-robin standings computation.

Pure functions operating on plain data so they can be unit-tested without a
database. The DB-aware wrapper lives in ``recompute_group_standings``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

DEFAULT_TIE_BREAKERS = ["points", "gd", "gf", "head_to_head", "admin"]


@dataclass
class PointsRules:
    win: int = 3
    draw: int = 1
    loss: int = 0
    tie_breakers: list[str] = field(default_factory=lambda: list(DEFAULT_TIE_BREAKERS))


@dataclass
class MatchResult:
    home: uuid.UUID
    away: uuid.UUID
    home_score: int
    away_score: int


@dataclass
class TableRow:
    team_id: uuid.UUID
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    def points(self, rules: PointsRules) -> int:
        return self.won * rules.win + self.drawn * rules.draw + self.lost * rules.loss


def _head_to_head_points(
    team_id: uuid.UUID,
    tied_group: set[uuid.UUID],
    results: list[MatchResult],
    rules: PointsRules,
) -> int:
    """Points earned only in matches among the tied teams."""
    pts = 0
    for r in results:
        if r.home not in tied_group or r.away not in tied_group:
            continue
        if r.home == team_id or r.away == team_id:
            is_home = r.home == team_id
            gf, ga = (r.home_score, r.away_score) if is_home else (r.away_score, r.home_score)
            if gf > ga:
                pts += rules.win
            elif gf == ga:
                pts += rules.draw
            else:
                pts += rules.loss
    return pts


def compute_table(
    team_ids: list[uuid.UUID],
    results: list[MatchResult],
    rules: PointsRules | None = None,
) -> list[TableRow]:
    """Compute a sorted standings table. Deterministic and idempotent: the same
    inputs always yield the same ordering (final fallback is team_id)."""
    rules = rules or PointsRules()
    rows: dict[uuid.UUID, TableRow] = {tid: TableRow(team_id=tid) for tid in team_ids}

    for r in results:
        if r.home not in rows or r.away not in rows:
            continue
        h, a = rows[r.home], rows[r.away]
        h.played += 1
        a.played += 1
        h.goals_for += r.home_score
        h.goals_against += r.away_score
        a.goals_for += r.away_score
        a.goals_against += r.home_score
        if r.home_score > r.away_score:
            h.won += 1
            a.lost += 1
        elif r.home_score < r.away_score:
            a.won += 1
            h.lost += 1
        else:
            h.drawn += 1
            a.drawn += 1

    ordered = list(rows.values())

    def sort_key(row: TableRow) -> tuple:
        pts = row.points(rules)
        tied = {t.team_id for t in ordered if t.points(rules) == pts}
        key: list = []
        for tb in rules.tie_breakers:
            if tb == "points":
                key.append(-pts)
            elif tb == "gd":
                key.append(-row.goal_difference)
            elif tb == "gf":
                key.append(-row.goals_for)
            elif tb == "head_to_head":
                key.append(-_head_to_head_points(row.team_id, tied, results, rules))
            elif tb == "admin":
                # Stable, deterministic placeholder for "administrator decision".
                key.append(str(row.team_id))
        key.append(str(row.team_id))  # absolute determinism guarantee
        return tuple(key)

    ordered.sort(key=sort_key)
    return ordered
