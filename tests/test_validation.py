import pytest

from mcp_server import server

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
        {"position": "MID", "metric": "bonus"},
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
]


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    def refuse():
        raise AssertionError("a rejected call must not reach the database")

    monkeypatch.setattr(server, "connect", refuse)


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
async def test_tools_list_is_the_five_read_only_tools(client):
    tools = (await client.list_tools()).tools
    assert sorted(t.name for t in tools) == [
        "fixture_outlook",
        "player_form",
        "player_season",
        "search_players",
        "top_players",
    ]
    for tool in tools:
        assert tool.annotations.read_only_hint is True, tool.name
        assert tool.annotations.open_world_hint is False, tool.name
