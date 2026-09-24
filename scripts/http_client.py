import sys
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import requests
from config import (
    BACKOFF_BASE,
    MAX_ATTEMPTS,
    MAX_DELAY,
    RETRY_STATUSES,
    TIMEOUT,
)


def _retry_after_seconds(value: str | None) -> float | None:
    """Return the Retry-After wait in seconds, or None if not usable."""
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def _log(attempt: int, reason: str, url: str, delay: float) -> None:
    print(
        f"attempt {attempt+1}/{MAX_ATTEMPTS} {reason} {url}, sleeping {delay}s",
        file=sys.stderr,
    )


def get_json(session: requests.Session, url: str) -> requests.Response:
    for attempt in range(MAX_ATTEMPTS):
        backoff = min(BACKOFF_BASE * 2**attempt, MAX_DELAY)
        last_attempt = attempt == MAX_ATTEMPTS - 1

        try:
            resp = session.get(url, timeout=TIMEOUT)
        except (requests.ConnectionError, requests.Timeout) as e:
            if last_attempt:
                raise
            _log(attempt, repr(e), url, backoff)
            time.sleep(backoff)
            continue
        if resp.status_code not in RETRY_STATUSES:
            resp.raise_for_status()
        else:
            if last_attempt:
                resp.raise_for_status()
            delay = backoff
            if resp.status_code == 429:
                retry_after = _retry_after_seconds(resp.headers.get("Retry-After"))
                if retry_after is not None:
                    delay = min(retry_after, MAX_DELAY)
            _log(attempt, f"Status_code: {resp.status_code}", url, delay)
            time.sleep(delay)
            continue

        try:
            resp.json()
        except requests.exceptions.JSONDecodeError as e:
            if last_attempt:
                raise ValueError(f"Body is not valid JSON: {resp.text[:200]}") from e
            _log(attempt, repr(e), url, backoff)
            time.sleep(backoff)
            continue

        return resp

    raise AssertionError("unreachable")
