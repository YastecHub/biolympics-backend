"""Initial tournament content for the Life Sciences Dean's Games 2026.

This is seed data, not hard-coded application logic — administrators edit it in
the database after seeding. Missing times/venues are intentionally left blank so
the UI shows them as TBD.
"""

from __future__ import annotations

from app.models.enums import (
    CompetitionFormat,
    GenderCategory,
    ParticipantKind,
    ScoringType,
)

TOURNAMENT = {
    "name": "Life Sciences Dean's Games 2026",
    "public_brand": "BIOLYMPICS LIVE",
    "slug": "deans-games-2026",
    "timezone": "Africa/Lagos",
    "start_date": "2026-06-19",
    "end_date": "2026-06-27",
    "description": "The Faculty of Life Sciences Dean's Games — eight departments, "
    "many sports, one champion.",
    "medal_points": {"gold": 5, "silver": 3, "bronze": 1},
}

# (name, abbreviation, short_name, primary, secondary)
DEPARTMENTS = [
    ("Botany", "BTN", "Botany", "#2e7d32", "#1b5e20"),
    ("Cell Biology and Genetics", "CBG", "Cell Bio", "#6a1b9a", "#4a148c"),
    ("Marine Sciences", "MSM", "Marine", "#0277bd", "#01579b"),
    ("Microbiology", "MIC", "Micro", "#c62828", "#8e0000"),
    ("Zoology", "ZLY", "Zoology", "#ef6c00", "#e65100"),
    ("Biochemistry", "BCH", "Biochem", "#00838f", "#006064"),
    ("Pre-Med", "PRE-MED", "Pre-Med", "#283593", "#1a237e"),
    ("Fisheries", "FISHERIES", "Fisheries", "#558b2f", "#33691e"),
]

# (name, slug, icon, gender, format, scoring, participant, requires_table,
#  requires_bracket, supports_live, uses_timing, periods, order)
SPORTS = [
    (
        "Male Football",
        "male-football",
        "soccer",
        GenderCategory.MALE,
        CompetitionFormat.GROUP_THEN_KNOCKOUT,
        ScoringType.GOAL_BASED,
        ParticipantKind.TEAM,
        True,
        True,
        True,
        False,
        2,
        1,
    ),
    (
        "Female Football",
        "female-football",
        "soccer",
        GenderCategory.FEMALE,
        CompetitionFormat.KNOCKOUT,
        ScoringType.GOAL_BASED,
        ParticipantKind.TEAM,
        False,
        True,
        True,
        False,
        2,
        2,
    ),
    (
        "Basketball",
        "basketball",
        "basketball",
        GenderCategory.OPEN,
        CompetitionFormat.KNOCKOUT,
        ScoringType.POINT_BASED,
        ParticipantKind.TEAM,
        False,
        True,
        True,
        False,
        4,
        3,
    ),
    (
        "Volleyball",
        "volleyball",
        "volleyball",
        GenderCategory.OPEN,
        CompetitionFormat.KNOCKOUT,
        ScoringType.SET_BASED,
        ParticipantKind.TEAM,
        False,
        True,
        True,
        False,
        5,
        4,
    ),
    (
        "Table Tennis",
        "table-tennis",
        "table-tennis",
        GenderCategory.MIXED,
        CompetitionFormat.INDIVIDUAL_BRACKET,
        ScoringType.SET_BASED,
        ParticipantKind.INDIVIDUAL,
        False,
        True,
        True,
        False,
        5,
        5,
    ),
    (
        "Athletics / Track Events",
        "athletics",
        "running",
        GenderCategory.MIXED,
        CompetitionFormat.RANKED_TIMED,
        ScoringType.TIMED_RACE,
        ParticipantKind.INDIVIDUAL,
        False,
        False,
        True,
        True,
        1,
        6,
    ),
    (
        "Marathon",
        "marathon",
        "running",
        GenderCategory.MIXED,
        CompetitionFormat.RANKED_TIMED,
        ScoringType.TIMED_RACE,
        ParticipantKind.INDIVIDUAL,
        False,
        False,
        True,
        True,
        1,
        7,
    ),
    (
        "Swimming",
        "swimming",
        "swimming",
        GenderCategory.MIXED,
        CompetitionFormat.RANKED_TIMED,
        ScoringType.TIMED_RACE,
        ParticipantKind.INDIVIDUAL,
        False,
        False,
        True,
        True,
        1,
        8,
    ),
    (
        "Chess",
        "chess",
        "chess",
        GenderCategory.OPEN,
        CompetitionFormat.INDIVIDUAL_BRACKET,
        ScoringType.WIN_LOSS,
        ParticipantKind.INDIVIDUAL,
        False,
        True,
        False,
        False,
        1,
        9,
    ),
    (
        "Scrabble",
        "scrabble",
        "scrabble",
        GenderCategory.OPEN,
        CompetitionFormat.INDIVIDUAL_BRACKET,
        ScoringType.CUSTOM_NUMERIC,
        ParticipantKind.INDIVIDUAL,
        False,
        True,
        False,
        False,
        1,
        10,
    ),
    (
        "Ludo",
        "ludo",
        "dice",
        GenderCategory.OPEN,
        CompetitionFormat.KNOCKOUT,
        ScoringType.WIN_LOSS,
        ParticipantKind.INDIVIDUAL,
        False,
        True,
        False,
        False,
        1,
        11,
    ),
    (
        "PES Console",
        "pes-console",
        "gamepad",
        GenderCategory.OPEN,
        CompetitionFormat.KNOCKOUT,
        ScoringType.GOAL_BASED,
        ParticipantKind.INDIVIDUAL,
        False,
        True,
        True,
        False,
        2,
        12,
    ),
    (
        "COD Mobile",
        "cod-mobile",
        "gamepad",
        GenderCategory.OPEN,
        CompetitionFormat.KNOCKOUT,
        ScoringType.BEST_OF_N,
        ParticipantKind.TEAM,
        False,
        True,
        True,
        False,
        5,
        13,
    ),
    (
        "Other Indoor Games",
        "indoor-games",
        "board",
        GenderCategory.OPEN,
        CompetitionFormat.CUSTOM,
        ScoringType.CUSTOM_NUMERIC,
        ParticipantKind.TEAM,
        False,
        False,
        False,
        False,
        1,
        14,
    ),
]

