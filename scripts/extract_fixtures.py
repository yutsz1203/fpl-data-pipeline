from config import FIXTURES_URL
from extract_sync import extract_to_file, parse_run_date


def main():
    run_date = parse_run_date("Extract from Fixtures API.")
    extract_to_file(FIXTURES_URL, run_date, "fixtures.json")


if __name__ == "__main__":
    main()
