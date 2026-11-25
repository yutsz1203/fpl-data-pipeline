from typing import Annotated

from mcp.server.mcpserver.exceptions import ToolError
from psycopg import sql
from pydantic import Field

from mcp_server.app import mcp
from mcp_server.classes import (
    Game,
    Player,
    PlayerFormResult,
    PlayerSeasonResult,
    PlayerStatusResult,
    RankedPlayer,
    SearchResult,
    Split,
    StatusChange,
    TopPlayersResult,
    WindowTotals,
)
from mcp_server.constants import (
    FORM_CAP,
    HISTORY_CAP,
    METRICS,
    READ_ONLY,
    SEARCH_CAP,
    TOP_CAP,
    MaxPrice,
    Metric,
    PlayerKey,
    PlayerName,
    Position,
    Season,
    TeamName,
)
from mcp_server.db import (
    check_team,
    find_player,
    like_pattern,
    named,
    open_cursor,
    resolve_season,
)
from mcp_server.queries import (
    FORM_GAMES_SQL,
    FORM_TOTALS_SQL,
    NEXT_LINEUP_SQL,
    OWNERSHIP_WEEK_AGO_SQL,
    SEARCH_SQL,
    SEASON_SQL,
    SPLITS_SQL,
    STATUS_HISTORY_SQL,
    STATUS_SQL,
    TOP_SQL,
)


@mcp.tool(annotations=READ_ONLY)
def search_players(
    name: PlayerName | None = None,
    team: TeamName = None,
    position: Annotated[
        Position | None, Field(description="GKP, DEF, MID or FWD.")
    ] = None,
    max_price: MaxPrice = None,
    season: Season = None,
) -> SearchResult:
    """Find players by name, team, position or price, and get their player_key.

    Use this whenever the user names a player: the other player tools need the
    player_key it returns. It matches part of the short name ("García" finds
    "A.García") or of the full name, ignoring case and accents ("Odegaard" finds
    "Ødegaard"). Several players can share a name: if more than one matches, show
    the user their team and position and ask which one they mean. Give at least one
    of name, team, position and max_price: team="ARS" with position="DEF" lists
    Arsenal's defenders. Players with no minutes yet are included. Returns at most
    10 players, highest season points first.
    """
    if name is None and team is None and position is None and max_price is None:
        raise ToolError("Give at least one of name, team, position and max_price.")
    with open_cursor() as cur:
        current = resolve_season(cur, season)
        check_team(cur, current["season"], team)
        rows = cur.execute(
            SEARCH_SQL,
            {
                "season": current["season"],
                "pattern": None if name is None else like_pattern(name),
                "team": team,
                "position": position,
                "max_price": max_price,
                "limit": SEARCH_CAP + 1,
            },
        ).fetchall()
    if not rows:
        if name is None:
            raise ToolError(
                f"No player in {current['season']} matches those filters. Raise max_price or drop a filter."
            )
        raise ToolError(
            f"No player in {current['season']} matches {name!r}. Try the surname only, check the spelling, or drop the other filters."
        )
    return SearchResult(
        season=current["season"],
        data_to_gameweek=current["data_to_gameweek"],
        row_count=min(len(rows), SEARCH_CAP),
        truncated=len(rows) > SEARCH_CAP,
        players=[Player(**named(row)) for row in rows[:SEARCH_CAP]],
    )


