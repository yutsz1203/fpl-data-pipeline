import math
from collections import Counter, defaultdict
from statistics import mean
from typing import Annotated, Literal

import psycopg
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from mcp_server.app import mcp
from mcp_server.classes import (
    FixtureOutlookResult,
    GameweekProjection,
    LineupPlayer,
    OutlookFixture,
    PointsBreakdown,
    ProjectedPlayer,
    ProjectedPointsResult,
    StartCount,
    TeamLineup,
    TeamLineupsResult,
    TeamOutlook,
)
from mcp_server.constants import (
    LINEUPS_CAP,
    OUTLOOK_CAP,
    PLAYER_KEYS_CAP,
    PROJECTION_CAP,
    PROJECTION_METHOD,
    READ_ONLY,
    STATUS_NAMES,
    MaxPrice,
    OneTeam,
    PlayerKey,
    Position,
    TeamName,
)
from mcp_server.db import (
    check_team,
    game_rules,
    next_gameweeks,
    open_cursor,
    resolve_season,
)
from mcp_server.forecast import load_forecast
from mcp_server.projection import (
    PARTS,
    Forecaster,
    availability_for,
    fit_strengths,
    fixture_points,
)
from mcp_server.queries import (
    GAMEWEEK_RANGE_SQL,
    LINEUP_FIXTURES_SQL,
    LINEUPS_SQL,
    LINEUPS_UPDATED_SQL,
    OUTLOOK_SQL,
    PROJECTION_SQL,
    RESULTS_SQL,
    UNSCHEDULED_SQL,
)


def load_forecaster(cur: psycopg.Cursor, season: str) -> Forecaster:
    results = cur.execute(RESULTS_SQL, {"season": season}).fetchall()
    return Forecaster(load_forecast(), fit_strengths(results))


def forecast_notes(
    forecaster: Forecaster, start: int, fallback_count: int, missing: int
) -> str:
    engine = forecaster.engine
    notes = []
    if not engine.fixtures:
        notes.append(engine.note)
        notes.append(
            "Every forecast comes from the fallback model: team strengths fitted on this season's results."
            if forecaster.fallback
            else "Showing FPL difficulty only."
        )
    else:
        if engine.first_gameweek < start:
            notes.append(
                f"The engine's forecast was made for gameweek {engine.first_gameweek} onward, "
                f"before gameweek {start}. Its numbers may be out of date."
            )
        if fallback_count:
            notes.append(
                f"{fallback_count} fixtures outside the engine's forecast (gameweeks "
                f"{engine.first_gameweek}-{engine.last_gameweek}) use the fallback model: "
                "team strengths fitted on this season's results. It is rougher."
            )
    if missing:
        notes.append(f"{missing} fixtures have no forecast.")
    return " ".join(notes)


