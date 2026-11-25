import math
import time

import psycopg
import pytest

from mcp_server import db, fpl_api
from mcp_server.constants import FORM_CAP, SEARCH_CAP, STATUS_NAMES, TOP_CAP
from mcp_server.rulebook import rules_notes
from mcp_server.tools import fixtures

UNKNOWN_KEY = "0" * 32


@pytest.fixture(scope="module", autouse=True)
def warehouse():
    try:
        with db.connect() as conn:
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


@pytest.mark.anyio
async def test_fixture_outlook_without_engine_uses_the_fallback(client, monkeypatch):
    monkeypatch.delenv("FORECAST_CSV", raising=False)
    outlook = await call(client, "fixture_outlook", {"gameweeks": 3})
    assert len(outlook["teams"]) == 20
    assert outlook["forecast_gameweeks"] is None
    assert "No engine forecast is set up" in outlook["forecast_note"]
    assert "fallback model" in outlook["forecast_note"]
    team = outlook["teams"][0]
    assert team["expected_gf"] > 0
    assert team["fixtures_without_forecast"] == 0
    assert team["fixtures"] == []
    assert len(team["opponents"]) == team["fixture_count"]
    goals = [t["expected_gf"] for t in outlook["teams"]]
    assert goals == sorted(goals, reverse=True)


@pytest.mark.anyio
async def test_fixture_outlook_without_any_forecast_uses_difficulty(
    client, monkeypatch
):
    monkeypatch.delenv("FORECAST_CSV", raising=False)
    monkeypatch.setattr(fixtures, "fit_strengths", lambda results: None)
    outlook = await call(client, "fixture_outlook", {"gameweeks": 3})
    assert "FPL difficulty only" in outlook["forecast_note"]
    assert outlook["teams"][0]["expected_gf"] is None
    difficulty = [t["average_difficulty"] for t in outlook["teams"]]
    assert difficulty == sorted(difficulty)


@pytest.mark.anyio
async def test_fixture_outlook_prefers_the_engine_forecast(
    client, monkeypatch, tmp_path
):
    monkeypatch.delenv("FORECAST_CSV", raising=False)
    plain = await call(client, "fixture_outlook", {"gameweeks": 2, "team": "ARS"})
    fixture = plain["teams"][0]["fixtures"][0]
    assert fixture["forecast_source"] == "fallback"
    ids = {}
    with db.connect() as conn:
        for row in conn.execute(
            "select team_short_name, team_id from marts.dim_team where season = %s",
            (plain["season"],),
        ):
            ids[row["team_short_name"]] = row["team_id"]
    forecast = tmp_path / "fixture_forecast.csv"
    forecast.write_text(
        "gameweek,team_id,opponent_id,home,expected_gf,expected_ga\n"
        f"{fixture['gameweek']},{ids['ARS']},{ids[fixture['opponent']]},"
        f"{fixture['home']},1.8,0.5\n"
    )
    monkeypatch.setenv("FORECAST_CSV", str(forecast))

    joined = await call(client, "fixture_outlook", {"gameweeks": 2, "team": "ARS"})
    team = joined["teams"][0]
    first = team["fixtures"][0]
    assert (first["expected_gf"], first["expected_ga"]) == (1.8, 0.5)
    assert first["forecast_source"] == "engine"
    assert first["clean_sheet_probability"] == round(math.exp(-0.5), 2)
    sources = [f["forecast_source"] for f in team["fixtures"][1:]]
    assert sources == ["fallback"] * len(sources)
    assert (
        f"{len(sources)} fixtures outside the engine's forecast"
        in (joined["forecast_note"])
    )
    assert (
        joined["forecast_gameweeks"] == f"{fixture['gameweek']}-{fixture['gameweek']}"
    )


@pytest.mark.anyio
async def test_fixture_outlook_unknown_team_lists_the_teams(client):
    result = await client.call_tool("fixture_outlook", {"team": "XYZ"})
    assert result.is_error is True
    assert "Teams: ARS" in result.content[0].text


