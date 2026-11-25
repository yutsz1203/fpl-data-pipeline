from datetime import date, datetime

from pydantic import BaseModel, Field


class Player(BaseModel):
    player_key: str
    web_name: str
    full_name: str
    team: str | None = Field(description="The player's current club.")
    position: str | None
    price: float = Field(description="Current price in £m.")
    status: str = Field(
        description="available, doubtful, injured, suspended, unavailable or not in squad."
    )
    chance_of_playing_next_round: int | None = Field(
        description="FPL's chance in percent. Empty means no doubt has been flagged."
    )
    news: str = Field(description="FPL's injury or suspension note. Empty if none.")
    selected_pct: float = Field(description="Share of FPL managers who own the player.")
    minutes: int
    total_points: int


class SearchResult(BaseModel):
    season: str
    data_to_gameweek: int | None
    row_count: int
    truncated: bool = Field(
        description="True if more players matched than were returned. Add a filter or use a longer name."
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
    bonus: int
    bps: int = Field(description="Bonus points system score, which decides the bonus.")


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
    bonus: int
    bps: int


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


class Split(BaseModel):
    split: str
    appearances: int
    minutes: int
    total_points: int
    points_per_appearance: float | None
    goals_scored: int
    assists: int
    xgi: float
    clean_sheets: int
    bonus: int


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
    bonus: int
    bps: int
    status: str
    chance_of_playing_next_round: int | None
    news: str
    selected_pct: float
    penalties_order: int | None = Field(
        description="1 means first-choice penalty taker. Empty means not listed."
    )
    direct_freekicks_order: int | None
    corners_and_indirect_freekicks_order: int | None
    splits: list[Split] = Field(
        description="The season split by home and away, and by FPL fixture difficulty."
    )


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
    forecast_source: str | None = Field(
        description="engine: the prediction engine's forecast. fallback: a simpler team-strength model fitted on this season's results."
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
    forecast_note: str = Field(
        description="Empty when every fixture has a fresh engine forecast."
    )
    unscheduled_fixtures: int = Field(
        description="Postponed fixtures with no gameweek yet. They will make a double gameweek later."
    )
    teams: list[TeamOutlook]


class FlaggedPlayer(BaseModel):
    player_key: str
    web_name: str
    team: str
    position: str
    price: float
    status: str
    chance_of_playing_next_round: int | None
    news: str
    news_added: datetime | None
    selected_pct: float
    injury_type: str | None = Field(description="From Bzzoiro. Empty if not listed.")
    expected_return: date | None = Field(
        description="Bzzoiro's expected return date. Empty if unknown."
    )


class AvailabilityResult(BaseModel):
    season: str
    data_to_gameweek: int | None
    team: str | None
    row_count: int
    truncated: bool
    players: list[FlaggedPlayer] = Field(description="Most-owned first.")


class StatusChange(BaseModel):
    run_date: date
    status: str
    chance_of_playing_next_round: int | None
    news: str
    price: float
    price_change: float | None
    selected_pct: float


class PlayerStatusResult(BaseModel):
    player_key: str
    web_name: str
    team: str
    position: str
    season: str
    price: float
    status: str
    chance_of_playing_next_round: int | None
    news: str
    news_added: datetime | None
    injury_type: str | None
    expected_return: date | None
    selected_pct: float
    selected_pct_week_ago: float | None
    transfers_in_gameweek: int
    transfers_out_gameweek: int
    net_transfers_gameweek: int
    price_change_gameweek: float
    price_change_season: float
    penalties_order: int | None
    direct_freekicks_order: int | None
    corners_and_indirect_freekicks_order: int | None
    expected_minutes: int | None = Field(
        description="Average minutes over the recent games he was available for, times his chance of playing."
    )
    start_rate: float | None = Field(
        description="Share of those recent games that he started."
    )
    recent_games: int = Field(
        description="How many games that average uses, 5 at most."
    )
    predicted_starter: bool | None = Field(
        description="Whether Bzzoiro's predicted lineup for the next fixture starts him. Empty if there is no prediction yet or he is not in the matchday squad."
    )
    predicted_lineup_gameweek: int | None
    history: list[StatusChange] = Field(
        description="Days on which his status, news or price changed, newest first. Daily snapshots began on 2026-09-24."
    )


class MarketPlayer(BaseModel):
    rank: int
    player_key: str
    web_name: str
    team: str
    position: str
    price: float
    status: str
    selected_pct: float
    transfers_in_gameweek: int
    transfers_out_gameweek: int
    net_transfers_gameweek: int
    price_change_gameweek: float
    price_change_season: float


class MarketWatchResult(BaseModel):
    season: str
    data_to_gameweek: int | None
    sort_by: str
    row_count: int
    players: list[MarketPlayer]


class Pick(BaseModel):
    slot: int = Field(description="1-11 start, 12-15 are the bench in order.")
    player_key: str | None
    web_name: str
    team: str | None
    position: str | None
    is_captain: bool
    is_vice_captain: bool
    price: float | None = Field(description="Current price in £m.")
    purchase_price: float | None
    selling_price: float | None = Field(
        description="What the manager gets for selling now: purchase price plus half of any rise, rounded down to £0.1m."
    )
    status: str | None
    chance_of_playing_next_round: int | None
    news: str | None


class SquadTransfer(BaseModel):
    gameweek: int
    time: datetime
    player_in: str
    price_in: float
    player_out: str
    price_out: float


class ChipUse(BaseModel):
    chip: str
    gameweek: int


class ChipLeft(BaseModel):
    chip: str = Field(
        description="wildcard, freehit, bboost (Bench Boost) or 3xc (Triple Captain)."
    )
    from_gameweek: int
    to_gameweek: int
    playable_now: bool = Field(
        description="True if the next gameweek is inside the window."
    )


class League(BaseModel):
    league_id: int
    name: str
    kind: str = Field(
        description="classic or h2h. league_standings and rival_compare read classic leagues only."
    )
    private: bool = Field(
        description="True for a league that managers made and joined by code. False for FPL's own leagues (overall, country, club)."
    )
    entries: int | None = Field(description="How many teams are in the league.")
    rank: int | None
    last_rank: int | None = Field(description="Rank one gameweek earlier.")


class MyTeamResult(BaseModel):
    entry_id: int
    team_name: str
    season: str
    data_to_gameweek: int | None
    picks_gameweek: int = Field(
        description="The gameweek whose team sheet the picks come from."
    )
    next_gameweek: int | None
    overall_points: int | None
    overall_rank: int | None
    gameweek_points: int | None
    bank: float = Field(description="Money in the bank in £m, after pending transfers.")
    squad_selling_value: float | None = Field(
        description="Sum of the 15 selling prices in £m."
    )
    free_transfers: int | None = Field(
        description="Estimate for the next deadline, worked out from the transfer history. FPL does not publish it, and one-off top-ups are not counted."
    )
    pending_transfers: int = Field(
        description="Transfers already made for the next gameweek. The picks include them."
    )
    active_chip: str | None = Field(description="Chip played in picks_gameweek.")
    chips_used: list[ChipUse]
    chips_left: list[ChipLeft] = Field(
        description="Chips not yet played whose window has not closed."
    )
    notes: list[str]
    picks: list[Pick]
    recent_transfers: list[SquadTransfer] = Field(
        description="Newest first, 10 at most."
    )
    leagues: list[League] = Field(
        description="Private leagues first, smallest first. Pass a league_id to league_standings or rival_compare."
    )


class LeagueRow(BaseModel):
    rank: int
    last_rank: int | None
    entry_id: int
    team_name: str
    manager_name: str
    total_points: int
    gameweek_points: int
    is_me: bool


class LeagueStandingsResult(BaseModel):
    league_id: int
    league_name: str
    updated_at: datetime | None
    page: int
    has_next_page: bool
    my_rank: int | None = Field(
        description="The user's rank in this league. Empty if they are not in it or no entry id is saved."
    )
    my_page: int | None = Field(description="The page that holds the user's row.")
    row_count: int
    managers: list[LeagueRow]


class Rival(BaseModel):
    entry_id: int
    team_name: str
    manager_name: str
    rank: int
    total_points: int
    points_ahead_of_me: int = Field(
        description="Their league total minus the user's. Negative means they are behind."
    )
    gameweek_points: int | None
    captain: str | None
    vice_captain: str | None
    active_chip: str | None = Field(
        description="Chip played in the gameweek of the squads. After a freehit the squad goes back to the one before it."
    )
    chips_used: list[ChipUse]
    chips_left: list[str] = Field(
        description="Chips not yet played whose window has not closed."
    )
    transfers_made: int | None = Field(
        description="Transfers made for the gameweek of the squads."
    )
    hit_points: int | None = Field(
        description="Points paid for extra transfers in that gameweek."
    )
    squad_value: float | None = Field(description="Squad value plus bank, in £m.")
    players_shared_with_me: int = Field(description="Out of 15.")
    players_i_do_not_own: list[str] = Field(
        description="Their players that the user does not own. A (C) marks their captain, (bench) a bench player."
    )


class RivalPlayer(BaseModel):
    player_key: str | None
    web_name: str
    team: str | None
    position: str | None
    price: float | None
    status: str | None
    chance_of_playing_next_round: int | None
    owned_by: int = Field(description="How many of the compared rivals own the player.")
    started_by: int
    captained_by: int
    my_role: str | None = Field(
        description="captain, vice-captain, starter or bench in the user's squad. Empty if the user does not own the player."
    )


class RivalCompareResult(BaseModel):
    league_id: int
    league_name: str
    season: str
    data_to_gameweek: int | None
    squads_gameweek: int = Field(
        description="Every squad is the one from this gameweek's deadline."
    )
    my_entry_id: int
    my_rank: int | None
    my_total_points: int | None
    rivals_compared: int
    notes: list[str]
    rivals: list[Rival] = Field(description="By league rank.")
    threats: list[RivalPlayer] = Field(
        description="Players the user does not own, most-owned among the rivals first. If one scores, the user loses ground on every rival who owns him."
    )
    my_players: list[RivalPlayer] = Field(
        description="The user's 15 players, least-owned among the rivals first. Low owned_by is a differential: the user gains on most rivals when he scores. High owned_by is cover: it protects rank and wins nothing."
    )


class GameweekProjection(BaseModel):
    gameweek: int
    opponents: str = Field(
        description="For example 'BOU (H)'. Empty for a blank gameweek."
    )
    expected_minutes: float
    points: float


class PointsBreakdown(BaseModel):
    appearance: float
    goals: float
    assists: float
    clean_sheets: float
    saves: float
    defcon: float
    bonus: float
    goals_conceded: float
    yellow_cards: float


class ProjectedPlayer(BaseModel):
    rank: int
    player_key: str
    web_name: str
    team: str
    position: str
    price: float
    status: str
    chance_of_playing_next_round: int | None
    predicted_starter: bool | None = Field(
        description="Bzzoiro's predicted lineup for the next fixture. Shown for context: it does not change the projection."
    )
    start_rate: float | None
    projected_points: float
    points_per_million: float
    breakdown: PointsBreakdown = Field(
        description="projected_points split by source, summed over the gameweeks."
    )
    gameweeks: list[GameweekProjection]


class ProjectedPointsResult(BaseModel):
    season: str
    data_to_gameweek: int | None
    from_gameweek: int
    to_gameweek: int
    forecast_note: str
    method: str
    row_count: int
    truncated: bool
    players: list[ProjectedPlayer]


class LineupPlayer(BaseModel):
    player_name: str
    line: str | None = Field(
        description="GKP, DEF, MID or FWD in this lineup. Bzzoiro gives no finer position."
    )
    player_key: str | None = Field(description="Empty if no FPL player matched.")
    start_score: float | None = Field(
        description="Bzzoiro's 0-1 score. Predicted lineups only."
    )


class TeamLineup(BaseModel):
    gameweek: int | None
    kickoff_time: datetime
    opponent: str
    home: bool
    lineup_status: str = Field(description="confirmed or predicted.")
    formation: str | None
    confidence: float | None = Field(
        description="Bzzoiro's 0-1 confidence in a predicted lineup."
    )
    starters: list[LineupPlayer]
    bench: list[LineupPlayer]


class StartCount(BaseModel):
    player_name: str
    player_key: str | None
    starts: int
    bench: int


class TeamLineupsResult(BaseModel):
    season: str
    team: str
    lineups_updated_at: datetime | None
    confirmed_lineups: int
    lineups: list[TeamLineup] = Field(
        description="The predicted lineup for the next fixture first, if there is one, then confirmed lineups newest first."
    )
    start_counts: list[StartCount] = Field(
        description="Starts and bench places over the confirmed lineups above, most starts first."
    )
