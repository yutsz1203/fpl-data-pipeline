from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date

import psycopg
from psycopg.pq import TransactionStatus


@dataclass
class RunStats:
    rows_loaded: int | None = None
    failed_ids: list[int] = field(default_factory=list)


@contextmanager
def track_run(conn: psycopg.Connection, run_date: date, step: str):
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise RuntimeError("track_run must start outside a transaction")
    run_id = conn.execute(
        "INSERT INTO raw.pipeline_runs (run_date, step) VALUES (%s, %s) RETURNING run_id",
        (run_date, step),
    ).fetchone()[0]
    stats = RunStats()
    try:
        yield stats
    except BaseException as e:
        conn.execute(
            """
            UPDATE raw.pipeline_runs
            SET status = 'failed',
                finished_at = now(),
                rows_loaded = %s,
                failed_ids = %s,
                error = %s
            WHERE run_id = %s
            """,
            (
                stats.rows_loaded,
                stats.failed_ids,
                f"{type(e).__name__}: {e}",
                run_id,
            ),
        )
        raise
    else:
        conn.execute(
            """
            UPDATE raw.pipeline_runs
            SET status = 'success',
                finished_at = now(),
                rows_loaded = %s,
                failed_ids = %s
            WHERE run_id = %s
            """,
            (
                stats.rows_loaded,
                stats.failed_ids,
                run_id,
            ),
        )
