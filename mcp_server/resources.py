from collections import defaultdict

from mcp.server.mcpserver.exceptions import ResourceError

from mcp_server.app import mcp
from mcp_server.classes import Freshness, StepFreshness
from mcp_server.constants import GLOSSARY, SCHEMA_TABLES
from mcp_server.db import open_cursor
from mcp_server.queries import FRESHNESS_SQL, SCHEMA_SQL, SEASONS_SQL
from mcp_server.rulebook import render_rules


@mcp.resource("fpl://rules", mime_type="text/markdown", title="FPL rules")
def rules() -> str:
    """This season's FPL rules: squad limits, scoring, transfers, chips and their gameweek
    windows. The numbers come from FPL's own daily data, so they follow rule changes. The
    fpl_rules tool returns the same text.
    """
    return render_rules(ResourceError)


@mcp.resource("fpl://schema", mime_type="text/markdown", title="Warehouse schema")
def schema() -> str:
    """The warehouse tables behind the tools, their columns and types, and a glossary of the stats."""
    with open_cursor() as cur:
        rows = cur.execute(SCHEMA_SQL, {"tables": list(SCHEMA_TABLES)}).fetchall()
    columns = defaultdict(list)
    for row in rows:
        columns[row["table_name"]].append(row)
    lines = [
        "# FPL warehouse",
        "",
        "The tools read these tables in the `marts` schema. There is no SQL access: ask through the tools.",
    ]
    for table, about in SCHEMA_TABLES.items():
        if not columns[table]:
            raise ResourceError(f"Table marts.{table} is missing or not readable.")
        lines += ["", f"## {table}", "", about, "", "| column | type |", "|---|---|"]
        lines += [f"| {c['column_name']} | {c['data_type']} |" for c in columns[table]]
    lines += ["", "## Glossary", ""]
    lines += [f"- **{term}**: {meaning}" for term, meaning in GLOSSARY.items()]
    return "\n".join(lines) + "\n"


@mcp.resource("fpl://freshness", mime_type="application/json", title="Data freshness")
def freshness() -> Freshness:
    """How fresh the data is: the latest finished and data-checked gameweek, and the
    last successful run of each pipeline step. The player steps run only after a new
    gameweek finishes, so their dates can be days older than the other steps.
    """
    with open_cursor() as cur:
        seasons = cur.execute(SEASONS_SQL).fetchall()
        steps = cur.execute(FRESHNESS_SQL).fetchall()
    latest = seasons[0] if seasons else {"season": None, "data_to_gameweek": None}
    return Freshness(
        season=latest["season"],
        data_to_gameweek=latest["data_to_gameweek"],
        steps=[StepFreshness(**row) for row in steps],
    )
