from mcp.server.mcpserver.exceptions import ToolError

from mcp_server.app import mcp
from mcp_server.constants import READ_ONLY
from mcp_server.rulebook import render_rules


@mcp.tool(annotations=READ_ONLY)
def fpl_rules() -> str:
    """This season's FPL rules: squad limits, the scoring table, transfers, selling prices and chips.

    Call this before you answer any question about the rules, and before you reason
    about points, hits, free transfers, selling prices or chips. The rules change
    every season (the number of chips, how many free transfers can be saved, points
    for defensive contributions), so what you remember is likely from an older
    season. The numbers come from FPL's own daily data for the season in the
    warehouse. The notes under them are hand-written each season: if they open with
    a warning, pass it on. Takes no arguments and returns Markdown.
    """
    return render_rules(ToolError)
