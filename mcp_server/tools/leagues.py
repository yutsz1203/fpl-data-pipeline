from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Literal

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from mcp_server import fpl_api
from mcp_server.app import mcp
from mcp_server.classes import (
    ChipUse,
    LeagueRow,
    LeagueStandingsResult,
    Rival,
    RivalCompareResult,
    RivalPlayer,
)
from mcp_server.constants import (
    FPL_FETCH_WORKERS,
    READ_ONLY_LIVE,
    RIVALS_CAP,
    STANDINGS_PAGE_SIZE,
    THREATS_CAP,
    EntryId,
    LeagueId,
)
from mcp_server.db import game_rules, named, open_cursor, resolve_season
from mcp_server.queries import GAMEWEEK_RANGE_SQL, SQUAD_SQL
from mcp_server.squad import chips_left
from mcp_server.tools.entry import saved_entry_id


def standings_page(league_id: int, page: int) -> dict:
    return fpl_api.fetch(
        f"leagues-classic/{league_id}/standings/?page_standings={page}",
        missing=fpl_api.NO_LEAGUE,
    )


def league_of(entry: dict, league_id: int) -> dict | None:
    for league in (entry.get("leagues") or {}).get("classic") or []:
        if league["id"] == league_id:
            return league
    return None


def page_of(rank: int | None) -> int | None:
    return None if rank is None else (rank - 1) // STANDINGS_PAGE_SIZE + 1


@mcp.tool(annotations=READ_ONLY_LIVE)
def league_standings(
    league_id: LeagueId,
    page: Annotated[
        int,
        Field(
            ge=1,
            le=10_000,
            description="Page of the table, 50 teams a page. Page 1 is the top.",
        ),
    ] = 1,
    entry_id: EntryId = None,
) -> LeagueStandingsResult:
    """One classic league's table, read live from the FPL site: rank, team, manager and points.

    Use this for "how am I doing in my league", "who is top of X" or "how far behind
    am I". Get the league_id from my_team's leagues. Each page has 50 teams: my_page
    is the page with the user's row. To compare squads with rivals, use
    rival_compare. Head-to-head leagues are not supported.
    """
    with open_cursor() as cur:
        season = resolve_season(cur, None)["season"]
    if entry_id is None:
        try:
            entry_id = saved_entry_id(season)
        except ToolError:
            entry_id = None
    table = standings_page(league_id, page)
    rows = table["standings"]["results"]
    if not rows and page > 1:
        raise ToolError(f"Page {page} of this league has no teams. Try a lower page.")
    mine = None
    if entry_id is not None:
        mine = league_of(fpl_api.fetch(f"entry/{entry_id}/"), league_id)
    my_rank = mine["entry_rank"] if mine else None
    return LeagueStandingsResult(
        league_id=league_id,
        league_name=table["league"]["name"],
        updated_at=table.get("last_updated_data"),
        page=page,
        has_next_page=table["standings"]["has_next"],
        my_rank=my_rank,
        my_page=page_of(my_rank),
        row_count=len(rows),
        managers=[
            LeagueRow(
                rank=row["rank"],
                last_rank=row["last_rank"] or None,
                entry_id=row["entry"],
                team_name=row["entry_name"],
                manager_name=row["player_name"],
                total_points=row["total"],
                gameweek_points=row["event_total"],
                is_me=row["entry"] == entry_id,
            )
            for row in rows
        ],
    )


def load_squad(entry_id: int, gameweek: int) -> tuple[dict, dict] | None:
    try:
        sheet = fpl_api.fetch(f"entry/{entry_id}/event/{gameweek}/picks/")
        history = fpl_api.fetch(f"entry/{entry_id}/history/")
    except ToolError:
        return None
    return sheet, history


def role_of(pick: dict) -> str:
    if pick["is_captain"]:
        return "captain"
    if pick["is_vice_captain"]:
        return "vice-captain"
    return "starter" if pick["position"] <= 11 else "bench"


