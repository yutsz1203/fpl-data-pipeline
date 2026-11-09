import math
import os
from collections import Counter, defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from statistics import mean
from typing import Annotated, Literal

import psycopg
from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from psycopg import sql
from psycopg.rows import dict_row
from pydantic import Field

from mcp_server.classes import (
    FixtureOutlookResult,
    Freshness,
    Game,
    OutlookFixture,
    Player,
    PlayerFormResult,
    PlayerSeasonResult,
    RankedPlayer,
    SearchResult,
    StepFreshness,
    TeamOutlook,
    TopPlayersResult,
    WindowTotals,
)
from mcp_server.constants import (
    FORM_CAP,
    GLOSSARY,
    MAX_PRICE,
    METRICS,
    MIN_PRICE,
    OUTLOOK_CAP,
    READ_ONLY,
    SCHEMA_TABLES,
    SEARCH_CAP,
    TOP_CAP,
    Metric,
    PlayerKey,
    PlayerName,
    Position,
    Season,
    TeamName,
)
from mcp_server.forecast import load_forecast
from mcp_server.prompts import scout_position, transfer_check
from mcp_server.queries import (
    FIND_PLAYER_SQL,
    FORM_GAMES_SQL,
    FORM_TOTALS_SQL,
    FRESHNESS_SQL,
    GAMEWEEK_RANGE_SQL,
    OUTLOOK_SQL,
    SCHEMA_SQL,
    SEARCH_SQL,
    SEASON_SQL,
    SEASONS_SQL,
    TEAMS_SQL,
    TOP_SQL,
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


mcp = MCPServer(
    "fpl-warehouse",
    instructions=(
        "Read-only Fantasy Premier League stats from a daily-updated warehouse. "
        "Players are identified by player_key, which search_players returns. "
        "fixture_outlook looks ahead: upcoming fixtures, FPL difficulty and forecast goals. "
        "Say which gameweek the data runs to (data_to_gameweek) when you answer."
    ),
)


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user="mcp_reader",
        password=os.environ["MCP_READER_PASSWORD"],
        application_name="fpl-mcp-server",
        connect_timeout=5,
        row_factory=dict_row,
    )


@contextmanager
def open_cursor() -> Iterator[psycopg.Cursor]:
    try:
        with connect() as conn, conn.cursor() as cur:
            yield cur
    except psycopg.errors.QueryCanceled:
        raise ToolError(
            "The query took too long and was cancelled. Try again, or ask a narrower question."
        ) from None


def resolve_season(cur: psycopg.Cursor, season: str | None) -> dict:
    rows = cur.execute(SEASONS_SQL).fetchall()
    if not rows:
        raise ToolError("The warehouse has no seasons loaded yet.")
    if season is None:
        return rows[0]
    for row in rows:
        if row["season"] == season:
            return row
    available = ", ".join(row["season"] for row in rows)
    raise ToolError(f"No data for season {season}. Seasons available: {available}.")


def find_player(cur: psycopg.Cursor, player_key: str) -> dict:
    row = cur.execute(FIND_PLAYER_SQL, {"player_key": player_key}).fetchone()
    if row is None:
        raise ToolError(
            f"Unknown player_key {player_key!r}. Call search_players with the player's name to get one."
        )
    return row


def like_pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@mcp.tool(annotations=READ_ONLY)
def search_players(
    name: PlayerName,
    season: Season = None,
) -> SearchResult:
    """Find players by name and get their player_key.

    Use this whenever the user names a player: player_form and player_season need
    the player_key it returns. It matches part of the short name ("García" finds
    "A.García") or of the full name, ignoring case and accents ("Odegaard" finds
    "Ødegaard"). Several players can share a name: if more than
    one matches, show the user their team and position and ask which one they mean.
    Returns at most 10 players, highest season points first.
    """
    with open_cursor() as cur:
        current = resolve_season(cur, season)
        rows = cur.execute(
            SEARCH_SQL,
            {
                "season": current["season"],
                "pattern": like_pattern(name),
                "limit": SEARCH_CAP + 1,
            },
        ).fetchall()
    if not rows:
        raise ToolError(
            f"No player in {current['season']} matches {name!r}. Try the surname only, or check the spelling."
        )
    return SearchResult(
        season=current["season"],
        data_to_gameweek=current["data_to_gameweek"],
        row_count=min(len(rows), SEARCH_CAP),
        truncated=len(rows) > SEARCH_CAP,
        players=[Player(**row) for row in rows[:SEARCH_CAP]],
    )


