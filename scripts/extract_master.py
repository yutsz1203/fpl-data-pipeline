from config import MASTER_URL
from db import connect
from extract_sync import extract_to_file, parse_run_date
from run_log import track_run


def main():
    run_date = parse_run_date("Extract from Master API.")
    with connect() as conn, track_run(conn, run_date, "extract_master") as run:
        extract_to_file(MASTER_URL, run_date, "master.json")
        run.rows_loaded = 1


if __name__ == "__main__":
    main()
