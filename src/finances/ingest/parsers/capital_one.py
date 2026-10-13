"""The parser for Capital One credit card statements."""

import re
from datetime import date

from finances.domain.models import AccountType
from finances.ingest.parsers.helpers import MONTHS, collapse_ws, parse_amount, parse_month_day
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

_MONEY = r"\$(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\.[0-9]{2}"
_SIGNED_MONEY = rf"(?:[-+=] *)*{_MONEY}"
_ANYWHERE = r"(?:^|\s\s)"
_DATE = r"[A-Z][a-z]{2} [0-9]{1,2}"
_DAY = r"([A-Z][a-z]{2}) ([0-9]{1,2}), ([0-9]{4})"

_ENDING = re.compile(r"ending in ([0-9]{4})")
_PERIOD = re.compile(rf"{_DAY} - {_DAY}")
_HEADING = re.compile(
    r"(.+?) #([0-9]{4}): (Payments, Credits and Adjustments|Total Transactions|Transactions)"
)
_ROW = re.compile(rf"({_DATE})\s+({_DATE})\s+(.+?)\s+((?:- )?{_MONEY})")

_OPENS = {
    "Payments, Credits and Adjustments": Section.PAYMENTS_CREDITS,
    "Transactions": Section.PURCHASES,
}
_INTEREST_LABELS = (
    "Interest Charge on Purchases",
    "Interest Charge on Cash Advances",
    "Interest Charge on Other Balances",
)
_FEES_LABEL = "Total Fees for This Period"
_TOTALS = (
    (Section.FEES, "Fees Charged"),
    (Section.INTEREST, "Interest Charged"),
    (Section.PURCHASES, "Total Transactions for This Period"),
)

_NO_ENDING = "capital one: card ending not found"
_NO_PERIOD = "capital one: billing period not found"
_NO_PREVIOUS = "capital one: previous balance not found"
_NO_NEW = "capital one: new balance not found"


class CapitalOneCardParser:
    name = "capital_one_card"

    def detect(self, first_page: str) -> bool:
        brand = "Capital One" in first_page or "capitalone.com" in first_page
        return brand and "days in Billing Cycle" in first_page

    def parse(self, pages: list[str]) -> ParsedStatement:
        lines = [line.strip() for page in pages for line in page.splitlines()]
        ending = _ENDING.search("\n".join(lines))
        if ending is None:
            raise StatementError(_NO_ENDING)
        start, end = _period("\n".join(lines))
        previous = _find(lines, "Previous Balance")
        if previous is None:
            raise StatementError(_NO_PREVIOUS)
        new = _find(lines, "New Balance")
        if new is None:
            raise StatementError(_NO_NEW)
        return ParsedStatement(
            parser_name=self.name,
            institution="Capital One",
            account_type=AccountType.CREDIT_CARD,
            account_last4=ending.group(1),
            period_start=start,
            period_end=end,
            opening_balance_cents=-previous[1],
            closing_balance_cents=-new[1],
            lines=_rows(lines, start, end) + _charges(lines, end),
            declared_section_totals=_declared_totals(lines),
        )


def _period(text: str) -> tuple[date, date]:
    match = _PERIOD.search(text)
    if match is None:
        raise StatementError(_NO_PERIOD)
    try:
        return _date(*match.group(1, 2, 3)), _date(*match.group(4, 5, 6))
    except ValueError:
        raise StatementError(_NO_PERIOD) from None


def _date(month: str, day: str, year: str) -> date:
    return date(int(year), MONTHS.index(month.lower()) + 1, int(day))


def _find(lines: list[str], label: str, before: str = _ANYWHERE) -> tuple[int, int] | None:
    """Return the line index and amount of the first line where label is followed by money."""
    pattern = re.compile(before + re.escape(label) + rf"\s+({_SIGNED_MONEY})")
    for index, line in enumerate(lines):
        match = pattern.search(line)
        if match is None:
            continue
        try:
            return index, parse_amount(match.group(1))
        except ValueError:
            continue
    return None


def _declared_totals(lines: list[str]) -> dict[Section, int]:
    totals: dict[Section, int] = {}
    payments = _find(lines, "Payments")
    credits = _find(lines, "Other Credits")
    if payments is not None and credits is not None:
        totals[Section.PAYMENTS_CREDITS] = -(payments[1] + credits[1])
    for section, label in _TOTALS:
        found = _find(lines, label)
        if found is not None:
            totals[section] = -found[1]
    return totals


def _rows(lines: list[str], start: date, end: date) -> list[StatementLine]:
    rows: list[StatementLine] = []
    section: Section | None = None
    holder: str | None = None
    last4: str | None = None
    for line in lines:
        heading = _HEADING.match(line)
        if heading is not None:
            holder, last4, kind = heading.groups()
            section = _OPENS.get(kind)
            continue
        row = _ROW.fullmatch(line)
        if section is None or row is None:
            continue
        rows.append(
            StatementLine(
                posted_date=parse_month_day(row.group(2), start, end),
                transaction_date=parse_month_day(row.group(1), start, end),
                description=collapse_ws(row.group(3)),
                amount_cents=-parse_amount(row.group(4)),
                section=section,
                card_last4=last4,
                cardholder=holder,
            )
        )
    return rows


def _charges(lines: list[str], end: date) -> list[StatementLine]:
    """Return the interest lines in printed order, then the fee line."""
    interest: list[tuple[int, str, int]] = []
    for label in _INTEREST_LABELS:
        found = _find(lines, label, before="^")
        if found is not None and found[1] != 0:
            interest.append((found[0], label, found[1]))
    interest.sort()
    charges = [
        StatementLine(end, None, label.upper(), -cents, Section.INTEREST)
        for _, label, cents in interest
    ]
    fees = _find(lines, _FEES_LABEL)
    if fees is not None and fees[1] != 0:
        charges.append(StatementLine(end, None, _FEES_LABEL.upper(), -fees[1], Section.FEES))
    return charges