@mcp.tool(annotations=READ_ONLY)
def top_players(
    position: Annotated[Position, Field(description="GKP, DEF, MID or FWD.")],
    metric: Annotated[
        Metric, Field(description="The stat to rank by. See the tool description.")
    ],
    max_price: Annotated[
        float | None,
        Field(
            ge=MIN_PRICE,
            le=MAX_PRICE,
            description="Only players at or under this price in £m, for example 7.0.",
        ),
    ] = None,
    last_n: Annotated[
        int | None,
        Field(
            ge=1,
            le=10,
            description="Rank over each player's last N games. Leave it out for the whole season.",
        ),
    ] = None,
    season: Season = None,
    limit: Annotated[
        int, Field(ge=1, le=TOP_CAP, description="How many players to return.")
    ] = 10,
) -> TopPlayersResult:
    """Rank the players in one position by one stat.

    Use this for questions like "best midfielders under £7m" or "top defenders by
    clean sheets over the last 5 games". For one named player, use player_season
    or player_form instead.

    Metrics: total_points; points_per_million (points per £1m of current price);
    xgi (expected goals plus expected assists); xgi_per_90; gi (goals plus assists);
    clean_sheets; xgc_per_90 (expected goals conceded per 90, ranked lowest first);
    defcon_per_90 (defensive contributions per 90); defcon_hit_rate (share of
    appearances that earned defensive contribution points); saves.

    Only regular players are ranked: at least 60 minutes per finished gameweek for
    the season, or 60 minutes per game with last_n. min_minutes in the result says
    which floor was used. Returns at most 25 players.
    """
    column, direction = METRICS[metric]
    if last_n is None:
        table, window_filter, window = "player_scouting", sql.SQL(""), "season"
    else:
        table, window_filter = (
            "player_scouting_last_n",
            sql.SQL("and last_n = %(last_n)s"),
        )
        window = f"last {last_n} games"
    query = TOP_SQL.format(
        column=sql.Identifier(column),
        table=sql.Identifier("marts", table),
        window_filter=window_filter,
        direction=sql.SQL(direction),
    )
    with open_cursor() as cur:
        current = resolve_season(cur, season)
        min_minutes = 60 * (last_n or current["finished_gameweeks"])
        rows = cur.execute(
            query,
            {
                "season": current["season"],
                "position": position,
                "min_minutes": min_minutes,
                "max_price": max_price,
                "last_n": last_n,
                "limit": limit + 1,
            },
        ).fetchall()
    if not rows:
        price_note = f" at or under £{max_price}m" if max_price is not None else ""
        raise ToolError(
            f"No {position}{price_note} has at least {min_minutes} minutes in the {window}. "
            "Raise max_price, or use a shorter last_n."
        )
    return TopPlayersResult(
        season=current["season"],
        data_to_gameweek=current["data_to_gameweek"],
        position=position,
        metric=metric,
        window=window,
        min_minutes=min_minutes,
        max_price=max_price,
        row_count=min(len(rows), limit),
        truncated=len(rows) > limit,
        players=[
            RankedPlayer(rank=i, **row) for i, row in enumerate(rows[:limit], start=1)
        ],
    )


@mcp.tool(annotations=READ_ONLY)
def player_form(
    player_key: PlayerKey,
    last_n: Annotated[
        int, Field(ge=1, le=FORM_CAP, description="How many recent games to return.")
    ] = 5,
) -> PlayerFormResult:
    """One player's recent form: game by game, newest first, plus totals over those games.

    Use this for "how has X played lately" or "X's last 5 games". It needs a
    player_key from search_players. Games are the player's team's games, so a game
    they did not play shows 0 minutes. For whole-season numbers, use player_season.
    Returns at most 10 games.
    """
    params = {"player_key": player_key, "last_n": last_n}
    with open_cursor() as cur:
        player = find_player(cur, player_key)
        current = resolve_season(cur, player["season"])
        totals = cur.execute(FORM_TOTALS_SQL, params).fetchone()
        games = cur.execute(FORM_GAMES_SQL, params).fetchall()
    if totals is None:
        raise ToolError(f"{player['web_name']} has no games in {player['season']} yet.")
    return PlayerFormResult(
        player_key=player_key,
        web_name=totals["web_name"],
        team=totals["team"],
        position=totals["position"],
        price=totals["price"],
        season=player["season"],
        data_to_gameweek=current["data_to_gameweek"],
        row_count=len(games),
        games=[Game(**row) for row in games],
        totals=WindowTotals(**totals),
    )