@pytest.mark.anyio
async def test_search_players_by_team_and_position_includes_unused_players(client):
    found = await call(client, "search_players", {"team": "ARS", "position": "GKP"})
    assert {p["team"] for p in found["players"]} == {"ARS"}
    assert {p["position"] for p in found["players"]} == {"GKP"}
    assert min(p["minutes"] for p in found["players"]) == 0
    assert found["players"][0]["status"] in STATUS_NAMES.values()


@pytest.mark.anyio
async def test_top_players_min_minutes_replaces_the_default_floor(client):
    args = {"position": "FWD", "metric": "bonus", "limit": TOP_CAP}
    regulars = await call(client, "top_players", args)
    everyone = await call(client, "top_players", args | {"min_minutes": 1})
    assert everyone["min_minutes"] == 1
    assert regulars["min_minutes"] > 1
    assert everyone["row_count"] >= regulars["row_count"]


@pytest.mark.anyio
async def test_player_season_has_home_and_away_splits(client):
    season = await call(
        client, "player_season", {"player_key": await haaland_key(client)}
    )
    splits = {s["split"]: s for s in season["splits"]}
    assert {"home", "away"} <= set(splits)
    assert (
        splits["home"]["total_points"] + splits["away"]["total_points"]
        == season["total_points"]
    )
    assert season["bonus"] == splits["home"]["bonus"] + splits["away"]["bonus"]


@pytest.mark.anyio
async def test_availability_lists_only_flagged_players(client):
    flagged = await call(client, "availability", {})
    assert 0 < flagged["row_count"] <= 60
    assert "available" not in {p["status"] for p in flagged["players"]}
    owned = [p["selected_pct"] for p in flagged["players"]]
    assert owned == sorted(owned, reverse=True)


@pytest.mark.anyio
async def test_player_status_returns_role_and_history(client):
    status = await call(
        client, "player_status", {"player_key": await haaland_key(client)}
    )
    assert status["web_name"] == "Haaland"
    assert status["recent_games"] > 0
    dates = [h["run_date"] for h in status["history"]]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.anyio
async def test_market_watch_ranks_by_net_transfers(client):
    market = await call(client, "market_watch", {"sort_by": "transfers_out"})
    net = [p["net_transfers_gameweek"] for p in market["players"]]
    assert net == sorted(net)
    assert market["row_count"] == 10


@pytest.mark.anyio
async def test_projected_points_ranks_and_adds_up(client):
    result = await call(
        client, "projected_points", {"gameweeks": 3, "position": "MID", "limit": 5}
    )
    points = [p["projected_points"] for p in result["players"]]
    assert points == sorted(points, reverse=True)
    assert result["truncated"] is True
    top = result["players"][0]
    assert len(top["gameweeks"]) == result["to_gameweek"] - result["from_gameweek"] + 1
    assert sum(g["points"] for g in top["gameweeks"]) == pytest.approx(
        top["projected_points"], abs=0.2
    )
    assert sum(top["breakdown"].values()) == pytest.approx(
        top["projected_points"], abs=0.5
    )


@pytest.mark.anyio
async def test_projected_points_for_named_players(client):
    key = await haaland_key(client)
    result = await call(
        client, "projected_points", {"gameweeks": 1, "player_keys": [key]}
    )
    assert [p["web_name"] for p in result["players"]] == ["Haaland"]
    assert result["truncated"] is False


@pytest.mark.anyio
async def test_team_lineups_have_eleven_starters(client):
    with db.connect() as conn:
        if (
            conn.execute("select count(*) as n from marts.fct_lineup").fetchone()["n"]
            == 0
        ):
            pytest.skip("no Bzzoiro lineups loaded")
    result = await call(client, "team_lineups", {"team": "MCI", "last_n": 2})
    assert result["confirmed_lineups"] == 2
    assert all(len(lineup["starters"]) == 11 for lineup in result["lineups"])
    confirmed = [l for l in result["lineups"] if l["lineup_status"] == "confirmed"]
    kickoffs = [l["kickoff_time"] for l in confirmed]
    assert kickoffs == sorted(kickoffs, reverse=True)
    assert sum(c["starts"] for c in result["start_counts"]) == 22


