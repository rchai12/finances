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
LIST_TRANSACTIONS_DESCRIPTION = (
    "Transactions, latest first, filtered by any of: text in the description, account, person "
    "(a name, joint, or unassigned), category, group, merchant, bank, card (last 4 digits), "
    "kind (spending, income, transfer, unsorted_in, pending, refund), and a start and end day. "
    "Amounts in integer cents, money out negative. At most limit (1 to 200, default 50) per "
    "call; pass next_offset as offset for the next page."
)
GET_SPENDING_DESCRIPTION = (
    "Spending from start to end (ISO days, both or neither; default this month) grouped by "
    "category, group, merchant, person, account, bank, or card. Each line: spent_cents "
    "(purchases), refunds_cents (money back), net_cents (spent minus refunds, below zero when "
    "refunds win), and count; plus a summary with income, transfers left out, and money in "
    "without a category. Integer cents."
)
MONTH_OVER_MONTH_DESCRIPTION = (
    "Net spending (purchases minus refunds) and income in integer cents for each of the last N "
    "months (1 to 24, default 6) ending with the given month (YYYY-MM, default this month), "
    "oldest first, with the accounts whose data does not cover that whole month."
)
GET_INSIGHTS_DESCRIPTION = (
    "Findings for a month (YYYY-MM, default this month): each with its type, severity (high, "
    "medium, low), subject (a category or merchant, or null), what acting on it could save a "
    "month in integer cents, and a sentence; and each merchant's visits, spending, average, "
    "baseline from earlier months, change, and weekend visits, in integer cents."
)
GET_RECURRING_DESCRIPTION = (
    "Recurring charges, or recurring income when income is true, found up to today: merchant, "
    "cadence (week, two_weeks, month, quarter, year), the last amount and its monthly cost in "
    "integer cents (charges negative, income positive), how many were seen, the first, last, "
    "and next day, and whether it is still active. Stopped series only when include_inactive "
    "is true."
)
GET_UPCOMING_DESCRIPTION = (
    "Bills and income expected in the next N days (1 to 90, default 30, today the first) from "
    "the active recurring series: day, bill or income, merchant, cadence, and amount in integer "
    "cents (bills negative), with the total of each."
)
GET_FORECAST_DESCRIPTION = (
    "Each account's balance walked forward through its own expected bills and income for the "
    "next N days (1 to 90, default 30): the starting balance and its date, expected in and out, "
    "the end, and the lowest point with its day, in integer cents, with each step; or one "
    "account when account is given. Accounts with no balance are listed by name."
)
GET_BUDGETS_DESCRIPTION = (
    "Each budget for a month (YYYY-MM, default this month): category or group, monthly target, "
    "net spending so far (purchases minus refunds), what is left, the share used, and the share "
    "of the month gone, in integer cents and whole percents."
)
_TOOLS = (
    (tools.list_accounts, LIST_ACCOUNTS_DESCRIPTION),
    (tools.get_balances, GET_BALANCES_DESCRIPTION),
    (tools.get_net_worth, GET_NET_WORTH_DESCRIPTION),
    (tools.list_transactions, LIST_TRANSACTIONS_DESCRIPTION),
    (tools.get_spending, GET_SPENDING_DESCRIPTION),
    (tools.month_over_month, MONTH_OVER_MONTH_DESCRIPTION),
    (tools.get_insights, GET_INSIGHTS_DESCRIPTION),
    (tools.get_recurring, GET_RECURRING_DESCRIPTION),
    (tools.get_upcoming, GET_UPCOMING_DESCRIPTION),
    (tools.get_forecast, GET_FORECAST_DESCRIPTION),
    (tools.get_budgets, GET_BUDGETS_DESCRIPTION),
)


def build_server() -> MCPServer:
    server = MCPServer(name=SERVER_NAME, instructions=INSTRUCTIONS, log_level="WARNING")
    for fn, description in _TOOLS:
        server.add_tool(fn, description=description, annotations=READ_ONLY, structured_output=True)
    logging.getLogger("mcp").setLevel(logging.CRITICAL)
    return server


def serve() -> None:
    build_server().run("stdio")
