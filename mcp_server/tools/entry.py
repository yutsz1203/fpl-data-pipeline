import os

from mcp.server.mcpserver.exceptions import ToolError

from mcp_server import fpl_api
from mcp_server.app import mcp
from mcp_server.classes import (
    ChipLeft,
    ChipUse,
    League,
    MyTeamResult,
    Pick,
    SquadTransfer,
)
from mcp_server.constants import LEAGUES_CAP, READ_ONLY_LIVE, EntryId
from mcp_server.db import game_rules, named, open_cursor, resolve_season
from mcp_server.queries import GAMEWEEK_RANGE_SQL, SQUAD_SQL
from mcp_server.squad import chips_left, free_transfers, purchase_prices, selling_price


def entry_leagues(entry: dict) -> list[League]:
    found = entry.get("leagues") or {}
    leagues = [
        League(
            league_id=league["id"],
            name=league["name"],
            kind=kind,
            private=league.get("league_type") == "x",
            entries=league.get("rank_count"),
            rank=league.get("entry_rank"),
            last_rank=league.get("entry_last_rank"),
        )
        for kind in ("classic", "h2h")
        for league in found.get(kind) or []
    ]
    leagues.sort(key=lambda league: (not league.private, league.entries or 0))
    return leagues[:LEAGUES_CAP]


def saved_entry_id(season: str) -> int:
    saved = os.environ.get("FPL_ENTRY_ID", "").strip()
    if not saved.isdigit():
        raise ToolError(
            "No FPL entry id is saved. Ask the user for their entry id: it is the number "
            "in the address of their Points page on the FPL site. Pass it as entry_id, and "
            "ask them to put FPL_ENTRY_ID and FPL_ENTRY_SEASON in .env."
        )
    saved_season = os.environ.get("FPL_ENTRY_SEASON", "").strip()
    if saved_season != season:
        raise ToolError(
            f"The saved FPL entry id is for {saved_season or 'an unknown season'}, and the "
            f"warehouse is on {season}. FPL gives every manager a new entry id each season. "
            "Ask the user for this season's id, pass it as entry_id, and ask them to "
            "update FPL_ENTRY_ID and FPL_ENTRY_SEASON in .env."
        )
    return int(saved)


