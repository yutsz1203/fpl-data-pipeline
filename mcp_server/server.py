from mcp_server import resources, tools
from mcp_server.app import mcp
from mcp_server.prompts import plan_gameweek, scout_position, transfer_check

mcp.prompt(title="Scout a position")(scout_position)
mcp.prompt(title="Check a transfer")(transfer_check)
mcp.prompt(title="Plan the next gameweek")(plan_gameweek)

__all__ = ["mcp", "resources", "tools"]

if __name__ == "__main__":
    mcp.run()
