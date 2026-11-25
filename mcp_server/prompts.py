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
    LeagueName,
    MetricsArg,
    PlayerName,
    Position,
)

WINDOW_NOTE = (
    "player_form's totals do not have every metric. Show a metric for the last 5 games "
    "only if player_form returns it, and otherwise for the season only."
)


FORECAST_NOTE = "If fixture_outlook's forecast_note is not empty, say what it says and lean on difficulty."


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
    outlook = "expected_clean_sheets" if position in ("GKP", "DEF") else "expected_gf"
    return f"""Scout {POSITION_NAMES[position]} at or under £{budget:.1f}m for my FPL team.

1. Call top_players with position={position}, metric=total_points and max_price={budget}, for the whole season.
2. Call top_players again with the same arguments and last_n=5.
3. Take the top 3 players from step 2. For each one, call player_season, and player_form with last_n=5.
4. Call fixture_outlook once for each of their teams, with gameweeks=5. Call projected_points with position={position}, max_price={budget} and gameweeks=5, and player_status for each of the 3.
5. Compare them on these metrics: {compare}. Make two short tables, one for the season and one for the last 5 games, with name, team and price in each. {WINDOW_NOTE}
6. Make a third table for the next 5 gameweeks: opponents, average difficulty, and the team's {outlook}. Mark blank and double gameweeks. {FORECAST_NOTE}
7. Say if any of them is flagged, is not a regular starter, or is rising or falling in price. Show each one's projected points, and say that they are a model's estimate.
8. Recommend one player in two sentences, and name the numbers that decide it: form, fixtures and availability all count.

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
2. Call player_season, player_form (last_n=5) and player_status for both players, fixture_outlook (gameweeks=5) for each player's team, and projected_points with both player_keys and gameweeks=5. Call my_team to see the selling price of {player_out}, the bank and the free transfers. If my_team fails, say what it asks for and go on without it.
3. If they play different positions, say so first: an FPL transfer must replace a player with one in the same position.
4. {compare} Make two short tables, one for the season and one for the last 5 games, with price in each. {WINDOW_NOTE}
5. Make a third table for the next 5 gameweeks: opponents, average difficulty, expected goals for (for attacking players) or expected clean sheets (for goalkeepers and defenders). Mark blank and double gameweeks. {FORECAST_NOTE}
6. Call fpl_rules for the cost of an extra transfer. Say whether the money works: bank plus the selling price of {player_out} against the price of {player_in}, and whether the transfer is free or costs points. Say if either player is flagged or is not a regular starter.
7. Recommend: make the transfer, or keep {player_out}. Give the two or three numbers that decide it: form, fixtures, availability and projected points all count. Projected points are a model's estimate: say so.

Use only the numbers that the tools return. Say which gameweek the data runs to."""


def plan_gameweek(
    league: Annotated[
        str,
        Field(
            description="Optional: all or part of the name of one of your leagues. Leave it out to plan for the most points. Give it to also compare with your rivals in that league."
        ),
    ] = "",
) -> str:
    """Plan the next gameweek for your own team: transfers or a roll, chips, captain and bench.

    Aims for the most points. Compares any player it suggests buying with the one it suggests selling. With a league name, it also finds the threats and differentials against your rivals there.
    """
    league = prompt_arg("league", LeagueName, league)
    if league:
        goal = f"Aim for the most points, and weigh the result against my rivals in the league whose name contains {league!r}."
        rivals = f"""
4. From my_team's leagues, take the league whose name contains {league!r}. If none or more than one matches, show me the league names and ask. Call rival_compare with its league_id and rivals=5. List the main threats (players my rivals own and I do not) and my differentials (my players that few of them own). Call projected_points for the top threats with gameweeks=5 to see which ones matter."""
        owned = ", and how many of the compared rivals own each"
        captain = " Say if the captain most rivals have is the safe pick, or if a differential captain is worth the risk given my rank."
        last = ", and one line on the main threat from my league rivals"
    else:
        goal = "Aim for the most points from my own team. Do not look at leagues or rivals."
        rivals, owned, captain, last = "", "", "", ""
    steps = iter(range(5 if league else 4, 10))
    return f"""Plan my FPL team for the next gameweek. {goal}

1. Call fpl_rules. Take every rule from it: free transfers, the cost of a hit, what each chip does and its gameweek window. Do not use rules from memory.
2. Call my_team. Note the bank, free_transfers, pending_transfers, chips_left, and every pick that is flagged.
3. Call projected_points with my 15 player_keys and gameweeks=1, and again with gameweeks=5. Call fixture_outlook with gameweeks=5 to find blank and double gameweeks. {FORECAST_NOTE}{rivals}
{next(steps)}. Find my weakest picks: flagged or not starting, low projected points over 5 gameweeks, or bad fixtures. For each one, at most 3, look for replacements: call projected_points with the same position, gameweeks=5 and max_price set to the bank plus that pick's selling_price. Call market_watch to see who is rising in price. Keep to the club limit in fpl_rules.
{next(steps)}. Choose one of these and say why the others lose:
   - Roll the transfer. This is right when no move gains much, and it is worth more while I hold fewer than the most free transfers that can be saved.
   - Make one or more transfers. Say if any of them costs a hit. A hit is worth it only if the gain over the next 5 gameweeks is clearly above its cost.
   - Play a chip. Only a chip whose playable_now is true. Name the gameweek that would suit it better if waiting is right: a double gameweek for Bench Boost or Triple Captain, a blank for Free Hit.
{next(steps)}. For each transfer you suggest, compare the player out with the player in. Call player_season, player_form (last_n=5) and player_status for both. Show one table: price, season points, last-5 points, projected points for the next 1 and 5 gameweeks, next 5 opponents and status{owned}. Say what the money looks like after the move.
{next(steps)}. Pick the captain and vice-captain from the gameweeks=1 projection.{captain} Give the starting 11 and the bench order. The formation must be legal under fpl_rules.
{next(steps)}. End with a short plan: transfers or roll, chip or none, captain and vice-captain, and bench order{last}.

Use only the numbers that the tools return. Projected points are a model's estimate and free_transfers is an estimate: say so. Say which gameweek the data runs to."""
