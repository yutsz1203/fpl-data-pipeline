from pathlib import Path
from typing import Annotated, Literal

from mcp.types import ToolAnnotations
from pydantic import Field, StringConstraints

SEARCH_CAP = 10
TOP_CAP = 25
FORM_CAP = 10
OUTLOOK_CAP = 8
AVAILABILITY_CAP = 60
MARKET_CAP = 25
PROJECTION_CAP = 25
PLAYER_KEYS_CAP = 20
LINEUPS_CAP = 10
HISTORY_CAP = 15
LEAGUES_CAP = 25
RIVALS_CAP = 10
THREATS_CAP = 15
STANDINGS_PAGE_SIZE = 50
FPL_FETCH_WORKERS = 4
MIN_PRICE = 3.5
MAX_PRICE = 20.0
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)
READ_ONLY_LIVE = ToolAnnotations(read_only_hint=True, open_world_hint=True)
RULES_DIR = Path(__file__).resolve().parent / "rules"
RULES_URL = "https://fantasy.premierleague.com/en/help/rules"
POSITIONS = ("GKP", "DEF", "MID", "FWD")
CHIP_NAMES = {
    "wildcard": "Wildcard",
    "freehit": "Free Hit",
    "bboost": "Bench Boost",
    "3xc": "Triple Captain",
}
INSTRUCTIONS = (
    "Read-only Fantasy Premier League stats from a daily-updated warehouse. "
    "Before you answer anything about rules, scoring, hits, free transfers, selling "
    "prices or chips, call fpl_rules. The rules change every season, so never answer "
    "them from memory. "
    "Players are identified by player_key, which search_players returns. "
    "Looking back: top_players, player_form, player_season. Looking ahead: "
    "fixture_outlook (fixtures and forecast goals), projected_points (a points model), "
    "availability and player_status (injuries, suspensions, price and ownership), "
    "team_lineups (confirmed and predicted lineups) and market_watch (transfers and "
    "price changes). Three tools read the FPL site live: my_team (the user's squad, "
    "bank, chips and leagues), league_standings (one league's table) and rival_compare "
    "(the user's squad against rivals in a league: threats and differentials). "
    "Say which gameweek the data runs to (data_to_gameweek) when you answer."
)
EntryId = Annotated[
    int | None,
    Field(
        ge=1,
        le=99_999_999,
        description="FPL entry id. Leave it out to use the user's saved id.",
    ),
]
LeagueName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]
LeagueId = Annotated[
    int,
    Field(
        ge=1,
        le=99_999_999,
        description="Classic league id, from the leagues list that my_team returns.",
    ),
]

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
    "bonus",
    "bps",
]
OneTeam = Annotated[
    str,
    Field(pattern=r"^[A-Z]{3}$", description="Team short name, for example 'ARS'."),
]
MaxPrice = Annotated[
    float | None,
    Field(
        ge=MIN_PRICE,
        le=MAX_PRICE,
        description="Only players at or under this price in £m, for example 7.0.",
    ),
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
    "bonus": ("bonus", "desc"),
    "bps": ("bps", "desc"),
}

STATUS_NAMES = {
    "a": "available",
    "d": "doubtful",
    "i": "injured",
    "s": "suspended",
    "u": "unavailable",
    "n": "not in squad",
}
FLAGGED_STATUSES = ["d", "i", "s", "n"]
MARKET_ORDERS = {
    "transfers_in": "p.transfers_in_gameweek - p.transfers_out_gameweek desc",
    "transfers_out": "p.transfers_in_gameweek - p.transfers_out_gameweek asc",
    "price_rise_gameweek": "p.price_change_gameweek desc",
    "price_fall_gameweek": "p.price_change_gameweek asc",
    "price_rise_season": "p.price_change_season desc",
    "price_fall_season": "p.price_change_season asc",
    "ownership": "p.current_selected_pct desc",
}
PROJECTION_METHOD = (
    "Per fixture: appearance points from the recent play and 60-minute rates; goals and "
    "assists from the player's share of his team's xG and xA times the team's forecast "
    "goals; clean sheet chance exp(-forecast goals against); goalkeeper saves from his "
    "saves per expected goal conceded; minus 1 per 2 goals conceded for goalkeepers and "
    "defenders; defensive contribution, bonus and yellow cards at the player's season "
    "rates. All scaled by expected minutes and the chance of playing. Red cards, own "
    "goals and penalties saved or missed are left out. Read it as a ranking aid, not an "
    "exact score."
)

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
    "bonus",
    "bps",
)

SCHEMA_TABLES = {
    "dim_player": "One row per player per season. player_key is the id the tools use.",
    "dim_team": "One row per team per season.",
    "dim_gameweek": "One row per gameweek. data_to_gameweek is the latest one that is finished and data-checked.",
    "dim_fixture": "One row per match, played or not, with FPL's difficulty for each side. fixture_outlook reads it.",
    "fct_player_match": "One row per player per match of their team. player_form reads it.",
    "player_season_stats": "Season totals and per-90 rates, one row per player. player_season reads it.",
    "player_scouting": "Season totals with team and position, one row per player. top_players reads it.",
    "fct_player_daily": "One row per player per daily snapshot since 2026-09-24: status, news, price and ownership that day. player_status reads it.",
    "player_projection": "Expected minutes and per-90 rates, one row per player. projected_points reads it.",
    "fct_lineup": "One row per player per team sheet from Bzzoiro, confirmed or predicted. team_lineups reads it.",
    "player_injury": "Bzzoiro's injury type and expected return for players who are out. availability reads it.",
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
    "bonus / bps": "Bonus points (3, 2 and 1 to the best three players of a match) and the bonus points system score that decides them.",
    "status": "FPL's flag: available, doubtful, injured, suspended, unavailable (left the league) or not in squad.",
    "chance_of_playing_next_round": "FPL's percent chance for the next gameweek. Empty when no doubt was ever flagged.",
    "selling_price": "Purchase price plus half of any rise since, rounded down to £0.1m. A fall is taken in full.",
    "expected_minutes": "Average minutes over the last 5 games the player was available for, times the chance of playing.",
    "projected_points": "A model estimate from expected minutes, the player's xG and xA share, and the fixture forecast. See the method field of projected_points.",
    "start_score": "Bzzoiro's 0-1 score for a player in a predicted lineup. Higher means more likely to start.",
    "difficulty": "FPL fixture difficulty for one side, 1 (easiest) to 5.",
    "expected_gf / expected_ga": "Forecast goals for and against in one fixture, from a Poisson model fitted on this season's results and weighted toward recent games. Use them to compare teams more than as exact numbers.",
    "clean_sheet_probability": "exp(-expected_ga): the model's chance that the team concedes no goal. Rough, because the model treats both teams' goals as independent.",
    "blank / double gameweek": "A gameweek in which a team has no fixture, or 2 or more.",
    "minutes floor": "top_players ranks only players with at least 60 minutes per finished gameweek (season) or 60 minutes per game (last_n).",
}
