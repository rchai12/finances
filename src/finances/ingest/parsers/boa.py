"""The parser for Bank of America credit card statements."""

import re
from datetime import date

from finances.domain.models import AccountType
from finances.ingest.parsers.helpers import (
    MONTHS,
    collapse_ws,
    find_labeled_amount,
    parse_amount,
    parse_month_day,
)
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

_DATE = r"[0-9]{2}/[0-9]{2}"
_AMOUNT = r"-?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\.[0-9]{2}"

_ACCOUNT = re.compile(r"Account# [0-9]{4} [0-9]{4} [0-9]{4} ([0-9]{4})")
_PERIOD = re.compile(r"([A-Z][a-z]+) ([0-9]{1,2}) - ([A-Z][a-z]+) ([0-9]{1,2}), ([0-9]{4})")
_SIX = re.compile(rf"({_DATE})\s+({_DATE})\s+(.+?)\s+([0-9]{{4}})\s+([0-9]{{4}})\s+({_AMOUNT})")
_FOUR = re.compile(rf"({_DATE})\s+({_DATE})\s+(.+?)\s+({_AMOUNT})")

_SECTIONS = {
    "Payments and Other Credits": Section.PAYMENTS_CREDITS,
    "Purchases and Adjustments": Section.PURCHASES,
    "Fees Charged": Section.FEES,
    "Interest Charged": Section.INTEREST,
}

_NO_ACCOUNT = "boa: account number not found"
_NO_PERIOD = "boa: statement period not found"
_NO_PREVIOUS = "boa: previous balance not found"
_NO_NEW = "boa: new balance not found"


class BoaCardParser:
    name = "boa_card"

    def detect(self, first_page: str) -> bool:
        return "bankofamerica.com" in first_page and "Account#" in first_page

    def parse(self, pages: list[str]) -> ParsedStatement:
        lines = [line.strip() for page in pages for line in page.splitlines()]
        text = "\n".join(lines)
        account = _ACCOUNT.search(text)
        if account is None:
            raise StatementError(_NO_ACCOUNT)
        start, end = _period(text)
        previous = find_labeled_amount(lines, "Previous Balance")
        if previous is None:
            raise StatementError(_NO_PREVIOUS)
        new = find_labeled_amount(lines, "New Balance Total")
        if new is None:
            raise StatementError(_NO_NEW)
        return ParsedStatement(
            parser_name=self.name,
            institution="Bank of America",
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
    first_month, first_day, last_month, last_day, year = match.groups()
    try:
        start_month = MONTHS.index(first_month[:3].lower()) + 1
        end_month = MONTHS.index(last_month[:3].lower()) + 1
        end = date(int(year), end_month, int(last_day))
        start_year = end.year - 1 if start_month > end_month else end.year
        return date(start_year, start_month, int(first_day)), end
    except ValueError:
        raise StatementError(_NO_PERIOD) from None


def _declared_totals(lines: list[str]) -> dict[Section, int]:
    totals: dict[Section, int] = {}
    for label, section in _SECTIONS.items():
        found = find_labeled_amount(lines, label)
        if found is not None:
            totals[section] = -found
    return totals


def _split(line: str) -> tuple[str, str, str, str | None, str | None, str] | None:
    """Return the dates, description, reference, card, and amount of a row, or None."""
    six = _SIX.fullmatch(line)
    if six is not None:
        trans, post, text, ref, card, amount = six.groups()
        return trans, post, text, ref, card, amount
    four = _FOUR.fullmatch(line)
    if four is None:
        return None
    trans, post, text, amount = four.groups()
    return trans, post, text, None, None, amount


def _rows(lines: list[str], start: date, end: date) -> list[StatementLine]:
    rows: list[StatementLine] = []
    section: Section | None = None
    for line in lines:
        if line in _SECTIONS:
            section = _SECTIONS[line]
            continue
        if line.startswith("TOTAL"):
            section = None
            continue
        parts = _split(line)
        if section is None or parts is None:
            continue
        trans, post, text, ref, card, amount = parts
        cents = -parse_amount(amount)
        if cents == 0:
            continue
        rows.append(
            StatementLine(
                posted_date=parse_month_day(post, start, end),
                transaction_date=parse_month_day(trans, start, end),
                description=collapse_ws(text),
                amount_cents=cents,
                section=section,
                card_last4=card,
                external_ref=ref,
            )
        )
    return rows
