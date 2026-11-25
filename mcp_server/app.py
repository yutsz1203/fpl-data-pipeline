from pathlib import Path

from dotenv import load_dotenv
from mcp.server import MCPServer

from mcp_server.constants import INSTRUCTIONS

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

mcp = MCPServer("fpl-warehouse", instructions=INSTRUCTIONS)
