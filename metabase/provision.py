import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

METABASE_URL = os.getenv("METABASE_URL", "http://localhost:3000")
DATABASE_NAME = "FPL warehouse"
MINUTES_PER_GAME = 60
CARD_WIDTH = 12
CARD_HEIGHT = 15
CHART_COLOR = "#c2562f"

LAST_N = "{{last_n}}"
LAST_N_TAG = {
    "id": "last-n",
    "name": "last_n",
    "display-name": "Last N games",
    "type": "number",
    "default": "5",
    "required": True,
}
LAST_N_FILTER = {
    "id": "last_n",
    "name": "Last N games",
    "slug": "last_n",
    "type": "number/=",
    "sectionId": "number",
    "default": [5],
}
SEASON = {
    "table": "marts.player_scouting",
    "window": [],
    "n": "finished_gameweeks",
    "suffix": "",
    "about": f"Season to date. Tables: top 20 with {MINUTES_PER_GAME}+ minutes "
    "per finished gameweek.",
    "parameters": [],
}
LAST_N_GAMES = {
    "table": "marts.player_scouting_last_n",
    "window": [f"last_n = least({LAST_N}, games_played)"],
    "n": "last_n",
    "suffix": " (last N games)",
    "about": "Each player's last N games (the filter, default 5), including games "
    f"they did not play. Tables: top 20 with {MINUTES_PER_GAME}+ minutes per game.",
    "parameters": [LAST_N_FILTER],
}
DASHBOARDS = {"FPL scouting": SEASON, "FPL form": LAST_N_GAMES}

POSITIONS = {
    "ALL": "All positions",
    "GKP": "Goalkeepers",
    "DEF": "Defenders",
    "MID": "Midfielders",
    "FWD": "Forwards",
}
LABELS = {
    "web_name": "Player",
    "team": "Team",
    "position": "Position",
    "price": "Price",
    "minutes": "Minutes",
    "total_points": "Points",
    "points_per_million": "Points per £m",
    "xgi": "xGI",
    "xgi_per_90": "xGI/90",
    "xgc_per_90": "xGC/90",
    "clean_sheets": "Clean sheets",
    "saves": "Saves",
    "defcon": "DefCon",
    "defcon_per_90": "DefCon/90",
    "defcon_hits": "Hits",
    "defcon_hit_rate": "Hit rate",
    "gi - xgi": "G+A minus xGI",
    "xgc - goals_conceded": "xGC minus goals conceded",
}
FORMATS = {
    "Price": {"prefix": "£", "suffix": "m", "decimals": 1},
    "Points per £m": {"decimals": 1},
    "xGI": {"decimals": 2},
    "xGI/90": {"decimals": 2},
    "xGC/90": {"decimals": 2},
    "DefCon/90": {"decimals": 1},
    "Hit rate": {"number_style": "percent", "decimals": 0},
}
XGI = "xgi_per_90 desc, xgi desc"
XGC = "xgc_per_90"
DEFCON = "defcon_per_90 desc, defcon desc"
PPM = "points_per_million desc"
XGI_COLUMNS = ["xgi_per_90", "xgi", "total_points"]
XGC_COLUMNS = ["xgc_per_90", "clean_sheets", "saves", "total_points"]
DEFCON_COLUMNS = ["defcon_per_90", "defcon", "defcon_hits", "defcon_hit_rate"]
PPM_COLUMNS = ["total_points", "points_per_million"]
DESCRIPTION = (
    "Each chart shows the players of the table to its left. "
    "Built by metabase/provision.py, which overwrites changes made in the UI."
)
PIPELINE_HEALTH = {
    "name": "Pipeline: latest run of each step",
    "description": "From raw.pipeline_runs. Master and fixtures run every day; "
    "the players steps run only after a gameweek finishes.",
    "display": "table",
    "sql": """select distinct on (step)
    step as "Step",
    run_date::text as "Run date",
    to_char(started_at at time zone 'UTC', 'YYYY-MM-DD HH24:MI') as "Started (UTC)",
    status as "Status",
    rows_loaded as "Rows loaded",
    coalesce(nullif(array_to_string(failed_ids, ', '), ''), 'none') as "Failed IDs"
from raw.pipeline_runs
order by step, started_at desc""",
    "visualization_settings": {
        "table.column_formatting": [
            {
                "columns": ["Status"],
                "type": "single",
                "operator": "=",
                "value": "failed",
                "color": "#ED6E6E",
                "highlight_row": True,
            }
        ]
    },
}