@mcp.tool(annotations=READ_ONLY)
def fixture_outlook(
    gameweeks: Annotated[
        int,
        Field(
            ge=1,
            le=OUTLOOK_CAP,
            description="How many gameweeks to look ahead, starting with the next deadline.",
        ),
    ] = 5,
    team: TeamName = None,
    sort_by: Annotated[
        Literal["attack", "defence"],
        Field(
            description="attack: most forecast goals for first. defence: most expected clean sheets first."
        ),
    ] = "attack",
) -> FixtureOutlookResult:
    """Each team's upcoming fixtures, with FPL difficulty and forecast goals for and against.

    Use this for "which teams have the best fixtures", "who has a double gameweek",
    "whose defenders should I buy", or to check a player's next games before a
    transfer or a captain pick: pass the team from the player's result, for example
    team="ARS". Fixtures and difficulty come from FPL. Forecast goals and clean sheet
    probabilities come from the prediction engine for the gameweeks it covers, and
    from a rougher fallback model for later ones: read forecast_note and say so.
    Totals add up every fixture in the window, so a double gameweek counts twice.
    blank_gameweeks and double_gameweeks mark them for each team. Returns at most 20
    teams. The forecast for each fixture is listed only when team is given.
    """
    with open_cursor() as cur:
        current = resolve_season(cur, None)
        season = current["season"]
        span = cur.execute(GAMEWEEK_RANGE_SQL, {"season": season}).fetchone()
        if span["next_gameweek"] is None:
            raise ToolError(f"Every gameweek deadline in {season} has passed.")
        start = span["next_gameweek"]
        end = min(start + gameweeks - 1, span["last_gameweek"])
        teams = check_team(cur, season, team)
        rows = cur.execute(
            OUTLOOK_SQL, {"season": season, "from_gameweek": start, "to_gameweek": end}
        ).fetchall()
        unscheduled = cur.execute(UNSCHEDULED_SQL, {"season": season}).fetchone()
        forecaster = load_forecaster(cur, season)

    forecast = forecaster.engine
    fallback_count = 0
    outlooks = []
    for t in teams:
        if team is not None and t["team"] != team:
            continue
        fixtures = []
        for row in rows:
            if row["team_id"] != t["team_id"]:
                continue
            gf, ga, source = forecaster.goals(
                row["gameweek"], row["team_id"], row["opponent_id"], row["home"]
            )
            fallback_count += source == "fallback"
            fixtures.append(
                OutlookFixture(
                    gameweek=row["gameweek"],
                    kickoff_time=row["kickoff_time"],
                    opponent=row["opponent"],
                    home=row["home"],
                    difficulty=row["difficulty"],
                    expected_gf=gf,
                    expected_ga=ga,
                    clean_sheet_probability=None
                    if ga is None
                    else round(math.exp(-ga), 2),
                    forecast_source=source,
                )
            )
        counts = Counter(f.gameweek for f in fixtures)
        known = [f for f in fixtures if f.expected_ga is not None]
        outlooks.append(
            TeamOutlook(
                rank=0,
                team=t["team"],
                fixture_count=len(fixtures),
                blank_gameweeks=[gw for gw in range(start, end + 1) if counts[gw] == 0],
                double_gameweeks=sorted(gw for gw, n in counts.items() if n > 1),
                average_difficulty=round(mean(f.difficulty for f in fixtures), 2)
                if fixtures
                else None,
                expected_gf=round(sum(f.expected_gf for f in known), 2)
                if known
                else None,
                expected_ga=round(sum(f.expected_ga for f in known), 2)
                if known
                else None,
                expected_clean_sheets=round(
                    sum(math.exp(-f.expected_ga) for f in known), 2
                )
                if known
                else None,
                fixtures_without_forecast=len(fixtures) - len(known),
                opponents=[
                    f"GW{f.gameweek} {f.opponent} ({'H' if f.home else 'A'}, {f.difficulty})"
                    for f in fixtures
                ],
                fixtures=fixtures if team is not None else [],
            )
        )

    score = "expected_gf" if sort_by == "attack" else "expected_clean_sheets"
    outlooks.sort(
        key=lambda o: (
            getattr(o, score) is None,
            -(getattr(o, score) or 0),
            o.average_difficulty or 9,
            o.team,
        )
    )
    for rank, outlook in enumerate(outlooks, start=1):
        outlook.rank = rank

    missing = sum(o.fixtures_without_forecast for o in outlooks)
    return FixtureOutlookResult(
        season=season,
        data_to_gameweek=current["data_to_gameweek"],
        from_gameweek=start,
        to_gameweek=end,
        sort_by=sort_by,
        forecast_gameweeks=f"{forecast.first_gameweek}-{forecast.last_gameweek}"
        if forecast.fixtures
        else None,
        forecast_updated_at=forecast.updated_at,
        forecast_note=forecast_notes(forecaster, start, fallback_count, missing),
        unscheduled_fixtures=unscheduled["fixtures"],
        teams=outlooks,
    )