def fake_fpl(squad, bank=15, transfers=(), chips=(), active_chip=None):
    def fetch(path):
        if path.endswith("/history/"):
            return {
                "current": [
                    {"event": 1, "event_transfers": 0, "event_transfers_cost": 0},
                    {"event": 2, "event_transfers": 0, "event_transfers_cost": 0},
                ],
                "chips": list(chips),
            }
        if path.endswith("/transfers/"):
            return list(transfers)
        if "/picks/" in path:
            return {
                "active_chip": active_chip,
                "entry_history": {"bank": bank, "points": 50},
                "picks": [
                    {
                        "element": element,
                        "position": slot,
                        "is_captain": slot == 1,
                        "is_vice_captain": slot == 2,
                    }
                    for slot, element in enumerate(squad, start=1)
                ],
            }
        return {
            "name": "Test XI",
            "current_event": 2,
            "started_event": 1,
            "summary_overall_points": 100,
            "summary_overall_rank": 1000,
        }

    return fetch


def some_players(count):
    with db.connect() as conn:
        return conn.execute(
            """
            select player_id, web_name, current_price, price_change_season
            from marts.dim_player
            where season = (select max(season) from marts.dim_player)
                and status = 'a'
                and price_change_season > 0.1
            order by current_selected_pct desc
            limit %s
            """,
            (count,),
        ).fetchall()


@pytest.mark.anyio
async def test_my_team_prices_the_squad_and_applies_pending_transfers(
    client, monkeypatch
):
    held, sold, bought = some_players(3)
    transfers = [
        {
            "event": 3,
            "time": "2026-11-09T10:00:00Z",
            "element_in": bought["player_id"],
            "element_in_cost": 70,
            "element_out": sold["player_id"],
            "element_out_cost": 60,
        }
    ]
    monkeypatch.setattr(
        fpl_api,
        "fetch",
        fake_fpl([held["player_id"], sold["player_id"]], transfers=transfers),
    )
    team = await call(client, "my_team", {"entry_id": 123})
    assert team["team_name"] == "Test XI"
    assert [p["web_name"] for p in team["picks"]] == [
        held["web_name"],
        bought["web_name"],
    ]
    assert team["bank"] == 0.5
    assert team["pending_transfers"] == 1
    assert team["free_transfers"] == 1
    first, second = team["picks"]
    start_price = float(held["current_price"] - held["price_change_season"])
    assert first["purchase_price"] == pytest.approx(start_price)
    assert start_price < first["selling_price"] < first["price"]
    assert second["purchase_price"] == 7.0
    assert first["is_captain"] is True
    assert {c["chip"] for c in team["chips_left"]} == {
        "wildcard",
        "freehit",
        "bboost",
        "3xc",
    }


@pytest.mark.anyio
async def test_my_team_after_a_free_hit_shows_the_squad_before_it(client, monkeypatch):
    (held,) = some_players(1)
    monkeypatch.setattr(
        fpl_api,
        "fetch",
        fake_fpl(
            [held["player_id"]],
            chips=[{"name": "freehit", "event": 2}],
            active_chip="freehit",
        ),
    )
    team = await call(client, "my_team", {"entry_id": 123})
    assert "Free Hit" in team["notes"][0]
    assert "freehit" not in {
        c["chip"] for c in team["chips_left"] if c["from_gameweek"] < 20
    }


