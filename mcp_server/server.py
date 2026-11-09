import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Literal

import psycopg
from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from psycopg import sql
from psycopg.rows import dict_row
from pydantic import Field, StringConstraints

from mcp_server.classes import (
    Game,
    Player,
    PlayerFormResult,
    PlayerSeasonResult,
    RankedPlayer,
    SearchResult,
    TopPlayersResult,
    WindowTotals,
)
from mcp_server.queries import (
    FIND_PLAYER_SQL,
    FORM_GAMES_SQL,
    FORM_TOTALS_SQL,
    SEARCH_SQL,
    SEASON_SQL,
    SEASONS_SQL,
    TOP_SQL,
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SEARCH_CAP = 10
TOP_CAP = 25
FORM_CAP = 10
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
Position = Literal["GKP", "DEF", "MID", "FWD"]
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

mcp = MCPServer(
    "fpl-warehouse",
    instructions=(
        "Read-only Fantasy Premier League stats from a daily-updated warehouse. "
        "Players are identified by player_key, which search_players returns. "
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
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=2, max_length=40),
        Field(
            description="All or part of the player's name, for example 'Haaland' or 'Erling'."
        ),
    ],
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
            ge=3.5,
            le=20.0,
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


if __name__ == "__main__":
    mcp.run()
