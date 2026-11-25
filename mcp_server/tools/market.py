from typing import Annotated, Literal

from mcp.server.mcpserver.exceptions import ToolError
from psycopg import sql
from pydantic import Field

from mcp_server.app import mcp
from mcp_server.classes import (
    AvailabilityResult,
    FlaggedPlayer,
    MarketPlayer,
    MarketWatchResult,
)
from mcp_server.constants import (
    AVAILABILITY_CAP,
    FLAGGED_STATUSES,
    MARKET_CAP,
    MARKET_ORDERS,
    READ_ONLY,
    MaxPrice,
    Position,
    TeamName,
)
from mcp_server.db import check_team, named, open_cursor, resolve_season
from mcp_server.queries import AVAILABILITY_SQL, MARKET_SQL


@mcp.tool(annotations=READ_ONLY)
def availability(team: TeamName = None) -> AvailabilityResult:
    """Players who are flagged: doubtful, injured, suspended or out of the squad.

    Use this for "who is injured at Arsenal", "any doubts in my defence's clubs" or
    before a transfer. Pass team for one club's full list, or leave it out for the
    most-owned flagged players in the league. Status, chance of playing and news
    come from FPL and are as of the last daily run. Injury type and expected return
    come from Bzzoiro and can be empty. For one player's history, use player_status.
    Returns at most 60 players, most-owned first.
    """
    with open_cursor() as cur:
        current = resolve_season(cur, None)
        check_team(cur, current["season"], team)
        rows = cur.execute(
            AVAILABILITY_SQL,
            {
                "season": current["season"],
                "statuses": FLAGGED_STATUSES,
                "team": team,
                "limit": AVAILABILITY_CAP + 1,
            },
        ).fetchall()
    return AvailabilityResult(
        season=current["season"],
        data_to_gameweek=current["data_to_gameweek"],
        team=team,
        row_count=min(len(rows), AVAILABILITY_CAP),
        truncated=len(rows) > AVAILABILITY_CAP,
        players=[FlaggedPlayer(**named(row)) for row in rows[:AVAILABILITY_CAP]],
    )


@mcp.tool(annotations=READ_ONLY)
def market_watch(
    sort_by: Annotated[
        Literal[
            "transfers_in",
            "transfers_out",
            "price_rise_gameweek",
            "price_fall_gameweek",
            "price_rise_season",
            "price_fall_season",
            "ownership",
        ],
        Field(
            description="transfers_in and transfers_out rank by net transfers this gameweek. The price options rank by price change this gameweek or this season."
        ),
    ] = "transfers_in",
    position: Annotated[
        Position | None, Field(description="GKP, DEF, MID or FWD.")
    ] = None,
    team: TeamName = None,
    max_price: MaxPrice = None,
    limit: Annotated[
        int, Field(ge=1, le=MARKET_CAP, description="How many players to return.")
    ] = 10,
) -> MarketWatchResult:
    """The transfer market: who managers are buying and selling, price changes and ownership.

    Use this for "who is everyone buying", "who is about to rise or fall in price",
    "most-owned midfielders" or to spot a player to buy before a price rise. Heavy
    net transfers in usually come before a price rise, and heavy net transfers out
    before a fall. Numbers are as of the last daily run. Returns at most 25 players.
    """
    query = MARKET_SQL.format(order=sql.SQL(MARKET_ORDERS[sort_by]))
    with open_cursor() as cur:
        current = resolve_season(cur, None)
        check_team(cur, current["season"], team)
        rows = cur.execute(
            query,
            {
                "season": current["season"],
                "position": position,
                "team": team,
                "max_price": max_price,
                "limit": limit,
            },
        ).fetchall()
    if not rows:
        raise ToolError(
            "No player matches those filters. Raise max_price or drop a filter."
        )
    return MarketWatchResult(
        season=current["season"],
        data_to_gameweek=current["data_to_gameweek"],
        sort_by=sort_by,
        row_count=len(rows),
        players=[
            MarketPlayer(rank=i, **named(row)) for i, row in enumerate(rows, start=1)
        ],
    )
