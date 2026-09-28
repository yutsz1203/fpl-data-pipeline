import argparse
from datetime import date

import psycopg
from config import DATA_DIR
from db import connect
from extract_players import load_player_ids
from psycopg import sql
from run_log import track_run

SNAPSHOT_FILES = {"master": "master.json", "fixtures": "fixtures.json"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Loading raw data into db.")
    parser.add_argument(
        "--run-date",
        required=True,
        type=date.fromisoformat,
        help="date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=[*SNAPSHOT_FILES, "players"],
        help="Provide a source.",
    )

    return parser.parse_args()


def load_snapshot(conn: psycopg.Connection, source: str, run_date: date) -> int:
    source_path = DATA_DIR / str(run_date) / SNAPSHOT_FILES[source]
    try:
        payload = source_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"{source_path} not found. Run extract_{source} first.")
    table = sql.Identifier("raw", source)
    with conn.transaction():
        deleted = conn.execute(
            sql.SQL("DELETE FROM {} WHERE run_date = %s").format(table), (run_date,)
        ).rowcount
        inserted = conn.execute(
            sql.SQL("INSERT INTO {} (run_date, payload) VALUES (%s, %s::jsonb)").format(
                table
            ),
            (run_date, payload),
        ).rowcount
    print(f"deleted={deleted}, inserted={inserted}")
    return inserted


def load_players(conn: psycopg.Connection, run_date: date) -> int:
    files = sorted((DATA_DIR / str(run_date) / "players").glob("*.json"))
    if len(files) == 0:
        raise SystemExit("No player files found. Run extract_players first.")
    missing = set(load_player_ids(run_date)) - {int(p.stem) for p in files}
    if missing:
        raise SystemExit(
            f"{len(missing)} players have no file (e.g. {sorted(missing)[:5]}). "
            "Run extract_players again."
        )
    rows = [(int(p.stem), run_date, p.read_text(encoding="utf-8")) for p in files]
    with conn.transaction():
        deleted = conn.execute(
            "DELETE FROM raw.player_summary WHERE run_date = %s", (run_date,)
        ).rowcount
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO raw.player_summary (player_id, run_date, payload) "
                "VALUES (%s, %s, %s::jsonb)",
                rows,
            )
            inserted = cur.rowcount
    print(f"deleted={deleted}, inserted={inserted}")
    return inserted


def main():
    args = parse_args()
    with (
        connect() as conn,
        track_run(conn, args.run_date, f"load_{args.source}") as run,
    ):
        if args.source == "players":
            run.rows_loaded = load_players(conn, args.run_date)
        else:
            run.rows_loaded = load_snapshot(conn, args.source, args.run_date)


if __name__ == "__main__":
    main()
