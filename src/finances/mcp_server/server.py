"""Build and run the MCP server on stdio."""

import logging

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from finances.mcp_server import tools

SERVER_NAME = "finances"
INSTRUCTIONS = (
    "Read-only tools over one household's finances. Money is in integer cents. Amounts are"
    " from the account holder's side: money leaving is negative, money coming in is positive,"
    " and a card balance owed is negative. Dates are ISO (YYYY-MM-DD). The tools change no"
    " data: they only store your proposals, which a person accepts or declines, and your notes."
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
LIST_UNCATEGORIZED_DESCRIPTION = (
    "Transactions without a category and not part of a transfer, latest first, at most limit "
    "(1 to 500, default 50), with the total count: id, posted day, account, description, the "
    "cleaned merchant, and the amount in integer cents (money out negative)."
)
LIST_CATEGORIES_DESCRIPTION = (
    "Every category with its group and whether it counts as a transfer, as income, or as "
    "sensitive, in name order ignoring case. No amounts."
)
LIST_RULES_DESCRIPTION = (
    "Every categorizing rule in the order rules are tried (highest priority first, then "
    "oldest): id, priority, match (contains, starts_with, equals), the pattern as stored, and "
    "the category it sets. No amounts."
)
LIST_TRANSFERS_DESCRIPTION = (
    "Transfers already paired, newest pair first, at most limit (1 to 500, default 100), with "
    "the total: each pair's id, status (auto when the app paired it, confirmed when a person "
    "did), and its outflow and inflow (id, posted day, account, description, amount in "
    "integer cents)."
)
LIST_TRANSFER_SUGGESTIONS_DESCRIPTION = (
    "Possible transfers waiting for a person to decide, where more than one pairing was "
    "possible: each an outflow and an inflow of the same amount on different accounts (id, "
    "posted day, account, description, amount in integer cents). A person confirms or rejects "
    "them; these tools never do."
)
DATA_COVERAGE_DESCRIPTION = (
    "How far the data can be trusted, as of today: for each open account its type, the first "
    "and last day with any data, the periods covered by imported statements (audited) and the "
    "gaps between them, the newest statement's end, whether SimpleFIN feeds it, its last pull, "
    "and the newest balance drift in integer cents with its day; and the data problems the app "
    "sees (kind, account, what is wrong, what to do). Use it before answering about a period "
    "that may be partial or stale."
)
FIND_MERCHANTS_DESCRIPTION = (
    "Merchant and category names that look like a phrase (a misspelling, part of a name, or a "
    "word such as coffee), best first, each with a score from 75 to 100, at most limit (1 to "
    "20, default 5). Use the names it returns with the other tools. No amounts."
)
WRITES_PROPOSALS = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
)
PROPOSE_CATEGORY_DESCRIPTION = (
    "Propose a category for a transaction without one (or set only by a rule), with a one-line "
    "reason a person will read. The category may be one still proposed with "
    "propose_new_category; this proposal then waits for that one. It changes nothing: a person "
    "accepts or declines it with fin review. Refused when a person already decided the "
    "transaction, declined this same proposal, or another proposal for it is open."
)
PROPOSE_TRANSFER_DESCRIPTION = (
    "Propose that money out (out_id) and money in (in_id) on another account, of the same "
    "amount, are one transfer, with a one-line reason a person will read. It changes nothing "
    "until a person accepts it. Refused when either is already in a pair, a person said they "
    "are not a transfer, declined this proposal, or another proposal for the two is open."
)
PROPOSE_NOT_TRANSFER_DESCRIPTION = (
    "Propose that money out (out_id) and money in (in_id) are not one transfer though they "
    "look like one, with a one-line reason. It changes nothing until a person accepts it; the "
    "same refusals as propose_transfer apply."
)
PROPOSE_RULE_DESCRIPTION = (
    "Propose a rule that puts every transaction whose merchant matches pattern in a category "
    "(match: contains, starts_with, or equals; priority -1000 to 1000, higher tried first), "
    "with an example transaction it matches and a one-line reason a person will read. The "
    "category may be one still proposed with propose_new_category; this proposal then waits "
    "for that one. It changes nothing until a person accepts it; then the rules run over every "
    "transaction. Refused when it does not match the example, a rule with this pattern and "
    "match exists, a person declined it, or another proposal for it is open. No amounts."
)
PROPOSE_MERCHANT_ALIAS_DESCRIPTION = (
    "Propose merging the merchant of an example transaction (its cleaned name) into another "
    "merchant (target), with a one-line reason a person will read, so reports count them as "
    "one and a rule on either name matches both. It changes nothing until a person accepts "
    "it; then the rules run over every transaction. Refused when the two are the same, "
    "either is already merged, other merchants are merged into the example's, a person "
    "declined it, or another proposal for that merchant is open. No amounts."
)
PROPOSE_GROUP_DESCRIPTION = (
    "Propose a new group of categories (a name; kind: spending, transfer, or income; sensitive "
    "or not), with an example transaction it is for and a one-line reason a person will read. "
    "Use it only when no existing group fits. It changes nothing until a person accepts it "
    "with fin review. Refused when a category or group has the name, a person declined it, or "
    "another proposal for that name is open. No amounts."
)
PROPOSE_NEW_CATEGORY_DESCRIPTION = (
    "Propose a new category (a name) in a group, tax-relevant or not, with an example "
    "transaction it is for and a one-line reason a person will read. The group may be one still "
    "proposed with propose_group; this proposal then waits for that one. It changes nothing "
    "until a person accepts it with fin review; then propose_category can put transactions in "
    "it. Refused when the group neither exists nor is proposed, a category or group has the "
    "name, a person declined it, or another proposal for that name is open. No amounts."
)
LIST_PROPOSALS_DESCRIPTION = (
    "Your proposals, newest first, of one status (open by default, accepted, or declined), at "
    "most limit (1 to 200, default 50): the transaction, the category, your reason, when it was "
    "made and decided, and whether it is out of date (a person decided the transaction since). "
    "No amounts."
)
LOG_ADVICE_DESCRIPTION = (
    "Keep a note of advice you gave or something to remember about this household (up to 1000 "
    "characters, with an optional subject of up to 100). It changes no data. No amounts are "
    "computed here; write them as you would in integer cents or plain text."
)
LIST_ADVICE_DESCRIPTION = (
    "Your notes, newest first, at most limit (1 to 200, default 20), with when each was kept."
)
_WRITES = (
    "propose_category",
    "propose_transfer",
    "propose_not_transfer",
    "propose_rule",
    "propose_merchant_alias",
    "propose_group",
    "propose_new_category",
    "log_advice",
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
    (tools.list_uncategorized, LIST_UNCATEGORIZED_DESCRIPTION),
    (tools.list_categories, LIST_CATEGORIES_DESCRIPTION),
    (tools.list_rules, LIST_RULES_DESCRIPTION),
    (tools.list_transfers, LIST_TRANSFERS_DESCRIPTION),
    (tools.list_transfer_suggestions, LIST_TRANSFER_SUGGESTIONS_DESCRIPTION),
    (tools.data_coverage, DATA_COVERAGE_DESCRIPTION),
    (tools.find_merchants, FIND_MERCHANTS_DESCRIPTION),
)