@mcp.tool(annotations=READ_ONLY)
def player_season(player_key: PlayerKey) -> PlayerSeasonResult:
    """One player's season totals and per-90 rates.

    Use this for "is X worth his price", "how many points has X scored", or to
    compare two players (call it once for each). It needs a player_key from
    search_players. The key already fixes the season. For recent games, use
    player_form.
    """
    with open_cursor() as cur:
        player = find_player(cur, player_key)
        current = resolve_season(cur, player["season"])
        row = cur.execute(SEASON_SQL, {"player_key": player_key}).fetchone()
    if row is None:
        raise ToolError(f"{player['web_name']} has no games in {player['season']} yet.")
    return PlayerSeasonResult(data_to_gameweek=current["data_to_gameweek"], **row)


@mcp.tool(annotations=READ_ONLY)
def fixture_outlook(
    gameweeks: Annotated[
        int,
        Field(
            ge=1,
            le=OUTLOOK_CAP,
            description="How many gameweeks to look ahead, starting with the next deadline.",
        ),
    ] = 5,
    team: TeamName = None,
    sort_by: Annotated[
        Literal["attack", "defence"],
        Field(
            description="attack: most forecast goals for first. defence: most expected clean sheets first."
        ),
    ] = "attack",
) -> FixtureOutlookResult:
    """Each team's upcoming fixtures, with FPL difficulty and forecast goals for and against.

    Use this for "which teams have the best fixtures", "who has a double gameweek",
    "whose defenders should I buy", or to check a player's next games before a
    transfer or a captain pick: pass the team from the player's result, for example
    team="ARS". Fixtures and difficulty come from FPL. Forecast goals and clean sheet
    probabilities come from a team-strength model, and can be missing or out of date:
    read forecast_note and say so. Totals add up every fixture in the window, so a
    double gameweek counts twice. Returns at most 20 teams. The forecast for each
    fixture is listed only when team is given.
    """
    with open_cursor() as cur:
        current = resolve_season(cur, None)
        season = current["season"]
        span = cur.execute(GAMEWEEK_RANGE_SQL, {"season": season}).fetchone()
        if span["next_gameweek"] is None:
            raise ToolError(f"Every gameweek deadline in {season} has passed.")
        start = span["next_gameweek"]
        end = min(start + gameweeks - 1, span["last_gameweek"])
        teams = cur.execute(TEAMS_SQL, {"season": season}).fetchall()
        rows = cur.execute(
            OUTLOOK_SQL, {"season": season, "from_gameweek": start, "to_gameweek": end}
        ).fetchall()
    if team is not None and team not in {t["team"] for t in teams}:
        names = ", ".join(t["team"] for t in teams)
        raise ToolError(f"No team {team!r} in {season}. Teams: {names}.")

    forecast = load_forecast()
    outlooks = []
    for t in teams:
        if team is not None and t["team"] != team:
            continue
        fixtures = []
        for row in rows:
            if row["team_id"] != t["team_id"]:
                continue
            key = (row["gameweek"], row["team_id"], row["opponent_id"])
            gf, ga = forecast.fixtures.get(key, (None, None))
            fixtures.append(
                OutlookFixture(
                    gameweek=row["gameweek"],
                    kickoff_time=row["kickoff_time"],
                    opponent=row["opponent"],
                    home=row["home"],
                    difficulty=row["difficulty"],
                    expected_gf=gf,
                    expected_ga=ga,
                    clean_sheet_probability=None
                    if ga is None
                    else round(math.exp(-ga), 2),
                )
            )
        counts = Counter(f.gameweek for f in fixtures)
        known = [f for f in fixtures if f.expected_ga is not None]
        outlooks.append(
            TeamOutlook(
                rank=0,
                team=t["team"],
                fixture_count=len(fixtures),
                blank_gameweeks=[gw for gw in range(start, end + 1) if counts[gw] == 0],
                double_gameweeks=sorted(gw for gw, n in counts.items() if n > 1),
                average_difficulty=round(mean(f.difficulty for f in fixtures), 2)
                if fixtures
                else None,
                expected_gf=round(sum(f.expected_gf for f in known), 2)
                if known
                else None,
                expected_ga=round(sum(f.expected_ga for f in known), 2)
                if known
                else None,
                expected_clean_sheets=round(
                    sum(math.exp(-f.expected_ga) for f in known), 2
                )
                if known
                else None,
                fixtures_without_forecast=len(fixtures) - len(known),
                opponents=[
                    f"GW{f.gameweek} {f.opponent} ({'H' if f.home else 'A'}, {f.difficulty})"
                    for f in fixtures
                ],
                fixtures=fixtures if team is not None else [],
            )
        )

    score = "expected_gf" if sort_by == "attack" else "expected_clean_sheets"
    outlooks.sort(
        key=lambda o: (
            getattr(o, score) is None,
            -(getattr(o, score) or 0),
            o.average_difficulty or 9,
            o.team,
        )
    )
    for rank, outlook in enumerate(outlooks, start=1):
        outlook.rank = rank

    notes = [forecast.note] if forecast.note else []
    if forecast.fixtures:
        if forecast.first_gameweek < start:
            notes.append(
                f"The forecast was made for gameweek {forecast.first_gameweek} onward, "
                f"before gameweek {start}. Its numbers may be out of date."
            )
        missing = sum(o.fixtures_without_forecast for o in outlooks)
        if missing:
            notes.append(
                f"{missing} fixtures have no forecast (the forecast covers gameweeks "
                f"{forecast.first_gameweek}-{forecast.last_gameweek})."
            )
    return FixtureOutlookResult(
        season=season,
        data_to_gameweek=current["data_to_gameweek"],
        from_gameweek=start,
        to_gameweek=end,
        sort_by=sort_by,
        forecast_gameweeks=f"{forecast.first_gameweek}-{forecast.last_gameweek}"
        if forecast.fixtures
        else None,
        forecast_updated_at=forecast.updated_at,
        forecast_note=" ".join(notes),
        teams=outlooks,
    )