def top_sql(
    source: dict, position: str, order_by: str, columns: list[str], limit: int = 20
) -> str:
    select = ",\n    ".join(f'{column} as "{LABELS[column]}"' for column in columns)
    conditions = [f"season = (select max(season) from {source['table']})"]
    if position != "ALL":
        conditions.append(f"position = '{position}'")
    conditions += source["window"]
    conditions.append(f"minutes >= {MINUTES_PER_GAME} * {source['n']}")
    where = "\n    and ".join(conditions)
    return f"""select
    {select}
from {source["table"]}
where {where}
order by {order_by}, web_name
limit {limit}"""


def table(
    source: dict, position: str, title: str, order_by: str, columns: list[str]
) -> dict:
    player = ["web_name", "team"]
    if position == "ALL":
        player.append("position")
    return {
        "name": f"{POSITIONS[position]}: {title}{source['suffix']}",
        "display": "table",
        "sql": top_sql(
            source, position, order_by, [*player, "price", "minutes", *columns]
        ),
        "visualization_settings": {
            "column_settings": {
                json.dumps(["name", label]): fmt for label, fmt in FORMATS.items()
            }
        },
    }


def bar_chart(name: str, sql: str, metric: str, goal: int | None = None) -> dict:
    settings = {
        "graph.dimensions": ["Player"],
        "graph.metrics": [metric],
        "series_settings": {metric: {"color": CHART_COLOR}},
    }
    if goal is not None:
        settings |= {
            "graph.show_goal": True,
            "graph.goal_value": goal,
            "graph.goal_label": f"2 points at {goal}",
        }
    return {
        "name": name,
        "display": "row",
        "sql": sql,
        "visualization_settings": settings,
    }


def gap_chart(source: dict, position: str, order_by: str, gap: str) -> dict:
    label = LABELS[gap]
    inner = top_sql(source, position, order_by, ["web_name", gap])
    return bar_chart(
        f"{POSITIONS[position]}: {label}{source['suffix']}",
        f'select * from (\n{inner}\n) as top_players\norder by "{label}" desc',
        label,
    )


def defcon_chart(source: dict, position: str, threshold: int) -> dict:
    return bar_chart(
        f"{POSITIONS[position]}: DefCon/90 vs the 2-point line{source['suffix']}",
        top_sql(source, position, DEFCON, ["web_name", "defcon_per_90"], limit=10),
        "DefCon/90",
        goal=threshold,
    )


def dashboard_tabs(source: dict) -> dict:
    return {
        "Overview": [
            [
                table(source, "ALL", "points per £m", PPM, PPM_COLUMNS),
                PIPELINE_HEALTH,
            ]
        ],
        "Goalkeepers": [
            [
                table(source, "GKP", "xGC per 90", XGC, XGC_COLUMNS),
                gap_chart(source, "GKP", XGC, "xgc - goals_conceded"),
            ],
            [table(source, "GKP", "points per £m", PPM, PPM_COLUMNS)],
        ],
        "Defenders": [
            [
                table(source, "DEF", "xGI per 90", XGI, XGI_COLUMNS),
                gap_chart(source, "DEF", XGI, "gi - xgi"),
            ],
            [
                table(source, "DEF", "DefCon per 90", DEFCON, DEFCON_COLUMNS),
                defcon_chart(source, "DEF", 10),
            ],
            [table(source, "DEF", "points per £m", PPM, PPM_COLUMNS)],
        ],
        "Midfielders": [
            [
                table(source, "MID", "xGI per 90", XGI, XGI_COLUMNS),
                gap_chart(source, "MID", XGI, "gi - xgi"),
            ],
            [
                table(source, "MID", "DefCon per 90", DEFCON, DEFCON_COLUMNS),
                defcon_chart(source, "MID", 12),
            ],
            [table(source, "MID", "points per £m", PPM, PPM_COLUMNS)],
        ],
        "Forwards": [
            [
                table(source, "FWD", "xGI per 90", XGI, XGI_COLUMNS),
                gap_chart(source, "FWD", XGI, "gi - xgi"),
            ],
            [table(source, "FWD", "points per £m", PPM, PPM_COLUMNS)],
        ],
    }


def call(session: requests.Session, method: str, path: str, **kwargs):
    response = session.request(method, f"{METABASE_URL}/api/{path}", **kwargs)
    if not response.ok:
        body = response.json()
        if isinstance(body, dict):
            body = body.get("message") or body.get("errors")
        raise SystemExit(
            f"{method} /api/{path} failed ({response.status_code}): {body}"
        )
    return response.json()


def set_up_admin(session: requests.Session) -> None:
    properties = call(session, "GET", "session/properties")
    if properties["has-user-setup"]:
        print("Admin already set up")
        return
    call(
        session,
        "POST",
        "setup",
        json={
            "token": properties["setup-token"],
            "user": {
                "email": os.environ["METABASE_ADMIN_EMAIL"],
                "password": os.environ["METABASE_ADMIN_PASSWORD"],
                "first_name": "FPL",
                "last_name": "Admin",
            },
            "prefs": {"site_name": "FPL"},
        },
    )
    print("Admin created")