@pytest.mark.anyio
async def test_my_team_asks_for_a_new_id_when_the_saved_one_is_from_another_season(
    client, monkeypatch
):
    def refuse(path):
        raise AssertionError("a stale entry id must not reach the FPL site")

    monkeypatch.setattr(fpl_api, "fetch", refuse)
    monkeypatch.setenv("FPL_ENTRY_ID", "123")
    monkeypatch.setenv("FPL_ENTRY_SEASON", "2019/20")
    result = await client.call_tool("my_team", {})
    assert result.is_error is True
    assert "new entry id each season" in result.content[0].text
    monkeypatch.setenv("FPL_ENTRY_ID", "")
    result = await client.call_tool("my_team", {})
    assert "No FPL entry id is saved" in result.content[0].text


def fake_league(squads, me=1, league_id=77):
    ranks = {entry: rank for rank, entry in enumerate(squads, start=1)}
    totals = {entry: 510 - 10 * rank for entry, rank in ranks.items()}

    def fetch(path, missing=None):
        if path.startswith("leagues-classic/"):
            assert path.startswith(f"leagues-classic/{league_id}/standings/")
            return {
                "league": {"id": league_id, "name": "Test League"},
                "last_updated_data": "2026-11-10T04:00:00Z",
                "standings": {
                    "has_next": False,
                    "page": 1,
                    "results": [
                        {
                            "entry": entry,
                            "entry_name": f"Team {entry}",
                            "player_name": f"Manager {entry}",
                            "rank": rank,
                            "last_rank": rank,
                            "total": totals[entry],
                            "event_total": 50,
                        }
                        for entry, rank in ranks.items()
                    ],
                },
            }
        entry = int(path.split("/")[1])
        if path.endswith("/history/"):
            chips = [] if entry == me else [{"name": "bboost", "event": 1}]
            return {"current": [], "chips": chips}
        if path.endswith("/transfers/"):
            return []
        if "/picks/" in path:
            return {
                "active_chip": None,
                "entry_history": {
                    "bank": 5,
                    "points": 50,
                    "value": 1005,
                    "event_transfers": 1,
                    "event_transfers_cost": 0,
                },
                "picks": [
                    {
                        "element": element,
                        "position": slot,
                        "is_captain": slot == 1,
                        "is_vice_captain": slot == 2,
                    }
                    for slot, element in enumerate(squads[entry], start=1)
                ],
            }
        return {
            "name": f"Team {entry}",
            "current_event": 2,
            "started_event": 1,
            "summary_overall_points": totals[entry],
            "summary_overall_rank": 1000,
            "leagues": {
                "classic": [
                    {
                        "id": 314,
                        "name": "Overall",
                        "league_type": "s",
                        "rank_count": 11_000_000,
                        "entry_rank": 1000,
                        "entry_last_rank": 900,
                    },
                    {
                        "id": league_id,
                        "name": "Test League",
                        "league_type": "x",
                        "rank_count": len(squads),
                        "entry_rank": ranks[entry],
                        "entry_last_rank": ranks[entry],
                    },
                ],
                "h2h": [],
            },
        }

    return fetch


@pytest.mark.anyio
async def test_my_team_lists_leagues_with_private_ones_first(client, monkeypatch):
    (held,) = some_players(1)
    monkeypatch.setattr(fpl_api, "fetch", fake_league({1: [held["player_id"]]}))
    team = await call(client, "my_team", {"entry_id": 1})
    assert [(l["league_id"], l["private"]) for l in team["leagues"]] == [
        (77, True),
        (314, False),
    ]
    assert team["leagues"][0]["rank"] == 1


@pytest.mark.anyio
async def test_league_standings_marks_the_users_row(client, monkeypatch):
    monkeypatch.setattr(fpl_api, "fetch", fake_league({2: [], 1: [], 3: []}))
    table = await call(client, "league_standings", {"league_id": 77, "entry_id": 1})
    assert table["league_name"] == "Test League"
    assert [m["entry_id"] for m in table["managers"]] == [2, 1, 3]
    assert [m["is_me"] for m in table["managers"]] == [False, True, False]
    assert (table["my_rank"], table["my_page"]) == (2, 1)
    assert table["has_next_page"] is False


