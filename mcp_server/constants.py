from typing import Annotated, Literal

from mcp.types import ToolAnnotations
from pydantic import Field, StringConstraints

SEARCH_CAP = 10
TOP_CAP = 25
FORM_CAP = 10
OUTLOOK_CAP = 8
MIN_PRICE = 3.5
MAX_PRICE = 20.0
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

Season = Annotated[
    str | None,
    Field(
        pattern=r"^\d{4}/\d{2}$",
        description="Season in the form '2026/27'. Leave it out for the latest season.",
    ),
]
PlayerKey = Annotated[
    str,
    Field(
        pattern=r"^[0-9a-f]{32}$",
        description="The player's player_key from search_players. Not a name.",
    ),
]
PlayerName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=40),
    Field(
        description="All or part of the player's name, for example 'Haaland' or 'Erling'."
    ),
]
Position = Literal["GKP", "DEF", "MID", "FWD"]
TeamName = Annotated[
    str | None,
    Field(
        pattern=r"^[A-Z]{3}$",
        description="Team short name, for example 'ARS'. Leave it out for all 20 teams.",
    ),
]
Budget = Annotated[float, Field(ge=MIN_PRICE, le=MAX_PRICE)]
Metric = Literal[
    "total_points",
    "points_per_million",
    "xgi",
    "xgi_per_90",
    "gi",
    "clean_sheets",
    "xgc_per_90",
    "defcon_per_90",
    "defcon_hit_rate",
    "saves",
]
MetricsArg = Annotated[
    str,
    Field(
        description=(
            "Optional. Metrics to compare, separated by commas, for example "
            "'saves, clean_sheets'. They replace the position's default metrics. "
            "total_points, minutes, starts and points_per_million are always included."
        )
    ),
]

METRICS = {
    "total_points": ("total_points", "desc"),
    "points_per_million": ("points_per_million", "desc"),
    "xgi": ("xgi", "desc"),
    "xgi_per_90": ("xgi_per_90", "desc"),
    "gi": ("gi", "desc"),
    "clean_sheets": ("clean_sheets", "desc"),
    "xgc_per_90": ("xgc_per_90", "asc"),
    "defcon_per_90": ("defcon_per_90", "desc"),
    "defcon_hit_rate": ("defcon_hit_rate", "desc"),
    "saves": ("saves", "desc"),
}

POSITION_NAMES = {
    "GKP": "goalkeepers",
    "DEF": "defenders",
    "MID": "midfielders",
    "FWD": "forwards",
}

CORE_METRICS = ("total_points", "minutes", "starts", "points_per_million")
POSITION_METRICS = {
    "GKP": ("clean_sheets", "saves", "xgc_per_90"),
    "DEF": (
        "clean_sheets",
        "defcon_per_90",
        "defcon_hit_rate",
        "xgi_per_90",
        "goals_scored",
        "assists",
    ),
    "MID": (
        "xgi_per_90",
        "goals_scored",
        "assists",
        "gi_minus_xgi",
        "defcon_per_90",
        "defcon_hit_rate",
    ),
    "FWD": ("xgi_per_90", "goals_scored", "assists", "gi_minus_xgi"),
}
COMPARE_METRICS = (
    "appearances",
    "starts",
    "minutes",
    "total_points",
    "points_per_million",
    "goals_scored",
    "assists",
    "gi",
    "xg",
    "xa",
    "xgi",
    "gi_minus_xgi",
    "xgi_per_90",
    "clean_sheets",
    "goals_conceded",
    "xgc_per_90",
    "defcon_per_90",
    "defcon_hit_rate",
    "saves",
)

SCHEMA_TABLES = {
    "dim_player": "One row per player per season. player_key is the id the tools use.",
    "dim_team": "One row per team per season.",
    "dim_gameweek": "One row per gameweek. data_to_gameweek is the latest one that is finished and data-checked.",
    "dim_fixture": "One row per match, played or not, with FPL's difficulty for each side. fixture_outlook reads it.",
    "fct_player_match": "One row per player per match of their team. player_form reads it.",
    "player_season_stats": "Season totals and per-90 rates, one row per player. player_season reads it.",
    "player_scouting": "Season totals with team and position, one row per player. search_players and top_players read it.",
    "player_scouting_last_n": "The same totals over each player's last N team games, for every N from 1 to all games so far. top_players with last_n and player_form read it.",
}
GLOSSARY = {
    "player_key": "A 32-character id for one player in one season. search_players returns it.",
    "data_to_gameweek": "The latest gameweek that is finished and data-checked. Numbers include that gameweek and none after it.",
    "price": "Current price in £m.",
    "total_points": "FPL points.",
    "points_per_million": "Points per £1m of current price.",
    "gi": "Goals plus assists.",
    "xgi": "Expected goals plus expected assists.",
    "xgi_per_90": "xGI per 90 minutes.",
    "gi_minus_xgi": "Goals plus assists minus xGI. Above 0 means finishing above expectation.",
    "clean_sheets": "FPL clean sheets: the player played 60 minutes or more, and their team conceded no goal while they were on the pitch.",
    "xgc_per_90": "Expected goals conceded per 90 minutes. Lower is better.",
    "defcon_per_90": "Defensive contributions per 90 minutes. FPL gives 2 points when a defender reaches 10 in a match, or a midfielder or forward reaches 12.",
    "defcon_hit_rate": "Share of appearances (games with any minutes) that earned those 2 points.",
    "saves": "Goalkeeper saves.",
    "difficulty": "FPL fixture difficulty for one side, 1 (easiest) to 5.",
    "expected_gf / expected_ga": "Forecast goals for and against in one fixture, from a Poisson model fitted on this season's results and weighted toward recent games. Use them to compare teams more than as exact numbers.",
    "clean_sheet_probability": "exp(-expected_ga): the model's chance that the team concedes no goal. Rough, because the model treats both teams' goals as independent.",
    "blank / double gameweek": "A gameweek in which a team has no fixture, or 2 or more.",
    "minutes floor": "top_players ranks only players with at least 60 minutes per finished gameweek (season) or 60 minutes per game (last_n).",
}
