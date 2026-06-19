"""Configurable medal-table / department-points computation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

DEFAULT_MEDAL_POINTS = {"gold": 5, "silver": 2, "bronze": 1}


@dataclass
class MedalTally:
    department_id: uuid.UUID
    gold: int = 0
    silver: int = 0
    bronze: int = 0
    participation_points: float = 0.0
    bonus_points: float = 0.0
    penalties: float = 0.0


@dataclass
class MedalTableRow:
    department_id: uuid.UUID
    gold: int
    silver: int
    bronze: int
    participation_points: float
    bonus_points: float
    penalties: float
    total_points: float
    position: int = 0
    breakdown: dict = field(default_factory=dict)


def compute_medal_table(
    tallies: list[MedalTally], formula: dict | None = None
) -> list[MedalTableRow]:
    """Total = gold*g + silver*s + bronze*b + participation + bonus - penalties.

    The formula (points per medal) is editable per tournament. Ranking falls back
    to gold→silver→bronze count, then department_id, for full determinism.
    """
    formula = formula or DEFAULT_MEDAL_POINTS
    g = float(formula.get("gold", 5))
    s = float(formula.get("silver", 2))
    b = float(formula.get("bronze", 1))

    rows: list[MedalTableRow] = []
    for t in tallies:
        medal_pts = t.gold * g + t.silver * s + t.bronze * b
        total = medal_pts + t.participation_points + t.bonus_points - t.penalties
        rows.append(
            MedalTableRow(
                department_id=t.department_id,
                gold=t.gold,
                silver=t.silver,
                bronze=t.bronze,
                participation_points=t.participation_points,
                bonus_points=t.bonus_points,
                penalties=t.penalties,
                total_points=total,
                breakdown={
                    "medal_points": medal_pts,
                    "formula": {"gold": g, "silver": s, "bronze": b},
                },
            )
        )

    rows.sort(
        key=lambda r: (
            -r.total_points,
            -r.gold,
            -r.silver,
            -r.bronze,
            str(r.department_id),
        )
    )
    for i, row in enumerate(rows, start=1):
        row.position = i
    return rows
