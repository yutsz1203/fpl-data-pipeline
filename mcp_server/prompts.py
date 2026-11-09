from typing import Annotated, Any

from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS
from pydantic import Field, TypeAdapter, ValidationError

from mcp_server.constants import (
    COMPARE_METRICS,
    CORE_METRICS,
    POSITION_METRICS,
    POSITION_NAMES,
    Budget,
    MetricsArg,
    PlayerName,
    Position,
)

WINDOW_NOTE = (
    "player_form's totals do not have every metric. Show a metric for the last 5 games "
    "only if player_form returns it, and otherwise for the season only."
)


def prompt_arg(name: str, kind: Any, value: str) -> Any:
    try:
        return TypeAdapter(kind).validate_python(value)
    except ValidationError as err:
        raise MCPError(INVALID_PARAMS, f"{name}: {err.errors()[0]['msg']}.") from None


def parse_metrics(value: str) -> tuple[str, ...]:
    names = tuple(name.strip().lower() for name in value.split(",") if name.strip())
    unknown = [name for name in names if name not in COMPARE_METRICS]
    if unknown:
        raise MCPError(
            INVALID_PARAMS,
            f"metrics: unknown {', '.join(unknown)}. Choose from: {', '.join(COMPARE_METRICS)}.",
        )
    return names


def with_core(metrics: tuple[str, ...]) -> str:
    return ", ".join(dict.fromkeys(CORE_METRICS + metrics))


def scout_position(
    position: Annotated[str, Field(description="GKP, DEF, MID or FWD.")],
    budget: Annotated[
        str, Field(description="Most you will pay, in £m, from 3.5 to 20.0.")
    ],
    metrics: MetricsArg = "",
) -> str:
    """Find the best players in one position under a budget, by season and recent form.

    Compares them on the metrics that matter for the position, or on the ones you list.
    """
    position = prompt_arg("position", Position, position)
    budget = prompt_arg("budget", Budget, budget)
    compare = with_core(parse_metrics(metrics) or POSITION_METRICS[position])
    return f"""Scout {POSITION_NAMES[position]} at or under £{budget:.1f}m for my FPL team.

1. Call top_players with position={position}, metric=total_points and max_price={budget}, for the whole season.
2. Call top_players again with the same arguments and last_n=5.
3. Take the top 3 players from step 2. For each one, call player_season, and player_form with last_n=5.
4. Compare them on these metrics: {compare}. Make two short tables, one for the season and one for the last 5 games, with name, team and price in each. {WINDOW_NOTE}
5. Recommend one player in two sentences, and name the numbers that decide it.

Use only the numbers that the tools return. Say which gameweek the data runs to."""


def transfer_check(
    player_out: Annotated[str, Field(description="The player to sell.")],
    player_in: Annotated[str, Field(description="The player to buy.")],
    metrics: MetricsArg = "",
) -> str:
    """Compare the player you want to sell with the player you want to buy.

    Compares them on the metrics that matter for their position, or on the ones you list.
    """
    player_out = prompt_arg("player_out", PlayerName, player_out)
    player_in = prompt_arg("player_in", PlayerName, player_in)
    chosen = parse_metrics(metrics)
    if chosen:
        compare = f"Compare them on these metrics: {with_core(chosen)}."
    else:
        by_position = "\n".join(
            f"   - {position}: {', '.join(names)}"
            for position, names in POSITION_METRICS.items()
        )
        compare = (
            f"Compare them on {', '.join(CORE_METRICS)}, plus the metrics for their "
            f"position (for both positions if they differ):\n{by_position}\n  "
        )
    return f"""I am thinking of selling {player_out} and buying {player_in} in FPL.

1. Call search_players for each name. If a name matches more than one player, show me the matches with team and position, and ask which one I mean. Do not guess.
2. Call player_season and player_form (last_n=5) for both players.
3. If they play different positions, say so first: an FPL transfer must replace a player with one in the same position.
4. {compare} Make two short tables, one for the season and one for the last 5 games, with price in each. {WINDOW_NOTE}
5. Recommend: make the transfer, or keep {player_out}. Give the two or three numbers that decide it.

Use only the numbers that the tools return. Say which gameweek the data runs to."""
