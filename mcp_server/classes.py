from datetime import date, datetime

from pydantic import BaseModel, Field


class Player(BaseModel):
    player_key: str
    web_name: str
    full_name: str
    team: str | None = Field(
        description="Team in the player's latest match. Empty if the player has not played yet."
    )
    position: str | None
    price: float = Field(description="Current price in £m.")


class SearchResult(BaseModel):
    season: str
    data_to_gameweek: int | None
    row_count: int
    truncated: bool = Field(
        description="True if more players matched than were returned. Use a longer name to narrow the search."
    )
    players: list[Player]


class RankedPlayer(BaseModel):
    rank: int
    player_key: str
    web_name: str
    team: str
    price: float
    minutes: int
    total_points: int
    value: float | None = Field(description="The player's value for the ranked metric.")


class TopPlayersResult(BaseModel):
    season: str
    data_to_gameweek: int | None
    position: str
    metric: str
    window: str = Field(description="'season', or 'last N games'.")
    min_minutes: int = Field(
        description="Players with fewer minutes in the window were left out."
    )
    max_price: float | None
    row_count: int
    truncated: bool = Field(
        description="True if more players qualified than were returned."
    )
    players: list[RankedPlayer]


class Game(BaseModel):
    gameweek: int
    kickoff_time: datetime
    opponent: str
    home: bool
    started: bool
    minutes: int
    points: int
    goals: int
    assists: int
    xgi: float
    defcon: int = Field(description="Defensive contributions.")


class WindowTotals(BaseModel):
    games: int
    starts: int
    minutes: int
    total_points: int
    points_per_million: float
    goals_scored: int
    assists: int
    gi: int
    xgi: float
    xgi_per_90: float | None
    clean_sheets: int
    xgc_per_90: float | None
    defcon_per_90: float | None
    defcon_hit_rate: float | None
    saves: int


class PlayerFormResult(BaseModel):
    player_key: str
    web_name: str
    team: str
    position: str
    price: float
    season: str
    data_to_gameweek: int | None
    row_count: int
    games: list[Game] = Field(description="Newest first.")
    totals: WindowTotals = Field(
        description="Sums and per-90 rates over the games above."
    )


class PlayerSeasonResult(BaseModel):
    player_key: str
    web_name: str
    team: str
    position: str
    season: str
    data_to_gameweek: int | None
    price: float = Field(description="Current price in £m.")
    appearances: int
    starts: int
    minutes: int
    total_points: int
    points_per_million: float
    goals_scored: int
    assists: int
    gi: int
    xg: float
    xa: float
    xgi: float
    gi_minus_xgi: float = Field(
        description="Goals plus assists minus xGI. Above 0 means finishing above expectation."
    )
    xgi_per_90: float | None
    clean_sheets: int
    goals_conceded: int
    xgc_per_90: float | None
    defcon_per_90: float | None
    defcon_hit_rate: float | None
    saves: int


class StepFreshness(BaseModel):
    step: str
    last_success_run_date: date | None
    last_success_at: datetime | None


class Freshness(BaseModel):
    season: str | None
    data_to_gameweek: int | None = Field(
        description="Latest gameweek that is finished and data-checked."
    )
    steps: list[StepFreshness]


class OutlookFixture(BaseModel):
    gameweek: int
    kickoff_time: datetime
    opponent: str
    home: bool
    difficulty: int = Field(description="FPL fixture difficulty, 1 (easiest) to 5.")
    expected_gf: float | None = Field(
        description="Forecast goals for. Empty if no forecast."
    )
    expected_ga: float | None = Field(
        description="Forecast goals against. Empty if no forecast."
    )
    clean_sheet_probability: float | None = Field(
        description="Chance of conceding no goal: exp(-expected_ga)."
    )


class TeamOutlook(BaseModel):
    rank: int
    team: str
    fixture_count: int
    blank_gameweeks: list[int] = Field(description="Gameweeks with no fixture.")
    double_gameweeks: list[int] = Field(
        description="Gameweeks with 2 or more fixtures."
    )
    average_difficulty: float | None
    expected_gf: float | None = Field(
        description="Sum over the fixtures that have a forecast."
    )
    expected_ga: float | None
    expected_clean_sheets: float | None = Field(
        description="Sum of the clean sheet probabilities."
    )
    fixtures_without_forecast: int
    opponents: list[str] = Field(
        description="One per fixture, in kickoff order: gameweek, opponent, H or A, FPL difficulty."
    )
    fixtures: list[OutlookFixture] = Field(
        description="Each fixture with its forecast. Only when a team is given."
    )


class FixtureOutlookResult(BaseModel):
    season: str
    data_to_gameweek: int | None
    from_gameweek: int
    to_gameweek: int
    sort_by: str
    forecast_gameweeks: str | None = Field(
        description="The gameweeks the forecast covers, for example '11-15'."
    )
    forecast_updated_at: datetime | None
    forecast_note: str = Field(description="Empty when the forecast is fresh.")
    teams: list[TeamOutlook]