def build_server() -> MCPServer:
    server = MCPServer(name=SERVER_NAME, instructions=INSTRUCTIONS, log_level="WARNING")
    for fn, description in _TOOLS:
        server.add_tool(fn, description=description, annotations=READ_ONLY, structured_output=True)
    for fn, description in (
        (tools.propose_category, PROPOSE_CATEGORY_DESCRIPTION),
        (tools.propose_transfer, PROPOSE_TRANSFER_DESCRIPTION),
        (tools.propose_not_transfer, PROPOSE_NOT_TRANSFER_DESCRIPTION),
        (tools.propose_rule, PROPOSE_RULE_DESCRIPTION),
        (tools.propose_merchant_alias, PROPOSE_MERCHANT_ALIAS_DESCRIPTION),
        (tools.propose_group, PROPOSE_GROUP_DESCRIPTION),
        (tools.propose_new_category, PROPOSE_NEW_CATEGORY_DESCRIPTION),
        (tools.list_proposals, LIST_PROPOSALS_DESCRIPTION),
        (tools.log_advice, LOG_ADVICE_DESCRIPTION),
        (tools.list_advice, LIST_ADVICE_DESCRIPTION),
    ):
        annotations = WRITES_PROPOSALS if fn.__name__ in _WRITES else READ_ONLY
        server.add_tool(
            fn, description=description, annotations=annotations, structured_output=True
        )
    logging.getLogger("mcp").setLevel(logging.CRITICAL)
    return server


def serve() -> None:
    build_server().run("stdio")
