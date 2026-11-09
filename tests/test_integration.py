import time

import psycopg
import pytest

from mcp_server import server
from mcp_server.constants import FORM_CAP, SEARCH_CAP, TOP_CAP

UNKNOWN_KEY = "0" * 32


@pytest.fixture(scope="module", autouse=True)
def warehouse():
    try:
        with server.connect() as conn:
            conn.execute("select 1")
    except (KeyError, psycopg.OperationalError) as err:
        pytest.skip(f"warehouse not reachable: {err}")


async def call(client, tool, args):
    result = await client.call_tool(tool, args)
    assert result.is_error is False, result.content[0].text
    return result.structured_content


async def haaland_key(client):
    found = await call(client, "search_players", {"name": "Haaland"})
    return found["players"][0]["player_key"]


@pytest.mark.anyio
async def test_search_players_stops_at_its_cap(client):
    found = await call(client, "search_players", {"name": "an"})
    assert found["row_count"] == SEARCH_CAP == len(found["players"])
    assert found["truncated"] is True


@pytest.mark.anyio
@pytest.mark.parametrize("last_n", [None, 5])
async def test_top_players_stays_within_its_cap(client, last_n):
    args = {"position": "MID", "metric": "total_points", "limit": TOP_CAP}
    if last_n:
        args["last_n"] = last_n
    top = await call(client, "top_players", args)
    points = [p["total_points"] for p in top["players"]]
    assert 0 < top["row_count"] == len(points) <= TOP_CAP
    assert points == sorted(points, reverse=True)
    assert all(p["minutes"] >= top["min_minutes"] for p in top["players"])


@pytest.mark.anyio
async def test_player_form_stays_within_its_cap(client):
    form = await call(
        client,
        "player_form",
        {"player_key": await haaland_key(client), "last_n": FORM_CAP},
    )
    kickoffs = [g["kickoff_time"] for g in form["games"]]
    assert 0 < form["row_count"] == len(kickoffs) <= FORM_CAP
    assert kickoffs == sorted(kickoffs, reverse=True)
    assert form["totals"]["games"] == form["row_count"]


@pytest.mark.anyio
async def test_player_season_returns_one_player(client):
    key = await haaland_key(client)
    season = await call(client, "player_season", {"player_key": key})
    assert season["player_key"] == key
    assert season["web_name"] == "Haaland"


@pytest.mark.anyio
async def test_unknown_player_key_points_to_search_players(client):
    result = await client.call_tool("player_season", {"player_key": UNKNOWN_KEY})
    assert result.is_error is True
    assert "Call search_players" in result.content[0].text


@pytest.mark.anyio
async def test_unknown_season_lists_the_seasons(client):
    result = await client.call_tool(
        "search_players", {"name": "Haaland", "season": "2019/20"}
    )
    assert result.is_error is True
    assert "Seasons available:" in result.content[0].text


def test_server_connects_as_mcp_reader():
    with server.connect() as conn:
        assert (
            conn.execute("select current_user").fetchone()["current_user"]
            == "mcp_reader"
        )


INSERT_SQL = "insert into marts.dim_team select * from marts.dim_team limit 1"


def test_mcp_reader_sessions_are_read_only():
    with server.connect() as conn, pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        conn.execute(INSERT_SQL)


def test_mcp_reader_cannot_insert_even_with_read_only_off():
    with server.connect() as conn:
        conn.autocommit = True
        conn.execute("set default_transaction_read_only = off")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(INSERT_SQL)


def test_slow_query_is_cancelled():
    started = time.monotonic()
    with server.connect() as conn, pytest.raises(psycopg.errors.QueryCanceled):
        conn.execute("select pg_sleep(5)")
    assert time.monotonic() - started < 4.5
