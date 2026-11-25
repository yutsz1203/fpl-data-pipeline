import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from mcp.server.mcpserver.exceptions import ToolError
from psycopg.rows import dict_row

from mcp_server.constants import STATUS_NAMES
from mcp_server.queries import (
    FIND_PLAYER_SQL,
    GAME_RULES_SQL,
    GAMEWEEK_RANGE_SQL,
    SEASONS_SQL,
    TEAMS_SQL,
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


def named(row: dict) -> dict:
    out = dict(row)
    if "status" in out:
        out["status"] = STATUS_NAMES.get(out["status"], out["status"])
    if "news" in out:
        out["news"] = out["news"] or ""
    return out


def check_team(cur: psycopg.Cursor, season: str, team: str | None) -> list[dict]:
    teams = cur.execute(TEAMS_SQL, {"season": season}).fetchall()
    if team is not None and team not in {t["team"] for t in teams}:
        names = ", ".join(t["team"] for t in teams)
        raise ToolError(f"No team {team!r} in {season}. Teams: {names}.")
    return teams


def like_pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def game_rules(cur: psycopg.Cursor, season: str) -> dict:
    row = cur.execute(GAME_RULES_SQL, {"season": season}).fetchone()
    if row is None:
        raise ToolError(f"The warehouse has no game rules for {season}.")
    return row


def next_gameweeks(cur: psycopg.Cursor, season: str, gameweeks: int) -> tuple[int, int]:
    span = cur.execute(GAMEWEEK_RANGE_SQL, {"season": season}).fetchone()
    if span["next_gameweek"] is None:
        raise ToolError(f"Every gameweek deadline in {season} has passed.")
    start = span["next_gameweek"]
    return start, min(start + gameweeks - 1, span["last_gameweek"])
