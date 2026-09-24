import asyncio
import json
import random

import aiohttp
from config import (
    BACKOFF_BASE,
    MAX_ATTEMPTS,
    MAX_DELAY,
    RETRY_STATUSES,
)
from http_client import _log, _retry_after_seconds

RETRYABLE_ERRORS = (
    aiohttp.ClientConnectionError,
    aiohttp.ClientPayloadError,
    TimeoutError,
)


def _jitter(delay: float) -> float:
    return round(delay * random.uniform(0.5, 1.5), 2)


async def get_json_async(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    url: str,
) -> bytes:
    for attempt in range(MAX_ATTEMPTS):
        backoff = min(BACKOFF_BASE * 2**attempt, MAX_DELAY)
        last_attempt = attempt == MAX_ATTEMPTS - 1

        try:
            async with semaphore, session.get(url) as resp:
                body = await resp.read()
        except RETRYABLE_ERRORS as e:
            if last_attempt:
                raise
            delay = _jitter(backoff)
            _log(attempt, repr(e), url, delay)
            await asyncio.sleep(delay)
            continue

        if resp.status not in RETRY_STATUSES:
            resp.raise_for_status()
        else:
            if last_attempt:
                resp.raise_for_status()
            delay = _jitter(backoff)
            if resp.status == 429:
                retry_after = _retry_after_seconds(resp.headers.get("Retry-After"))
                if retry_after is not None:
                    delay = round(min(retry_after, MAX_DELAY) + random.uniform(0, 1), 2)
            _log(attempt, f"Status_code: {resp.status}", url, delay)
            await asyncio.sleep(delay)
            continue

        try:
            json.loads(body)
        except json.JSONDecodeError as e:
            if last_attempt:
                raise ValueError(f"Body is not valid JSON: {body[:200]!r}") from e
            delay = _jitter(backoff)
            _log(attempt, repr(e), url, delay)
            await asyncio.sleep(delay)
            continue

        return body

    raise AssertionError("unreachable")