@mcp.resource("fpl://schema", mime_type="text/markdown", title="Warehouse schema")
def schema() -> str:
    """The warehouse tables behind the tools, their columns and types, and a glossary of the stats."""
    with open_cursor() as cur:
        rows = cur.execute(SCHEMA_SQL, {"tables": list(SCHEMA_TABLES)}).fetchall()
    columns = defaultdict(list)
    for row in rows:
        columns[row["table_name"]].append(row)
    lines = [
        "# FPL warehouse",
        "",
        "The tools read these tables in the `marts` schema. There is no SQL access: ask through the tools.",
    ]
    for table, about in SCHEMA_TABLES.items():
        if not columns[table]:
            raise ResourceError(f"Table marts.{table} is missing or not readable.")
        lines += ["", f"## {table}", "", about, "", "| column | type |", "|---|---|"]
        lines += [f"| {c['column_name']} | {c['data_type']} |" for c in columns[table]]
    lines += ["", "## Glossary", ""]
    lines += [f"- **{term}**: {meaning}" for term, meaning in GLOSSARY.items()]
    return "\n".join(lines) + "\n"


@mcp.resource("fpl://freshness", mime_type="application/json", title="Data freshness")
def freshness() -> Freshness:
    """How fresh the data is: the latest finished and data-checked gameweek, and the
    last successful run of each pipeline step. The player steps run only after a new
    gameweek finishes, so their dates can be days older than the other steps.
    """
    with open_cursor() as cur:
        seasons = cur.execute(SEASONS_SQL).fetchall()
        steps = cur.execute(FRESHNESS_SQL).fetchall()
    latest = seasons[0] if seasons else {"season": None, "data_to_gameweek": None}
    return Freshness(
        season=latest["season"],
        data_to_gameweek=latest["data_to_gameweek"],
        steps=[StepFreshness(**row) for row in steps],
    )


mcp.prompt(title="Scout a position")(scout_position)
mcp.prompt(title="Check a transfer")(transfer_check)


if __name__ == "__main__":
    mcp.run()