def choose_rivals(
    league_id: int, entry_id: int, my_rank: int | None, rivals: int, who: str
) -> tuple[dict, list[dict], dict | None]:
    my_page = page_of(my_rank) or 1
    table = standings_page(league_id, 1 if who == "top" else my_page)
    rows = list(table["standings"]["results"])
    me = next((row for row in rows if row["entry"] == entry_id), None)
    if who == "top":
        if me is None and my_page > 1:
            mine = standings_page(league_id, my_page)["standings"]["results"]
            me = next((row for row in mine if row["entry"] == entry_id), None)
        others = [row for row in rows if row["entry"] != entry_id]
        return table, others[:rivals], me
    index = rows.index(me) if me else len(rows) // 2
    if my_page > 1 and index < rivals:
        before = standings_page(league_id, my_page - 1)["standings"]["results"]
        rows, index = before + rows, index + len(before)
    if table["standings"]["has_next"] and len(rows) - 1 - index < rivals:
        rows += standings_page(league_id, my_page + 1)["standings"]["results"]
    near = sorted(
        (
            (abs(position - index), position, row)
            for position, row in enumerate(rows)
            if row["entry"] != entry_id
        ),
        key=lambda item: item[:2],
    )
    chosen = sorted(near[:rivals], key=lambda item: item[1])
    return table, [row for _, _, row in chosen], me