@pytest.mark.anyio
async def test_rival_compare_finds_threats_and_differentials(client, monkeypatch):
    a, b, c, d = (p["player_id"] for p in some_players(4))
    names = {p["player_id"]: p["web_name"] for p in some_players(4)}
    squads = {2: [a, b, c], 1: [a, d], 3: [b, c]}
    monkeypatch.setattr(fpl_api, "fetch", fake_league(squads))
    result = await call(client, "rival_compare", {"league_id": 77, "entry_id": 1})
    assert result["rivals_compared"] == 2
    assert (result["my_rank"], result["my_total_points"]) == (2, 490)
    assert [(t["web_name"], t["owned_by"]) for t in result["threats"]] == [
        (names[b], 2),
        (names[c], 2),
    ]
    assert result["threats"][0]["captained_by"] == 1
    assert all(t["my_role"] is None for t in result["threats"])
    assert [
        (p["web_name"], p["owned_by"], p["my_role"]) for p in result["my_players"]
    ] == [
        (names[d], 0, "vice-captain"),
        (names[a], 1, "captain"),
    ]
    leader, chaser = result["rivals"]
    assert (leader["entry_id"], leader["points_ahead_of_me"]) == (2, 10)
    assert leader["captain"] == names[a]
    assert leader["players_shared_with_me"] == 1
    assert leader["players_i_do_not_own"] == [names[b], names[c]]
    assert chaser["points_ahead_of_me"] == -10
    assert chaser["players_i_do_not_own"] == [f"{names[b]} (C)", names[c]]
    assert chaser["chips_used"] == [{"chip": "bboost", "gameweek": 1}]
    assert "bboost" in chaser["chips_left"]
    assert len(chaser["chips_left"]) == 7
    assert "gameweek 2 deadline" in result["notes"][0]


@pytest.mark.anyio
async def test_rival_compare_needs_a_league_the_user_is_in(client, monkeypatch):
    monkeypatch.setattr(fpl_api, "fetch", fake_league({1: [], 2: []}))
    result = await client.call_tool("rival_compare", {"league_id": 78, "entry_id": 1})
    assert result.is_error is True
    assert "is not in classic league 78" in result.content[0].text


@pytest.mark.anyio
async def test_fpl_rules_tool_returns_the_rules_resource_text(client):
    resource = (await client.read_resource("fpl://rules")).contents[0].text
    result = await client.call_tool("fpl_rules", {})
    assert result.is_error is False
    assert result.content[0].text == resource


@pytest.mark.anyio
async def test_rules_resource_has_this_seasons_numbers_and_notes(client):
    text = (await client.read_resource("fpl://rules")).contents[0].text
    assert "| goals_scored | 10 | 6 | 5 | 4 |" in text
    assert "| Wildcard | wildcard |" in text
    assert "Warning" not in text


def test_rules_notes_warn_when_the_season_has_no_notes():
    notes = rules_notes("2099/00")
    assert notes.startswith("> **Warning")
    assert "not 2099/00" in notes
    assert "mcp_server/rules/2099-00.md" in notes


def test_server_connects_as_mcp_reader():
    with db.connect() as conn:
        assert (
            conn.execute("select current_user").fetchone()["current_user"]
            == "mcp_reader"
        )


INSERT_SQL = "insert into marts.dim_team select * from marts.dim_team limit 1"


def test_mcp_reader_sessions_are_read_only():
    with db.connect() as conn, pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        conn.execute(INSERT_SQL)


def test_mcp_reader_cannot_insert_even_with_read_only_off():
    with db.connect() as conn:
        conn.autocommit = True
        conn.execute("set default_transaction_read_only = off")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(INSERT_SQL)


def test_slow_query_is_cancelled():
    started = time.monotonic()
    with db.connect() as conn, pytest.raises(psycopg.errors.QueryCanceled):
        conn.execute("select pg_sleep(5)")
    assert time.monotonic() - started < 4.5