VENUES = [
    ("Sports Centre", "Faculty of Life Sciences Sports Centre"),
    ("Main Field", "University Main Football Field"),
    ("Indoor Hall", "Life Sciences Indoor Games Hall"),
    ("Swimming Pool", "University Aquatic Centre"),
    ("Athletics Track", "University Athletics Track"),
]

# Group / pot draws per sport. {sport_slug: {group_name: [dept_abbr, ...]}}
DRAWS = {
    "male-football": {
        "Group A": ["BTN", "CBG", "MSM", "MIC"],
        "Group B": ["ZLY", "BCH", "PRE-MED", "FISHERIES"],
    },
    "female-football": {
        "Pot A": ["MSM", "ZLY", "FISHERIES", "BCH"],
        "Pot B": ["MIC", "BTN", "PRE-MED", "CBG"],
    },
    "basketball": {
        "Pot A": ["MSM", "BCH", "CBG", "ZLY"],
        "Pot B": ["MIC", "BTN", "PRE-MED", "FISHERIES"],
    },
    "volleyball": {
        "Pot A": ["BCH", "CBG", "BTN", "FISHERIES"],
        "Pot B": ["PRE-MED", "MIC", "MSM", "ZLY"],
    },
    "indoor-games": {
        "Pot A": ["BCH", "PRE-MED", "CBG", "MSM"],
        "Pot B": ["BTN", "MIC", "ZLY", "FISHERIES"],
    },
}

# Male football round-robin pairings by match day (per the official draw).
MALE_FOOTBALL_FIXTURES = {
    "Group A": {
        1: [("BTN", "CBG"), ("MSM", "MIC")],
        2: [("BTN", "MSM"), ("CBG", "MIC")],
        3: [("BTN", "MIC"), ("CBG", "MSM")],
    },
    "Group B": {
        1: [("ZLY", "BCH"), ("PRE-MED", "FISHERIES")],
        2: [("ZLY", "PRE-MED"), ("BCH", "FISHERIES")],
        3: [("ZLY", "FISHERIES"), ("BCH", "PRE-MED")],
    },
}

# Match-day start times in Africa/Lagos local time (date, hour, minute, venue).
MALE_FOOTBALL_SCHEDULE = {
    1: ("2026-06-20", 11, 0, "Main Field"),
    2: ("2026-06-22", 14, 0, "Main Field"),
    3: ("2026-06-23", 12, 0, "Main Field"),
}

# Standalone scheduled events as fixtures (often with TBD teams/times).
# (sport_slug, label/round_name, date or None, start hour, start min, end hour,
#  end min, venue or None)
SCHEDULE_EVENTS = [
    ("indoor-games", "Group Play", "2026-06-19", 16, 0, 19, 0, "Indoor Hall"),
    ("marathon", "Marathon (M & F)", "2026-06-20", 6, 30, 10, 0, None),
    ("female-football", "Knockout", "2026-06-20", 8, 0, 10, 0, None),
    ("volleyball", "Knockout", "2026-06-22", 12, 0, 14, 0, None),
    ("basketball", "Knockout", "2026-06-22", 12, 0, 14, 0, "Sports Centre"),
    ("female-football", "Semi-Finals", "2026-06-23", 12, 0, 14, 0, None),
    ("table-tennis", "Round 1", None, None, None, None, None, None),
    ("volleyball", "Semi-Finals", "2026-06-24", 14, 0, 16, 0, None),
    ("swimming", "Heats & Finals", "2026-06-24", 14, 0, 16, 0, "Swimming Pool"),
    ("athletics", "Heats", "2026-06-24", 16, 0, 18, 0, "Athletics Track"),
    ("basketball", "Semi-Finals", "2026-06-25", 12, 0, 14, 0, "Sports Centre"),
    ("female-football", "Third-Place Match", None, None, None, None, None, None),
    ("male-football", "Semi-Finals", None, None, None, None, None, None),
    ("basketball", "Third-Place Match", None, None, None, None, None, None),
    ("volleyball", "Final", None, None, None, None, None, None),
    ("volleyball", "Third-Place Match", None, None, None, None, None, None),
    ("male-football", "Final", None, None, None, None, None, None),
    ("male-football", "Third-Place Match", None, None, None, None, None, None),
    ("female-football", "Final", None, None, None, None, None, None),
    ("athletics", "Finals", None, None, None, None, None, None),
    ("basketball", "Final", None, None, None, None, None, None),
]

ANNOUNCEMENTS = [
    {
        "title": "Welcome to BIOLYMPICS LIVE 2026!",
        "body": "Follow every match, result and medal across all eight departments. "
        "Enable notifications to never miss a moment.",
        "type": "GENERAL",
        "is_urgent": False,
    },
    {
        "title": "Basketball moved to the Sports Centre",
        "body": "Monday's basketball knockout fixtures will be held at the Sports "
        "Centre. Plan your arrival accordingly.",
        "type": "VENUE_CHANGE",
        "is_urgent": True,
    },
]

SPONSORS = [
    {"name": "Faculty of Life Sciences", "tier": "Headline", "display_order": 1},
    {"name": "Students' Union", "tier": "Supporting", "display_order": 2},
]