@mcp.tool(annotations=READ_ONLY)
def projected_points(
    gameweeks: Annotated[
        int,
        Field(
            ge=1,
            le=OUTLOOK_CAP,
            description="How many gameweeks to project, starting with the next deadline.",
        ),
    ] = 5,
    position: Annotated[
        Position | None, Field(description="GKP, DEF, MID or FWD.")
    ] = None,
    team: TeamName = None,
    max_price: MaxPrice = None,
    player_keys: Annotated[
        list[PlayerKey] | None,
        Field(
            max_length=PLAYER_KEYS_CAP,
            description="Project only these players, for example the user's squad or two transfer targets.",
        ),
    ] = None,
    limit: Annotated[
        int, Field(ge=1, le=PROJECTION_CAP, description="How many players to return.")
    ] = 10,
) -> ProjectedPointsResult:
    """Projected FPL points for the next gameweeks, player by player, highest first.

    Use this for "who will score most over the next 5 gameweeks", "who should I
    captain", "is X or Y the better buy" or "who to bench". Filter by position,
    team and max_price, or pass player_keys to compare named players or a whole
    squad. Each player has a total, a split by source (goals, clean sheets, bonus
    and so on) and a line per gameweek, where a blank scores 0 and a double counts
    both fixtures. It is a model: read method and forecast_note, and say that the
    numbers are estimates. Injured players are projected from their chance of
    playing and expected return. The points per goal, clean sheet and so on are this
    season's, from the same data as fpl_rules. Returns at most 25 players.
    """
    with open_cursor() as cur:
        current = resolve_season(cur, None)
        season = current["season"]
        start, end = next_gameweeks(cur, season, gameweeks)
        check_team(cur, season, team)
        scoring = game_rules(cur, season)["scoring"]
        fixtures = cur.execute(
            OUTLOOK_SQL, {"season": season, "from_gameweek": start, "to_gameweek": end}
        ).fetchall()
        forecaster = load_forecaster(cur, season)
        rows = cur.execute(
            PROJECTION_SQL,
            {
                "season": season,
                "position": position,
                "team": team,
                "max_price": max_price,
                "player_keys": player_keys,
            },
        ).fetchall()
    if not rows:
        raise ToolError(
            "No player matches those filters. Raise max_price, drop a filter, or get player_keys from search_players."
        )

    by_team = defaultdict(list)
    fallback_count = missing = 0
    for fixture in fixtures:
        gf, ga, source = forecaster.goals(
            fixture["gameweek"],
            fixture["team_id"],
            fixture["opponent_id"],
            fixture["home"],
        )
        fallback_count += source == "fallback"
        missing += source is None
        by_team[fixture["team_id"]].append((fixture, gf, ga))
    if missing == len(fixtures):
        raise ToolError(
            "There is no fixture forecast yet, so points cannot be projected. Use fixture_outlook for difficulty."
        )

    projected = []
    for row in rows:
        totals = dict.fromkeys(PARTS, 0.0)
        weeks = {
            gw: {"opponents": [], "minutes": 0.0, "points": 0.0}
            for gw in range(start, end + 1)
        }
        for fixture, gf, ga in by_team[row["team_id"]]:
            week = weeks[fixture["gameweek"]]
            week["opponents"].append(
                f"{fixture['opponent']} ({'H' if fixture['home'] else 'A'})"
            )
            if gf is None:
                continue
            available = availability_for(
                row, fixture["kickoff_time"], fixture["gameweek"] == start
            )
            parts = fixture_points(row, gf, ga, available, scoring)
            week["minutes"] += parts.pop("minutes")
            week["points"] += sum(parts.values())
            for part, value in parts.items():
                totals[part] += value
        total = sum(totals.values())
        price = float(row["price"])
        projected.append(
            ProjectedPlayer(
                rank=0,
                player_key=row["player_key"],
                web_name=row["web_name"],
                team=row["team"],
                position=row["position"],
                price=price,
                status=STATUS_NAMES.get(row["status"], row["status"]),
                chance_of_playing_next_round=row["chance_of_playing_next_round"],
                predicted_starter=row["predicted_starter"],
                start_rate=row["start_rate"],
                projected_points=round(total, 1),
                points_per_million=round(total / price, 2),
                breakdown=PointsBreakdown(
                    **{part: round(value, 1) for part, value in totals.items()}
                ),
                gameweeks=[
                    GameweekProjection(
                        gameweek=gw,
                        opponents=", ".join(week["opponents"]),
                        expected_minutes=round(week["minutes"]),
                        points=round(week["points"], 1),
                    )
                    for gw, week in weeks.items()
                ],
            )
        )
    projected.sort(key=lambda p: (-p.projected_points, p.price, p.web_name))
    for rank, player in enumerate(projected[:limit], start=1):
        player.rank = rank
    return ProjectedPointsResult(
        season=season,
        data_to_gameweek=current["data_to_gameweek"],
        from_gameweek=start,
        to_gameweek=end,
        forecast_note=forecast_notes(forecaster, start, fallback_count, missing),
        method=PROJECTION_METHOD,
        row_count=min(len(projected), limit),
        truncated=len(projected) > limit,
        players=projected[:limit],
    )


