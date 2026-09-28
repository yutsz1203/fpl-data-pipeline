import asyncio
import json
import shutil
import sys
import time
from datetime import date
from pathlib import Path

import aiohttp
from config import CONCURRENCY, DATA_DIR, PLAYER_URL, TIMEOUT, USER_AGENT
from db import connect
from extract_sync import parse_run_date
from http_client_async import get_json_async
from run_log import track_run

PROGRESS_EVERY = 50


def load_player_ids(run_date: date) -> list[int]:
    try:
        with open(DATA_DIR / str(run_date) / "master.json", "r") as f:
            master = json.load(f)
    except FileNotFoundError:
        raise SystemExit("master.json not found, run extract_master first")

    ids = [e["id"] for e in master["elements"]]
    return ids


def reset_players_dir(run_date: date) -> Path:
    (DATA_DIR / str(run_date) / "failed_players.txt").unlink(missing_ok=True)
    players_dir = DATA_DIR / str(run_date) / "players"
    shutil.rmtree(players_dir, ignore_errors=True)
    players_dir.mkdir()
    return players_dir


async def fetch_and_save(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    out_dir: Path,
    player_id: int,
) -> tuple[int, str] | None:
    url = PLAYER_URL.format(id=player_id)
    try:
        body = await get_json_async(session, semaphore, url)
    except (aiohttp.ClientError, TimeoutError, ValueError) as e:
        return player_id, f"{type(e).__name__}: {e}"
    (out_dir / f"{player_id}.json").write_bytes(body)
    return None


async def extract_players(ids: list[int], out_dir: Path) -> list[tuple[int, str]]:
    async with aiohttp.ClientSession(
        headers={"User-Agent": USER_AGENT}, timeout=aiohttp.ClientTimeout(total=TIMEOUT)
    ) as session:
        semaphore = asyncio.Semaphore(CONCURRENCY)
        tasks = [fetch_and_save(session, semaphore, out_dir, pid) for pid in ids]
        failures = []
        for done, next_result in enumerate(asyncio.as_completed(tasks), start=1):
            result = await next_result
            if result is not None:
                failures.append(result)
            if done % PROGRESS_EVERY == 0 or done == len(tasks):
                print(
                    f"{done}/{len(tasks)} players done, {len(failures)} failed",
                    file=sys.stderr,
                )
    return failures


def write_failed_log(run_date: date, failures) -> Path:
    path = DATA_DIR / str(run_date) / "failed_players.txt"
    path.write_text("".join(f"{pid}\t{reason}\n" for pid, reason in sorted(failures)))
    return path


def main():
    run_date = parse_run_date("Extract from Players API.")
    with connect() as conn, track_run(conn, run_date, "extract_players") as run:
        ids = load_player_ids(run_date)
        players_dir = reset_players_dir(run_date)
        t1 = time.perf_counter()
        failures = asyncio.run(extract_players(ids, players_dir))
        t2 = time.perf_counter()
        log_path = write_failed_log(run_date, failures)
        run.rows_loaded = len(ids) - len(failures)
        run.failed_ids = sorted(pid for pid, _ in failures)
        print(
            f"Players API fetching summary: saved {len(ids)-len(failures)}/{len(ids)} players, "
            f"{len(failures)} failed, {t2-t1:.1f} s."
        )
        if failures:
            raise SystemExit(f"{len(failures)} players failed, see {log_path}.")


if __name__ == "__main__":
    main()
