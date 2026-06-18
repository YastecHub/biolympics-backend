"""Domain enumerations. Stored as strings for portability across Postgres/SQLite."""

from __future__ import annotations

import enum


class RoleName(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    TOURNAMENT_ADMIN = "TOURNAMENT_ADMIN"
    SCORE_OFFICIAL = "SCORE_OFFICIAL"
    CONTENT_MANAGER = "CONTENT_MANAGER"


class GenderCategory(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    MIXED = "MIXED"
    OPEN = "OPEN"


class CompetitionFormat(str, enum.Enum):
    ROUND_ROBIN = "ROUND_ROBIN"
    GROUP_STAGE = "GROUP_STAGE"
    KNOCKOUT = "KNOCKOUT"
    GROUP_THEN_KNOCKOUT = "GROUP_THEN_KNOCKOUT"
    DIRECT_FINAL = "DIRECT_FINAL"
    RANKED_TIMED = "RANKED_TIMED"
    INDIVIDUAL_BRACKET = "INDIVIDUAL_BRACKET"
    CUSTOM = "CUSTOM"


class ScoringType(str, enum.Enum):
    GOAL_BASED = "GOAL_BASED"
    POINT_BASED = "POINT_BASED"
    SET_BASED = "SET_BASED"
    TIMED_RACE = "TIMED_RACE"
    RANKED_FINISH = "RANKED_FINISH"
    BEST_OF_N = "BEST_OF_N"
    WIN_LOSS = "WIN_LOSS"
    CUSTOM_NUMERIC = "CUSTOM_NUMERIC"


class FixtureStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    WARMUP = "WARMUP"
    LIVE = "LIVE"
    HALF_TIME = "HALF_TIME"
    PERIOD_BREAK = "PERIOD_BREAK"
    PAUSED = "PAUSED"
    DELAYED = "DELAYED"
    POSTPONED = "POSTPONED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    WALKOVER = "WALKOVER"
    UNDER_REVIEW = "UNDER_REVIEW"


# Statuses in which a score official may mutate live state.
LIVE_EDITABLE_STATUSES = {
    FixtureStatus.WARMUP,
    FixtureStatus.LIVE,
    FixtureStatus.HALF_TIME,
    FixtureStatus.PERIOD_BREAK,
    FixtureStatus.PAUSED,
}

TERMINAL_STATUSES = {
    FixtureStatus.COMPLETED,
    FixtureStatus.CANCELLED,
    FixtureStatus.WALKOVER,
}


class MatchEventType(str, enum.Enum):
    GOAL = "GOAL"
    OWN_GOAL = "OWN_GOAL"
    YELLOW_CARD = "YELLOW_CARD"
    RED_CARD = "RED_CARD"
    SUBSTITUTION = "SUBSTITUTION"
    PENALTY_SCORED = "PENALTY_SCORED"
    PENALTY_MISSED = "PENALTY_MISSED"
    HALF_TIME = "HALF_TIME"
    FULL_TIME = "FULL_TIME"
    POINT = "POINT"
    NOTE = "NOTE"


class ParticipantKind(str, enum.Enum):
    TEAM = "TEAM"
    INDIVIDUAL = "INDIVIDUAL"


class AnnouncementType(str, enum.Enum):
    GENERAL = "GENERAL"
    URGENT = "URGENT"
    VENUE_CHANGE = "VENUE_CHANGE"
    POSTPONEMENT = "POSTPONEMENT"
    SCHEDULE_CHANGE = "SCHEDULE_CHANGE"
    WEATHER = "WEATHER"
    RESULT_CORRECTION = "RESULT_CORRECTION"


class RaceOutcome(str, enum.Enum):
    FINISHED = "FINISHED"
    DNS = "DNS"  # did not start
    DNF = "DNF"  # did not finish
    DQ = "DQ"  # disqualified


class MedalKind(str, enum.Enum):
    GOLD = "GOLD"
    SILVER = "SILVER"
    BRONZE = "BRONZE"


class NotificationTopic(str, enum.Enum):
    ALL = "ALL"
    DEPARTMENT = "DEPARTMENT"
    SPORT = "SPORT"
    FIXTURE = "FIXTURE"
    URGENT_ONLY = "URGENT_ONLY"
