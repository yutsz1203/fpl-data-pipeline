import pytest

from mcp_server import db

KEY = "0" * 32

GUARDRAILS = [
    (
        "top_players",
        {"position": "ST", "metric": "total_points"},
        "position",
        "Input should be 'GKP'",
    ),
    (
        "top_players",
        {"position": "MID", "metric": "goals"},
        "metric",
        "Input should be 'total_points'",
    ),
    (
        "top_players",
        {"position": "MID", "metric": "xgi", "limit": 500},
        "limit",
        "less than or equal to 25",
    ),
    (
        "top_players",
        {"position": "MID", "metric": "xgi", "limit": 0},
        "limit",
        "greater than or equal to 1",
    ),
    (
        "top_players",
        {"position": "MID", "metric": "xgi", "max_price": 99},
        "max_price",
        "less than or equal to 20",
    ),
    (
        "top_players",
        {"position": "MID", "metric": "xgi", "max_price": 3.4},
        "max_price",
        "greater than or equal to 3.5",
    ),
    (
        "top_players",
        {"position": "MID", "metric": "xgi", "last_n": 0},
        "last_n",
        "greater than or equal to 1",
    ),
    (
        "top_players",
        {"position": "MID", "metric": "xgi", "last_n": 11},
        "last_n",
        "less than or equal to 10",
    ),
    (
        "top_players",
        {"position": "MID", "metric": "xgi", "season": "2026"},
        "season",
        "should match pattern",
    ),
    ("search_players", {"name": "a"}, "name", "at least 2 characters"),
    ("search_players", {"name": "x" * 41}, "name", "at most 40 characters"),
    (
        "search_players",
        {"name": "Haaland", "season": "26/27"},
        "season",
        "should match pattern",
    ),
    ("player_form", {"player_key": "fake"}, "player_key", "should match pattern"),
    (
        "player_form",
        {"player_key": KEY, "last_n": 11},
        "last_n",
        "less than or equal to 10",
    ),
    ("player_season", {"player_key": "Haaland"}, "player_key", "should match pattern"),
    ("fixture_outlook", {"gameweeks": 0}, "gameweeks", "greater than or equal to 1"),
    ("fixture_outlook", {"gameweeks": 9}, "gameweeks", "less than or equal to 8"),
    ("fixture_outlook", {"team": "Arsenal"}, "team", "should match pattern"),
    ("fixture_outlook", {"sort_by": "goals"}, "sort_by", "Input should be 'attack'"),
    ("search_players", {"team": "Arsenal"}, "team", "should match pattern"),
    ("search_players", {"position": "ST"}, "position", "Input should be 'GKP'"),
    (
        "top_players",
        {"position": "MID", "metric": "xgi", "min_minutes": -1},
        "min_minutes",
        "greater than or equal to 0",
    ),
    ("availability", {"team": "arsenal"}, "team", "should match pattern"),
    ("player_status", {"player_key": "Saka"}, "player_key", "should match pattern"),
    (
        "market_watch",
        {"sort_by": "price"},
        "sort_by",
        "Input should be 'transfers_in'",
    ),
    ("market_watch", {"limit": 26}, "limit", "less than or equal to 25"),
    ("my_team", {"entry_id": 0}, "entry_id", "greater than or equal to 1"),
    ("projected_points", {"gameweeks": 9}, "gameweeks", "less than or equal to 8"),
    ("projected_points", {"limit": 26}, "limit", "less than or equal to 25"),
    (
        "projected_points",
        {"player_keys": [KEY] * 21},
        "player_keys",
        "at most 20 items",
    ),
    (
        "team_lineups",
        {"team": "MCI", "last_n": 11},
        "last_n",
        "less than or equal to 10",
    ),
    (
        "league_standings",
        {"league_id": 0},
        "league_id",
        "greater than or equal to 1",
    ),
    (
        "rival_compare",
        {"league_id": 5, "rivals": 11},
        "rivals",
        "less than or equal to 10",
    ),
    (
        "rival_compare",
        {"league_id": 5, "who": "everyone"},
        "who",
        "Input should be 'nearest'",
    ),
]


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    def refuse():
        raise AssertionError("a rejected call must not reach the database")

    monkeypatch.setattr(db, "connect", refuse)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool", "args", "field", "reason"),
    GUARDRAILS,
    ids=[f"{tool}-{field}-{args[field]!r}"[:60] for tool, args, field, _ in GUARDRAILS],
)
async def test_bad_argument_is_rejected(client, tool, args, field, reason):
    result = await client.call_tool(tool, args)
    assert result.is_error is True
    text = result.content[0].text
    assert f"Error executing tool {tool}" in text
    assert f"\n{field}\n" in text
    assert reason in text


@pytest.mark.anyio
async def test_search_players_needs_a_filter(client):
    result = await client.call_tool("search_players", {})
    assert result.is_error is True
    assert (
        "at least one of name, team, position and max_price" in result.content[0].text
    )


LIVE_TOOLS = {"my_team", "league_standings", "rival_compare"}


@pytest.mark.anyio
async def test_tools_are_read_only_and_only_three_leave_the_warehouse(client):
    tools = (await client.list_tools()).tools
    assert sorted(t.name for t in tools) == [
        "availability",
        "fixture_outlook",
        "fpl_rules",
        "league_standings",
        "market_watch",
        "my_team",
        "player_form",
        "player_season",
        "player_status",
        "projected_points",
        "rival_compare",
        "search_players",
        "team_lineups",
        "top_players",
    ]
    for tool in tools:
        assert tool.annotations.read_only_hint is True, tool.name
        assert tool.annotations.open_world_hint is (tool.name in LIVE_TOOLS), tool.name


@pytest.mark.anyio
async def test_instructions_send_rule_questions_to_fpl_rules(client):
    assert "call fpl_rules" in client.instructions


@pytest.mark.anyio
async def test_plan_gameweek_prompt_names_the_league_and_the_tools(client):
    prompt = await client.get_prompt("plan_gameweek", {"league": " Graz "})
    text = prompt.messages[0].content.text
    assert "name contains 'Graz'" in text
    for tool in ("fpl_rules", "my_team", "projected_points", "rival_compare"):
        assert tool in text
    default = (await client.get_prompt("plan_gameweek", {})).messages[0].content.text
    assert "rival_compare" not in default
    assert "Do not look at leagues or rivals" in default
    assert "\n8. End with a short plan" in default
    assert "\n9. End with a short plan" in text