@mcp.tool(annotations=READ_ONLY)
def top_players(
    position: Annotated[Position, Field(description="GKP, DEF, MID or FWD.")],
    metric: Annotated[
        Metric, Field(description="The stat to rank by. See the tool description.")
    ],
    max_price: MaxPrice = None,
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
    min_minutes: Annotated[
        int | None,
        Field(
            ge=0,
            le=3420,
            description="Leave out players with fewer minutes in the window. Leave it out for the default floor. Use a low number to see rotation players and recent signings.",
        ),
    ] = None,
    team: TeamName = None,
) -> TopPlayersResult:
    """Rank the players in one position by one stat.

    Use this for questions like "best midfielders under £7m" or "top defenders by
    clean sheets over the last 5 games". For one named player, use player_season
    or player_form instead.

    Metrics: total_points; points_per_million (points per £1m of current price);
    xgi (expected goals plus expected assists); xgi_per_90; gi (goals plus assists);
    clean_sheets; xgc_per_90 (expected goals conceded per 90, ranked lowest first);
    defcon_per_90 (defensive contributions per 90); defcon_hit_rate (share of
    appearances that earned defensive contribution points); saves; bonus; bps (bonus
    points system score).

    By default only regular players are ranked: at least 60 minutes per finished
    gameweek for the season, or 60 minutes per game with last_n. Pass min_minutes
    to change that floor. min_minutes in the result says which floor was used.
    Per-90 metrics over few minutes are noisy. Returns at most 25 players.
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
        check_team(cur, current["season"], team)
        if min_minutes is None:
            min_minutes = 60 * (last_n or current["finished_gameweeks"])
        rows = cur.execute(
            query,
            {
                "season": current["season"],
                "position": position,
                "min_minutes": min_minutes,
                "max_price": max_price,
                "team": team,
                "last_n": last_n,
                "limit": limit + 1,
            },
        ).fetchall()
    if not rows:
        price_note = f" at or under £{max_price}m" if max_price is not None else ""
        team_note = f" at {team}" if team is not None else ""
        raise ToolError(
            f"No {position}{team_note}{price_note} has at least {min_minutes} minutes in the {window}. "
            "Raise max_price, lower min_minutes, or use a shorter last_n."
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
    """One player's season totals, per-90 rates, set-piece duties and splits.

    Use this for "is X worth his price", "how many points has X scored", "does X
    take penalties", "is X better at home", or to compare two players (call it once
    for each). It needs a player_key from search_players. The key already fixes the
    season. splits breaks the season down by home and away and by FPL fixture
    difficulty. For recent games, use player_form.
    """
    with open_cursor() as cur:
        player = find_player(cur, player_key)
        current = resolve_season(cur, player["season"])
        row = cur.execute(SEASON_SQL, {"player_key": player_key}).fetchone()
        splits = cur.execute(SPLITS_SQL, {"player_key": player_key}).fetchall()
    if row is None:
        raise ToolError(f"{player['web_name']} has no games in {player['season']} yet.")
    return PlayerSeasonResult(
        data_to_gameweek=current["data_to_gameweek"],
        splits=[Split(**split) for split in splits],
        **named(row),
    )


@mcp.tool(annotations=READ_ONLY)
def player_status(player_key: PlayerKey) -> PlayerStatusResult:
    """One player's availability, price, ownership and role, with the days they changed.

    Use this for "is X fit", "when is X back", "is X's price rising", "is X nailed
    to start" or "does X take penalties". It needs a player_key from
    search_players. history lists the days on which status, news or price changed.
    Transfers in and out are for the current gameweek so far.
    """
    params = {"player_key": player_key}
    with open_cursor() as cur:
        find_player(cur, player_key)
        row = cur.execute(STATUS_SQL, params).fetchone()
        history = cur.execute(
            STATUS_HISTORY_SQL, {**params, "limit": HISTORY_CAP}
        ).fetchall()
        week_ago = cur.execute(OWNERSHIP_WEEK_AGO_SQL, params).fetchone()
        lineup = cur.execute(NEXT_LINEUP_SQL, params).fetchone()
    return PlayerStatusResult(
        **named(row),
        selected_pct_week_ago=week_ago["selected_pct"] if week_ago else None,
        predicted_starter=lineup["is_starter"] if lineup else None,
        predicted_lineup_gameweek=lineup["gameweek"] if lineup else None,
        history=[StatusChange(**named(change)) for change in history],
    )
