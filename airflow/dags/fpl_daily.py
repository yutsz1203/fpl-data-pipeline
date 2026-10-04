import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import ShortCircuitOperator
from airflow.sdk import DAG, CronTriggerTimetable, TriggerRule

FPL_HOME = "/opt/fpl"
RUN_DATE = "{{ dag_run.run_after | ds }}"


def fpl_script(task_id, command):
    return BashOperator(
        task_id=task_id,
        bash_command=f".venv/bin/python scripts/{command} --run-date {RUN_DATE}",
        cwd=FPL_HOME,
    )


def last_checked_deadline(events):
    return max(
        (e["deadline_time"] for e in events if e["finished"] and e["data_checked"]),
        default=None,
    )


def new_gameweek_finished(run_date):
    master = json.loads(Path(FPL_HOME, "data", run_date, "master.json").read_text())
    now = last_checked_deadline(master["events"])
    row = PostgresHook(postgres_conn_id="fpl_warehouse").get_first(
        """
        select payload -> 'events'
        from raw.master
        where run_date = (select max(run_date) from raw.player_summary where run_date < %s)
        """,
        parameters=(run_date,),
    )
    if row is None:
        print(f"No player load before {run_date}: first run")
        return True
    loaded = last_checked_deadline(row[0])
    print(
        f"Latest checked gameweek deadline: {now} now, {loaded} at the last player load"
    )
    return now is not None and (loaded is None or now > loaded)


def log_failure(context):
    ti = context["ti"]
    with open("/opt/airflow/logs/failures.log", "a") as f:
        f.write(
            f"{datetime.now(UTC):%Y-%m-%d %H:%M:%S} {ti.task_id} "
            f"run={ti.run_id} try={ti.try_number}: {context['exception']}\n"
        )


with DAG(
    dag_id="fpl_daily",
    schedule=CronTriggerTimetable("0 0 * * *", timezone="UTC"),
    start_date=datetime(2026, 9, 29, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=30),
        "on_failure_callback": log_failure,
    },
):
    extract_master = fpl_script("extract_master", "extract_master.py")
    extract_fixtures = fpl_script("extract_fixtures", "extract_fixtures.py")
    load_master = fpl_script("load_master", "load_raw.py --source master")
    load_fixtures = fpl_script("load_fixtures", "load_raw.py --source fixtures")

    gate = ShortCircuitOperator(
        task_id="gate",
        python_callable=new_gameweek_finished,
        op_kwargs={"run_date": RUN_DATE},
        ignore_downstream_trigger_rules=False,
    )

    extract_players = fpl_script("extract_players", "extract_players.py")
    load_players = fpl_script("load_players", "load_raw.py --source players")
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=".venv/bin/dbt run",
        cwd=f"{FPL_HOME}/dbt",
        trigger_rule=TriggerRule.NONE_FAILED,
    )
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=".venv/bin/dbt test",
        cwd=f"{FPL_HOME}/dbt",
        retries=0,
    )
    export_sheets = fpl_script("export_sheets", "export_sheets.py")
    extract_master >> load_master
    extract_fixtures >> load_fixtures
    (
        [load_master, load_fixtures]
        >> gate
        >> extract_players
        >> load_players
        >> dbt_run
        >> dbt_test
        >> export_sheets
    )
