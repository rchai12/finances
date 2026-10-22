"""Build and run the MCP server on stdio."""

import logging

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from finances.mcp_server import tools

SERVER_NAME = "finances"
INSTRUCTIONS = (
    "Read-only tools over one household's finances. Money is in integer cents. Amounts are"
    " from the account holder's side: money leaving is negative, money coming in is positive,"
    " and a card balance owed is negative. Dates are ISO (YYYY-MM-DD). Nothing here changes data."
)
READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
LIST_ACCOUNTS_DESCRIPTION = (
    "List the household's accounts: name, institution, type, currency, last 4 digits, "
    "whether open, and owner (a person's name, or joint). Closed accounts only when "
    "include_inactive is true. No amounts."
)
GET_BALANCES_DESCRIPTION = (
    "Each open account's newest balance in integer cents (a card balance owed is negative), "
    "its date and source (statement or aggregator), totals for cash, cards, and other, "
    "the net worth, and the open accounts with no balance yet."
)
GET_NET_WORTH_DESCRIPTION = (
    "Net worth in integer cents at the end of each of the last N months (1 to 60, default 12), "
    "this month ending today: each open account's newest balance on or before that day, "
    "with how many accounts were counted. Months before any balance are left out."
)
_TOOLS = (
    (tools.list_accounts, LIST_ACCOUNTS_DESCRIPTION),
    (tools.get_balances, GET_BALANCES_DESCRIPTION),
    (tools.get_net_worth, GET_NET_WORTH_DESCRIPTION),
)


def build_server() -> MCPServer:
    server = MCPServer(name=SERVER_NAME, instructions=INSTRUCTIONS, log_level="WARNING")
    for fn, description in _TOOLS:
        server.add_tool(fn, description=description, annotations=READ_ONLY, structured_output=True)
    logging.getLogger("mcp").setLevel(logging.CRITICAL)
    return server


def serve() -> None:
    build_server().run("stdio")