@mcp.tool(annotations=READ_ONLY)
def team_lineups(
    team: OneTeam,
    last_n: Annotated[
        int,
        Field(ge=1, le=LINEUPS_CAP, description="How many played fixtures to return."),
    ] = 3,
) -> TeamLineupsResult:
    """One team's lineups: the predicted 11 for the next fixture and the confirmed 11s of recent ones.

    Use this for "who starts for Arsenal", "is X nailed", "who plays alongside X"
    or "what formation do Spurs play". start_counts adds up starts and bench
    places over the confirmed lineups, which shows who is a regular and who
    rotates. Lineups come from Bzzoiro. A predicted lineup is a guess: give its
    confidence. line is only GKP, DEF, MID or FWD: there is no wing or full-back
    detail. Returns at most 10 confirmed lineups plus 1 predicted.
    """
    with open_cursor() as cur:
        current = resolve_season(cur, None)
        season = current["season"]
        check_team(cur, season, team)
        chosen = cur.execute(
            LINEUP_FIXTURES_SQL, {"season": season, "team": team, "last_n": last_n}
        ).fetchall()
        rows = cur.execute(
            LINEUPS_SQL,
            {
                "season": season,
                "team": team,
                "fixture_keys": [c["fixture_key"] for c in chosen],
            },
        ).fetchall()
        updated = cur.execute(LINEUPS_UPDATED_SQL).fetchone()
    if not rows:
        raise ToolError(
            f"No lineups for {team} yet. They come from the Bzzoiro extract: check the "
            "fpl://freshness resource for the load_bzzoiro step."
        )
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["kickoff_time"]].append(row)
    lineups, counts = [], {}
    for kickoff, players in grouped.items():
        first = players[0]
        confirmed = first["lineup_status"] == "confirmed"
        starters, bench = [], []
        for row in players:
            (starters if row["is_starter"] else bench).append(
                LineupPlayer(
                    player_name=row["player_name"],
                    line=row["line"],
                    player_key=row["player_key"],
                    start_score=row["start_score"],
                )
            )
            if confirmed:
                count = counts.setdefault(
                    row["player_name"],
                    StartCount(
                        player_name=row["player_name"],
                        player_key=row["player_key"],
                        starts=0,
                        bench=0,
                    ),
                )
                if row["is_starter"]:
                    count.starts += 1
                else:
                    count.bench += 1
        lineups.append(
            TeamLineup(
                gameweek=first["gameweek"],
                kickoff_time=kickoff,
                opponent=first["opponent"],
                home=first["home"],
                lineup_status=first["lineup_status"],
                formation=first["formation"],
                confidence=first["confidence"],
                starters=starters,
                bench=bench,
            )
        )
    lineups.sort(
        key=lambda l: (l.lineup_status != "predicted", -l.kickoff_time.timestamp())
    )
    return TeamLineupsResult(
        season=season,
        team=team,
        lineups_updated_at=updated["updated_at"] if updated else None,
        confirmed_lineups=sum(l.lineup_status == "confirmed" for l in lineups),
        lineups=lineups,
        start_counts=sorted(
            counts.values(), key=lambda c: (-c.starts, -c.bench, c.player_name)
        ),
    )
