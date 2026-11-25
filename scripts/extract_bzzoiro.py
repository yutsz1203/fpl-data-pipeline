import json
import os
import shutil
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import psycopg
import requests
from config import BZZOIRO_LEAGUE_ID, BZZOIRO_URL, BZZOIRO_USER_AGENT, DATA_DIR
from db import connect
from extract_sync import parse_run_date
from http_client import get_json
from run_log import track_run

SKIP_EXIT_CODE = 99
PAGE_SIZE = 200
PREDICTED_DAYS = 14


def get(session: requests.Session, path: str) -> dict:
    return get_json(session, BZZOIRO_URL + path).json()


def get_events(session: requests.Session, season_id: int) -> list[dict]:
    events, offset = [], 0
    while True:
        page = get(
            session,
            f"events/?league_id={BZZOIRO_LEAGUE_ID}&season_id={season_id}"
            f"&limit={PAGE_SIZE}&offset={offset}",
        )
        events += page["results"]
        if not page["next"] or not page["results"]:
            return events
        offset += len(page["results"])


def confirmed_lineups(conn: psycopg.Connection) -> set[int]:
    rows = conn.execute(
        "select event_id from raw.bzzoiro_lineups "
        "where payload ->> 'lineup_status' = 'confirmed'"
    )
    return {row[0] for row in rows}


def lineups_wanted(events: list[dict], confirmed: set[int]) -> list[int]:
    soon = datetime.now(UTC) + timedelta(days=PREDICTED_DAYS)
    wanted = []
    for event in events:
        kickoff = datetime.fromisoformat(event["event_date"])
        played = event["status"] == "finished" and event["id"] not in confirmed
        upcoming = event["status"] != "finished" and kickoff <= soon
        if played or upcoming:
            wanted.append(event["id"])
    return wanted


def write(path: Path, body: dict | list) -> None:
    path.write_text(json.dumps(body), encoding="utf-8")


def extract(conn: psycopg.Connection, session: requests.Session, out_dir: Path) -> int:
    league = get(session, f"leagues/{BZZOIRO_LEAGUE_ID}/")
    events = get_events(session, league["current_season"]["id"])
    write(out_dir / "events.json", events)

    team_ids = sorted(
        {e["home_team_id"] for e in events} | {e["away_team_id"] for e in events}
    )
    for team_id in team_ids:
        write(
            out_dir / "squads" / f"{team_id}.json",
            get(session, f"teams/{team_id}/squad/"),
        )

    saved = 0
    for event_id in lineups_wanted(events, confirmed_lineups(conn)):
        lineup = get(session, f"events/{event_id}/lineups/")
        if lineup["lineup_status"] != "unavailable":
            write(out_dir / "lineups" / f"{event_id}.json", lineup)
            saved += 1
    print(
        f"{len(events)} events, {len(team_ids)} squads, {saved} lineups",
        file=sys.stderr,
    )
    return len(events) + len(team_ids) + saved


def reset_dir(run_date: date) -> Path:
    out_dir = DATA_DIR / str(run_date) / "bzzoiro"
    shutil.rmtree(out_dir, ignore_errors=True)
    (out_dir / "squads").mkdir(parents=True)
    (out_dir / "lineups").mkdir()
    return out_dir


def main():
    run_date = parse_run_date("Extract lineups and injuries from the Bzzoiro API.")
    token = os.getenv("BZZOIRO_TOKEN")
    if not token:
        print("BZZOIRO_TOKEN is empty: skipping the Bzzoiro extract.")
        raise SystemExit(SKIP_EXIT_CODE)
    try:
        with (
            connect() as conn,
            track_run(conn, run_date, "extract_bzzoiro") as run,
            requests.Session() as session,
        ):
            session.headers.update(
                {"Authorization": f"Token {token}", "User-Agent": BZZOIRO_USER_AGENT}
            )
            run.rows_loaded = extract(conn, session, reset_dir(run_date))
    except (requests.RequestException, ValueError) as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status in (401, 403):
            print("Bzzoiro rejected BZZOIRO_TOKEN. Get a new key and put it in .env.")
        print(f"Bzzoiro extract failed, the rest of the pipeline goes on: {e}")
        raise SystemExit(SKIP_EXIT_CODE)


if __name__ == "__main__":
    main()
