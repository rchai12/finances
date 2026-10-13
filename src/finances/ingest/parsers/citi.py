"""The parser for Citi credit card statements."""

import re
from datetime import date

from finances.domain.models import AccountType
from finances.ingest.parsers.helpers import (
    collapse_ws,
    find_labeled_amount,
    parse_amount,
    parse_month_day,
)
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

_DATE = r"[0-9]{2}/[0-9]{2}"
_AMOUNT = r"-?\$(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\.[0-9]{2}"

_ACCOUNT = re.compile(r"Account number ending in: ([0-9]{4})")
_PERIOD = re.compile(
    r"Billing Period: ([0-9]{2})/([0-9]{2})/([0-9]{2})-([0-9]{2})/([0-9]{2})/([0-9]{2})"
)
_CARDHOLDER = re.compile(r"(.+?)\s+Card ending in ([0-9]{4})")
_ROW = re.compile(rf"(?:({_DATE})\s+)?({_DATE})\s+(.+?)\s+({_AMOUNT})")

_SECTIONS = {
    "Payments, Credits and Adjustments": Section.PAYMENTS_CREDITS,
    "Fees Charged": Section.FEES,
    "Interest Charged": Section.INTEREST,
}
_TOTALS = (
    (Section.PURCHASES, "Purchases"),
    (Section.FEES, "Fees"),
    (Section.INTEREST, "Interest"),
)

_NO_ACCOUNT = "citi: account number not found"
_NO_PERIOD = "citi: billing period not found"
_NO_PREVIOUS = "citi: previous balance not found"
_NO_NEW = "citi: new balance not found"


class CitiCardParser:
    name = "citi_card"

    def detect(self, first_page: str) -> bool:
        return "citicards.com" in first_page and "Billing Period:" in first_page

    def parse(self, pages: list[str]) -> ParsedStatement:
        lines = [line.strip() for page in pages for line in page.splitlines()]
        text = "\n".join(lines)
        account = _ACCOUNT.search(text)
        if account is None:
            raise StatementError(_NO_ACCOUNT)
        start, end = _period(text)
        previous = find_labeled_amount(lines, "Previous balance")
        if previous is None:
            raise StatementError(_NO_PREVIOUS)
        new = find_labeled_amount(lines, "New balance")
        if new is None:
            raise StatementError(_NO_NEW)
        return ParsedStatement(
            parser_name=self.name,
            institution="Citi",
            account_type=AccountType.CREDIT_CARD,
            account_last4=account.group(1),
            period_start=start,
            period_end=end,
            opening_balance_cents=-previous,
            closing_balance_cents=-new,
            lines=_rows(lines, start, end),
            declared_section_totals=_declared_totals(lines),
        )


def _period(text: str) -> tuple[date, date]:
    match = _PERIOD.search(text)
    if match is None:
        raise StatementError(_NO_PERIOD)
    numbers = [int(part) for part in match.groups()]
    try:
        start = date(2000 + numbers[2], numbers[0], numbers[1])
        end = date(2000 + numbers[5], numbers[3], numbers[4])
    except ValueError:
        raise StatementError(_NO_PERIOD) from None
    return start, end


def _declared_totals(lines: list[str]) -> dict[Section, int]:
    totals: dict[Section, int] = {}
    payments = find_labeled_amount(lines, "Payments")
    credits = find_labeled_amount(lines, "Credits")
    if payments is not None and credits is not None:
        totals[Section.PAYMENTS_CREDITS] = -(payments + credits)
    for section, label in _TOTALS:
        found = find_labeled_amount(lines, label)
        if found is not None:
            totals[section] = -found
    return totals


def _cardholders(lines: list[str]) -> dict[str, str]:
    """Return each cardholder's name, with whitespace collapsed, and the card's last four."""
    found: dict[str, str] = {}
    for line in lines:
        match = _CARDHOLDER.match(line)
        if match is not None:
            found[collapse_ws(match.group(1))] = match.group(2)
    return found


def _rows(lines: list[str], start: date, end: date) -> list[StatementLine]:
    cards = _cardholders(lines)
    rows: list[StatementLine] = []
    section: Section | None = None
    holder: str | None = None
    for line in lines:
        name = collapse_ws(line)
        if line in _SECTIONS or name in cards:
            section = _SECTIONS.get(line, Section.PURCHASES)
            holder = name if name in cards else None
            continue
        if line.startswith("TOTAL"):
            section = None
            continue
        row = _ROW.fullmatch(line)
        if section is None or row is None:
            continue
        sale, post, text, amount = row.groups()
        cents = -parse_amount(amount)
        if cents == 0:
            continue
        rows.append(
            StatementLine(
                posted_date=parse_month_day(post, start, end),
                transaction_date=None if sale is None else parse_month_day(sale, start, end),
                description=collapse_ws(text),
                amount_cents=cents,
                section=section,
                card_last4=None if holder is None else cards[holder],
                cardholder=holder,
            )
        )
    return rows
