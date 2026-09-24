from config import MASTER_URL
from extract_sync import extract_to_file, parse_run_date


def main():
    run_date = parse_run_date("Extract from Master API.")
    extract_to_file(MASTER_URL, run_date, "master.json")


if __name__ == "__main__":
    main()