def log_in(session: requests.Session) -> None:
    response = call(
        session,
        "POST",
        "session",
        json={
            "username": os.environ["METABASE_ADMIN_EMAIL"],
            "password": os.environ["METABASE_ADMIN_PASSWORD"],
        },
    )
    session.headers["X-Metabase-Session"] = response["id"]


def connect_warehouse(session: requests.Session) -> int:
    details = {
        "host": "warehouse",
        "port": 5432,
        "dbname": os.environ["POSTGRES_DB"],
        "user": "metabase_reader",
        "password": os.environ["METABASE_READER_PASSWORD"],
    }
    databases = call(session, "GET", "database")["data"]
    existing = next((db for db in databases if db["name"] == DATABASE_NAME), None)
    if existing is None:
        database = call(
            session,
            "POST",
            "database",
            json={"engine": "postgres", "name": DATABASE_NAME, "details": details},
        )
        print(f"Warehouse added as database {database['id']}")
    else:
        database = call(
            session, "PUT", f"database/{existing['id']}", json={"details": details}
        )
        print(f"Warehouse connection updated (database {database['id']})")
    return database["id"]


def save_card(
    session: requests.Session, database_id: int, card: dict, existing: dict[str, int]
) -> int:
    native = {"query": card["sql"]}
    if LAST_N in card["sql"]:
        native["template-tags"] = {"last_n": LAST_N_TAG}
    query = {"database": database_id, "type": "native", "native": native}
    result = session.post(f"{METABASE_URL}/api/dataset", json=query).json()
    if result["status"] != "completed":
        raise SystemExit(f"{card['name']}: {result['error']}")
    body = {
        "name": card["name"],
        "description": card.get("description"),
        "display": card["display"],
        "visualization_settings": card["visualization_settings"],
        "dataset_query": query,
    }
    if card["name"] in existing:
        card_id = call(session, "PUT", f"card/{existing[card['name']]}", json=body)[
            "id"
        ]
        print(f"  updated card {card_id}: {card['name']} ({result['row_count']} rows)")
    else:
        card_id = call(session, "POST", "card", json=body)["id"]
        print(f"  created card {card_id}: {card['name']} ({result['row_count']} rows)")
    return card_id


def build_dashboard(
    session: requests.Session, database_id: int, name: str, source: dict
) -> int:
    existing = {
        card["name"]: card["id"]
        for card in call(session, "GET", "card", params={"f": "all"})
    }
    dashboards = {d["name"]: d["id"] for d in call(session, "GET", "dashboard")}
    dashboard_id = dashboards.get(name)
    if dashboard_id is None:
        dashboard_id = call(session, "POST", "dashboard", json={"name": name})["id"]
    tabs, dashcards = [], []
    for tab_number, (tab_name, rows) in enumerate(
        dashboard_tabs(source).items(), start=1
    ):
        tabs.append({"id": -tab_number, "name": tab_name})
        for row_number, row in enumerate(rows):
            for column_number, card in enumerate(row):
                card_id = save_card(session, database_id, card, existing)
                mappings = []
                if LAST_N in card["sql"]:
                    mappings.append(
                        {
                            "parameter_id": LAST_N_FILTER["id"],
                            "card_id": card_id,
                            "target": ["variable", ["template-tag", "last_n"]],
                        }
                    )
                dashcards.append(
                    {
                        "id": -(len(dashcards) + 1),
                        "card_id": card_id,
                        "dashboard_tab_id": -tab_number,
                        "row": row_number * CARD_HEIGHT,
                        "col": column_number * CARD_WIDTH,
                        "size_x": CARD_WIDTH,
                        "size_y": CARD_HEIGHT,
                        "parameter_mappings": mappings,
                    }
                )
    call(
        session,
        "PUT",
        f"dashboard/{dashboard_id}",
        json={
            "width": "full",
            "description": f"{source['about']} {DESCRIPTION}",
            "parameters": source["parameters"],
            "tabs": tabs,
            "dashcards": dashcards,
        },
    )
    print(f"Dashboard {dashboard_id}: {len(tabs)} tabs, {len(dashcards)} cards")
    return dashboard_id


def main():
    with requests.Session() as session:
        set_up_admin(session)
        log_in(session)
        database_id = connect_warehouse(session)
        for name, source in DASHBOARDS.items():
            dashboard_id = build_dashboard(session, database_id, name, source)
            print(f"Open {METABASE_URL}/dashboard/{dashboard_id}")


if __name__ == "__main__":
    main()
