import requests
from mcp.server.mcpserver.exceptions import ToolError

FPL_API = "https://fantasy.premierleague.com/api/"
USER_AGENT = "fpl-warehouse-mcp/0.1"
TIMEOUT_SECONDS = 10
NO_ENTRY = (
    "FPL has no team with that entry id. Entry ids change every season: "
    "ask the user for this season's id."
)
NO_LEAGUE = (
    "FPL has no classic league with that id. League ids change every season: "
    "call my_team for the user's leagues."
)


def fetch(path: str, missing: str = NO_ENTRY) -> dict | list:
    try:
        response = requests.get(
            FPL_API + path,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        raise ToolError("The FPL site did not answer. Try again in a minute.") from None
    if response.status_code == 404:
        raise ToolError(missing)
    if response.status_code != 200:
        raise ToolError(
            f"The FPL site answered with status {response.status_code}. "
            "It is often closed while a gameweek updates. Try again later."
        )
    try:
        return response.json()
    except ValueError:
        raise ToolError(
            "The FPL site is updating and sent no data. Try again later."
        ) from None