@mcp.tool(annotations=READ_ONLY_LIVE)
def my_team(
    entry_id: EntryId = None,
) -> MyTeamResult:
    """The user's own FPL squad, read live from the FPL site: picks, prices, bank, transfers, chips and leagues.

    Use this first for any "my team" question: who to sell, who to captain, whether
    a transfer fits the budget. Each pick has the purchase price and the selling
    price, so bank plus a player's selling_price is the money available to replace
    him. Transfers already made for the next gameweek are applied to the picks.
    free_transfers is an estimate: read notes. leagues lists the user's leagues with
    their rank in each: pass a league_id to league_standings or rival_compare. For
    what a chip does, what a hit costs or how selling prices work, call fpl_rules.
    Returns the 15 picks, the 10 newest transfers and at most 25 leagues.
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
    history = fpl_api.fetch(f"entry/{entry_id}/history/")
    transfers = fpl_api.fetch(f"entry/{entry_id}/transfers/")
    sheet = fpl_api.fetch(f"entry/{entry_id}/event/{gameweek}/picks/")

    notes = []
    used = {chip["event"]: chip["name"] for chip in history["chips"]}
    free_hits = {event for event, name in used.items() if name == "freehit"}
    squad_sheet = sheet
    started = entry.get("started_event") or 1
    if sheet.get("active_chip") == "freehit" and gameweek > started:
        squad_sheet = fpl_api.fetch(f"entry/{entry_id}/event/{gameweek - 1}/picks/")
        notes.append(
            f"A Free Hit was played in gameweek {gameweek}. The picks are the squad from "
            f"gameweek {gameweek - 1}, which comes back at the next deadline."
        )
    picks = [dict(pick) for pick in squad_sheet["picks"]]
    bank = squad_sheet["entry_history"]["bank"] / 10

    pending = sorted(
        (t for t in transfers if t["event"] > gameweek), key=lambda t: t["time"]
    )
    for t in pending:
        for pick in picks:
            if pick["element"] == t["element_out"]:
                pick["element"] = t["element_in"]
        bank += (t["element_out_cost"] - t["element_in_cost"]) / 10

    newest = sorted(transfers, key=lambda t: t["time"], reverse=True)[:10]
    wanted = {pick["element"] for pick in picks}
    wanted |= {t["element_in"] for t in newest} | {t["element_out"] for t in newest}
    with open_cursor() as cur:
        rows = cur.execute(
            SQUAD_SQL, {"season": season, "player_ids": list(wanted)}
        ).fetchall()
    players = {row["player_id"]: named(row) for row in rows}

    bought = purchase_prices(transfers, free_hits)
    sell_on_fee = float(rules["settings"]["transfers_sell_on_fee"])
    result_picks, estimated = [], False
    for pick in sorted(picks, key=lambda pick: pick["position"]):
        player = players.get(pick["element"])
        if player is None:
            result_picks.append(
                Pick(
                    slot=pick["position"],
                    player_key=None,
                    web_name=f"FPL player {pick['element']} (not in the warehouse yet)",
                    team=None,
                    position=None,
                    is_captain=pick["is_captain"],
                    is_vice_captain=pick["is_vice_captain"],
                    price=None,
                    purchase_price=None,
                    selling_price=None,
                    status=None,
                    chance_of_playing_next_round=None,
                    news=None,
                )
            )
            continue
        price = float(player["price"])
        purchase = bought.get(pick["element"])
        if purchase is None:
            estimated = True
            purchase = round(price - float(player["price_change_season"]), 1)
        result_picks.append(
            Pick(
                slot=pick["position"],
                player_key=player["player_key"],
                web_name=player["web_name"],
                team=player["team"],
                position=player["position"],
                is_captain=pick["is_captain"],
                is_vice_captain=pick["is_vice_captain"],
                price=price,
                purchase_price=purchase,
                selling_price=selling_price(purchase, price, sell_on_fee),
                status=player["status"],
                chance_of_playing_next_round=player["chance_of_playing_next_round"],
                news=player["news"],
            )
        )
    if estimated:
        notes.append(
            "Players never transferred in are priced at the season's starting price. "
            "That is wrong for a team created after gameweek 1."
        )
    if pending:
        notes.append(
            f"{len(pending)} transfers already made for the next gameweek are applied to the picks and the bank."
        )
    most = 1 + int(rules["settings"]["max_extra_free_transfers"])
    notes.append(
        f"free_transfers is worked out from the transfer history: 1 a gameweek, {most} at "
        "most, unchanged by a Wildcard or Free Hit. Check it against the FPL site before a hit."
    )
    selling = [pick.selling_price for pick in result_picks]
    next_gameweek = span["next_gameweek"]

    def name_of(element: int) -> str:
        return (
            players[element]["web_name"]
            if element in players
            else f"FPL player {element}"
        )

    return MyTeamResult(
        entry_id=entry_id,
        team_name=entry.get("name") or "",
        season=season,
        data_to_gameweek=current["data_to_gameweek"],
        picks_gameweek=gameweek,
        next_gameweek=next_gameweek,
        overall_points=entry.get("summary_overall_points"),
        overall_rank=entry.get("summary_overall_rank"),
        gameweek_points=sheet["entry_history"].get("points"),
        bank=round(bank, 1),
        squad_selling_value=None if None in selling else round(sum(selling), 1),
        free_transfers=free_transfers(history["current"], used, len(pending), most),
        pending_transfers=len(pending),
        active_chip=sheet.get("active_chip"),
        chips_used=[
            ChipUse(chip=name, gameweek=event) for event, name in sorted(used.items())
        ],
        chips_left=[
            ChipLeft(**chip)
            for chip in chips_left(rules["chips"], used, next_gameweek or gameweek)
        ],
        notes=notes,
        picks=result_picks,
        recent_transfers=[
            SquadTransfer(
                gameweek=t["event"],
                time=t["time"],
                player_in=name_of(t["element_in"]),
                price_in=t["element_in_cost"] / 10,
                player_out=name_of(t["element_out"]),
                price_out=t["element_out_cost"] / 10,
            )
            for t in newest
        ],
        leagues=entry_leagues(entry),
    )
