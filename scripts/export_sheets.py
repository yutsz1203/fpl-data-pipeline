import argparse
import os
from datetime import date
from decimal import Decimal

import gspread
import psycopg
from db import connect
from run_log import track_run

SERVICE_ACCOUNT_FILE = "secrets/google-service-account.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SKIP_EXIT_CODE = 99
MAX_LAST_N = 5
TABS = {
    "season": """
        select *
        from marts.player_scouting
        where season = (select max(season) from marts.player_scouting)
        order by web_name, player_key
    """,
    "last_n": f"""
        select *
        from marts.player_scouting_last_n
        where season = (select max(season) from marts.player_scouting_last_n)
            and last_n <= {MAX_LAST_N}
        order by web_name, player_key, last_n
    """,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the scouting marts to Google Sheets."
    )
    parser.add_argument(
        "--run-date",
        required=True,
        type=date.fromisoformat,
        help="date in YYYY-MM-DD format.",
    )
    return parser.parse_args()


def to_cell(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return float(value)
    return value


def read_tab(conn: psycopg.Connection, query: str) -> list[list]:
    with conn.cursor() as cur:
        cur.execute(query)
        header = [column.name for column in cur.description]
        return [header, *([to_cell(value) for value in row] for row in cur)]


def open_sheet(sheet_id: str) -> gspread.Spreadsheet:
    client = gspread.service_account(filename=SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    try:
        return client.open_by_key(sheet_id)
    except (gspread.SpreadsheetNotFound, PermissionError) as e:
        raise SystemExit(f"Can't open sheet {sheet_id}: {e.__cause__}")


def write_tab(spreadsheet: gspread.Spreadsheet, tab: str, values: list[list]) -> int:
    worksheet = spreadsheet.worksheet(tab)
    response = worksheet.update(values, "A1")
    worksheet.resize(rows=len(values), cols=len(values[0]))
    print(f"{tab}: {len(values) - 1} rows -> {response['updatedRange']}")
    return len(values) - 1


def main():
    args = parse_args()
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        print("GOOGLE_SHEET_ID is empty: skipping the export.")
        raise SystemExit(SKIP_EXIT_CODE)
    with (
        connect() as conn,
        track_run(conn, args.run_date, "export_sheets") as run,
    ):
        tabs = {tab: read_tab(conn, query) for tab, query in TABS.items()}
        spreadsheet = open_sheet(sheet_id)
        run.rows_loaded = 0
        for tab, values in tabs.items():
            run.rows_loaded += write_tab(spreadsheet, tab, values)
    print(f"Open https://docs.google.com/spreadsheets/d/{sheet_id}")


if __name__ == "__main__":
    main()