@mcp.tool(annotations=READ_ONLY_LIVE)
def rival_compare(
    league_id: LeagueId,
    rivals: Annotated[
        int,
        Field(ge=1, le=RIVALS_CAP, description="How many rivals to compare with."),
    ] = 5,
    who: Annotated[
        Literal["nearest", "top"],
        Field(
            description="nearest: the teams closest to the user in the table, above and below. top: the league leaders."
        ),
    ] = "nearest",
    entry_id: EntryId = None,
) -> RivalCompareResult:
    """The user's squad against rivals in one classic league: who owns whom, threats and differentials.

    Use this for "how do I catch the leader", "who do my rivals have that I don't",
    "what are my differentials" or to choose a captain against a mini-league. Get
    the league_id from my_team's leagues. threats are players the user does not
    own, most-owned by the rivals first. my_players are the user's 15 with how many
    rivals own each: a low count is a differential. Each rival has their captain,
    chips and the players the user does not own. Squads are the ones from the last
    deadline: transfers made since do not show. Reads the FPL site live, two
    requests per rival, so keep rivals small. Follow it with projected_points on
    the threats and differentials to see which ones matter in the next gameweeks.
    """
    with open_cursor() as cur:
        current = resolve_season(cur, None)
        season = current["season"]
        span = cur.execute(GAMEWEEK_RANGE_SQL, {"season": season}).fetchone()
        rules = game_rules(cur, season)
    if entry_id is None:
        entry_id = saved_entry_id(season)
    entry = fpl_api.fetch(f"entry/{entry_id}/")
    gameweek = entry.get("current_event")
    if gameweek is None:
        raise ToolError(
            "This FPL team has not played a gameweek yet, so it has no picks."
        )
    mine = league_of(entry, league_id)
    if mine is None:
        raise ToolError(
            f"FPL team {entry_id} is not in classic league {league_id}. "
            "Call my_team for the leagues it is in."
        )
    my_rank = mine.get("entry_rank")
    table, chosen, me = choose_rivals(league_id, entry_id, my_rank, rivals, who)
    if not chosen:
        raise ToolError("This league has no other team to compare with.")
    my_total = me["total"] if me else entry.get("summary_overall_points")

    ids = [entry_id] + [row["entry"] for row in chosen]
    with ThreadPoolExecutor(max_workers=FPL_FETCH_WORKERS) as pool:
        squads = dict(zip(ids, pool.map(lambda i: load_squad(i, gameweek), ids)))
    if squads[entry_id] is None:
        raise ToolError(
            f"FPL has no gameweek {gameweek} team sheet for the user's team. Try again later."
        )
    notes = [
        (
            f"Every squad is the one from the gameweek {gameweek} deadline. Transfers "
            "made since then, the user's included, do not show. my_team has the user's own."
        )
    ]
    skipped = [row["entry_name"] for row in chosen if squads[row["entry"]] is None]
    if skipped:
        notes.append(f"No team sheet could be read for: {', '.join(skipped)}.")
    chosen = [row for row in chosen if squads[row["entry"]] is not None]
    if not chosen:
        raise ToolError("No rival's team sheet could be read. Try again later.")

    elements = {
        pick["element"]
        for found in squads.values()
        if found
        for pick in found[0]["picks"]
    }
    with open_cursor() as cur:
        rows = cur.execute(
            SQUAD_SQL, {"season": season, "player_ids": list(elements)}
        ).fetchall()
    players = {row["player_id"]: named(row) for row in rows}

    def name_of(element: int) -> str:
        return (
            players[element]["web_name"]
            if element in players
            else f"FPL player {element}"
        )

    my_sheet = squads[entry_id][0]
    my_picks = {pick["element"]: pick for pick in my_sheet["picks"]}
    if my_sheet.get("active_chip") == "freehit":
        notes.append(
            f"The user played a Free Hit in gameweek {gameweek}: their squad here is the "
            "Free Hit one, and it goes back to the earlier squad at the next deadline."
        )
    next_gameweek = span["next_gameweek"] or gameweek
    owned, started, captained = Counter(), Counter(), Counter()
    result_rivals = []
    for row in chosen:
        sheet, history = squads[row["entry"]]
        picks = sorted(sheet["picks"], key=lambda pick: pick["position"])
        for pick in picks:
            owned[pick["element"]] += 1
            started[pick["element"]] += pick["position"] <= 11
            captained[pick["element"]] += pick["is_captain"]
        used = {chip["event"]: chip["name"] for chip in history["chips"]}
        if sheet.get("active_chip") == "freehit":
            notes.append(
                f"{row['entry_name']} played a Free Hit in gameweek {gameweek}: their "
                "squad goes back to the earlier one at the next deadline."
            )
        week = sheet.get("entry_history") or {}
        value = week.get("value")
        marks = {"captain": " (C)", "bench": " (bench)"}
        result_rivals.append(
            Rival(
                entry_id=row["entry"],
                team_name=row["entry_name"],
                manager_name=row["player_name"],
                rank=row["rank"],
                total_points=row["total"],
                points_ahead_of_me=row["total"] - (my_total or 0),
                gameweek_points=week.get("points"),
                captain=next(
                    (name_of(p["element"]) for p in picks if p["is_captain"]), None
                ),
                vice_captain=next(
                    (name_of(p["element"]) for p in picks if p["is_vice_captain"]),
                    None,
                ),
                active_chip=sheet.get("active_chip"),
                chips_used=[
                    ChipUse(chip=name, gameweek=event)
                    for event, name in sorted(used.items())
                ],
                chips_left=[
                    chip["chip"]
                    for chip in chips_left(rules["chips"], used, next_gameweek)
                ],
                transfers_made=week.get("event_transfers"),
                hit_points=week.get("event_transfers_cost"),
                squad_value=None if value is None else value / 10,
                players_shared_with_me=sum(p["element"] in my_picks for p in picks),
                players_i_do_not_own=[
                    name_of(p["element"]) + marks.get(role_of(p), "")
                    for p in picks
                    if p["element"] not in my_picks
                ],
            )
        )

    def rival_player(element: int) -> RivalPlayer:
        player = players.get(element, {})
        pick = my_picks.get(element)
        return RivalPlayer(
            player_key=player.get("player_key"),
            web_name=name_of(element),
            team=player.get("team"),
            position=player.get("position"),
            price=player.get("price"),
            status=player.get("status"),
            chance_of_playing_next_round=player.get("chance_of_playing_next_round"),
            owned_by=owned[element],
            started_by=started[element],
            captained_by=captained[element],
            my_role=role_of(pick) if pick else None,
        )

    threats = sorted(
        (element for element in owned if element not in my_picks),
        key=lambda e: (-owned[e], -captained[e], -started[e], name_of(e)),
    )
    if len(threats) > THREATS_CAP:
        notes.append(
            f"threats shows the {THREATS_CAP} most-owned of {len(threats)} players."
        )
    return RivalCompareResult(
        league_id=league_id,
        league_name=table["league"]["name"],
        season=season,
        data_to_gameweek=current["data_to_gameweek"],
        squads_gameweek=gameweek,
        my_entry_id=entry_id,
        my_rank=me["rank"] if me else my_rank,
        my_total_points=my_total,
        rivals_compared=len(result_rivals),
        notes=notes,
        rivals=result_rivals,
        threats=[rival_player(e) for e in threats[:THREATS_CAP]],
        my_players=[
            rival_player(e)
            for e in sorted(my_picks, key=lambda e: (owned[e], my_picks[e]["position"]))
        ],
    )
