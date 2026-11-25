from mcp_server.constants import CHIP_NAMES, POSITIONS, RULES_DIR, RULES_URL
from mcp_server.db import open_cursor
from mcp_server.queries import GAME_RULES_SQL, SEASONS_SQL


def rules_notes(season: str) -> str:
    files = sorted(RULES_DIR.glob("*.md"))
    wanted = RULES_DIR / f"{season.replace('/', '-')}.md"
    if wanted in files:
        return wanted.read_text(encoding="utf-8")
    if not files:
        return (
            "## Rules the numbers above do not carry\n\n"
            f"No notes are written for {season}. Ask the user to check "
            f"{RULES_URL}.\n"
        )
    old = files[-1]
    return (
        f"> **Warning: these notes were written for {old.stem.replace('-', '/')}, not "
        f"{season}.** The numbers above are current. Anything below may have changed: "
        f"tell the user so, and ask them to check {RULES_URL} and add "
        f"mcp_server/rules/{season.replace('/', '-')}.md.\n\n"
        + old.read_text(encoding="utf-8")
    )


def render_rules(error: type[Exception]) -> str:
    with open_cursor() as cur:
        seasons = cur.execute(SEASONS_SQL).fetchall()
        if not seasons:
            raise error("The warehouse has no seasons loaded yet.")
        season = seasons[0]["season"]
        row = cur.execute(GAME_RULES_SQL, {"season": season}).fetchone()
    if row is None:
        raise error(f"The warehouse has no game rules for {season}.")
    settings, scoring = row["settings"], row["scoring"]
    lines = [
        f"# FPL rules, {season}",
        "",
        f"The numbers in the first three sections are FPL's own, from the snapshot of {row['run_date']}.",
        "",
        "## Squad",
        "",
        f"- {settings['squad_squadsize']} players, {settings['squad_squadplay']} of them start.",
        f"- Budget: £{settings['squad_total_spend'] / 10:.1f}m.",
        f"- At most {settings['squad_team_limit']} players from one club.",
        f"- Free transfers: 1 a gameweek, {1 + settings['max_extra_free_transfers']} held at most.",
        f"- At most {settings['transfers_cap']} transfers in one gameweek without a Wildcard or Free Hit.",
        f"- On a sale the manager keeps {1 - settings['transfers_sell_on_fee']:.0%} of any price rise.",
        "",
        "| position | in the squad | fewest starting | most starting |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {p['position']} | {p['squad_select']} | {p['squad_min_play']} | {p['squad_max_play']} |"
        for p in row["positions"]
    ]
    lines += [
        "",
        "## Scoring",
        "",
        "| action | GKP | DEF | MID | FWD |",
        "|---|---|---|---|---|",
    ]
    for action, points in sorted(scoring.items()):
        if action.startswith("mng_") or action == "special_multiplier":
            continue
        cells = (
            [points.get(p, 0) for p in POSITIONS]
            if isinstance(points, dict)
            else [points] * 4
        )
        if any(cells):
            lines.append(f"| {action} | " + " | ".join(str(c) for c in cells) + " |")
    lines += [
        "",
        (
            "short_play is playing under 60 minutes and long_play is 60 or more. saves is per 3 "
            "saves and goals_conceded is per 2 goals: see the notes below."
        ),
        "",
        "## Chips",
        "",
        "| chip | code | from gameweek | to gameweek |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {CHIP_NAMES.get(c['name'], c['name'])} | {c['name']} | {c['start_event']} | {c['stop_event']} |"
        for c in sorted(row["chips"], key=lambda c: (c["start_event"], c["name"]))
    ]
    return "\n".join(lines) + "\n\n" + rules_notes(season)
