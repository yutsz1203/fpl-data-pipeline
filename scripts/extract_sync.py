import argparse
from datetime import date
from pathlib import Path

import requests
from config import DATA_DIR, USER_AGENT
from http_client import get_json


def parse_run_date(description: str) -> date:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--run-date",
        required=True,
        type=date.fromisoformat,
        help="date in YYYY-MM-DD format.",
    )
    args = parser.parse_args()
    return args.run_date


def extract_to_file(url: str, run_date: date, filename: str) -> Path:
    try:
        with requests.Session() as session:
            session.headers.update({"User-Agent": USER_AGENT})
            resp = get_json(session, url)
    except (requests.RequestException, ValueError) as e:
        raise SystemExit(f"Error: {e}")

    out_dir = DATA_DIR / str(run_date)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    out_path.write_bytes(resp.content)
    print(f"Content written to {out_path}")
    return out_path
