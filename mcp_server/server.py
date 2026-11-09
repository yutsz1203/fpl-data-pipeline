import os
from pathlib import Path
from typing import Annotated

import psycopg
from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, StringConstraints

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SEARCH_CAP = 10
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

Season = Annotated[
    str | None,
    Field(
        pattern=r"^\d{4}/\d{2}$",
        description="Season in the form '2026/27'. Leave it out for the latest season.",
    ),
]

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


SEASONS_SQL = """
select
    season,
    max(gameweek_id) filter (where is_finished and is_data_checked) as data_to_gameweek
from marts.dim_gameweek
group by season
order by season desc
"""


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


def like_pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


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


SEARCH_SQL = """
select
    p.player_key,
    p.web_name,
    p.full_name,
    s.team,
    s.position,
    p.current_price as price
from marts.dim_player as p
left join marts.player_scouting as s
    on s.player_key = p.player_key
where p.season = %(season)s
    and (
        public.unaccent(p.web_name) ilike public.unaccent(%(pattern)s)
        or public.unaccent(p.full_name) ilike public.unaccent(%(pattern)s)
    )
order by s.total_points desc nulls last, p.web_name
limit %(limit)s
"""


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

    Use this whenever the user names a player: other questions about a player need
    the player_key it returns. It matches part of the short name ("García" finds
    "A.García") or of the full name, ignoring case and accents ("Odegaard" finds
    "Ødegaard"). Several players can share a name: if more than
    one matches, show the user their team and position and ask which one they mean.
    Returns at most 10 players, highest season points first.
    """
    with connect() as conn, conn.cursor() as cur:
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


if __name__ == "__main__":
    mcp.run()
