"""The parser for Truist checking and savings statements."""

import re
from datetime import date, timedelta

from finances.domain.models import AccountType
from finances.ingest.parsers.helpers import collapse_ws, parse_amount, parse_month_day, squeeze
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

_AMOUNT = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\.[0-9]{2}"
_SHORT_DATE = r"[0-9]{2}/[0-9]{2}"
_MONEY = rf"(?P<money>(?:[-+=] *)*\${_AMOUNT})(?![0-9])"
_DIGIT = "[0-9]"
_SPACED_DATE = r"\s*".join(
    [_DIGIT, _DIGIT, "/", _DIGIT, _DIGIT, "/", _DIGIT, _DIGIT, _DIGIT, _DIGIT]
)


def _loose(label: str, after: str) -> re.Pattern[str]:
    """Match label with any whitespace inside it, at the line start or after two whitespace."""
    spaced = r"\s*".join(re.escape(character) for character in squeeze(label))
    return re.compile(rf"(?:^|(?<=\s\s)){spaced}{after}")


_KIND = re.compile(r"\b(CHECKING|SAVINGS)\b")
_NUMBER_AT_END = re.compile(r".*\s([0-9]{4,})")
_PREVIOUS = _loose("Your previous balance as of", rf"\s*(?P<date>{_SPACED_DATE})\s+{_MONEY}")
_NEW = _loose("Your new balance as of", rf"\s*(?P<date>{_SPACED_DATE})\s+{_MONEY}")
_ROW = re.compile(rf"({_SHORT_DATE})\s+(.+?)\s+({_AMOUNT})")
_CHECK = re.compile(rf"({_SHORT_DATE})\s+(?:\*\s*)?([0-9]+)\s+({_AMOUNT})")
_CARD = re.compile(r"[0-9]{4}")
_MONTH_DAY = re.compile(r"[0-9]{2}-[0-9]{2}")

_TYPES = {"CHECKING": AccountType.CHECKING, "SAVINGS": AccountType.SAVINGS}
_SECTIONS = {
    squeeze("Checks"): Section.CHECKS,
    squeeze("Other withdrawals, debits and service charges"): Section.WITHDRAWALS,
    squeeze("Deposits, credits and interest"): Section.DEPOSITS,
}
_TOTALS = (
    (_loose("Total checks", rf"\s+{_MONEY}"), Section.CHECKS, -1),
    (
        _loose("Total other withdrawals, debits and service charges", rf"\s+{_MONEY}"),
        Section.WITHDRAWALS,
        -1,
    ),
    (_loose("Total deposits, credits and interest", rf"\s+{_MONEY}"), Section.DEPOSITS, 1),
)

_NO_ACCOUNT = "truist: account line not found"
_NO_PREVIOUS = "truist: previous balance not found"
_NO_NEW = "truist: new balance not found"


class TruistDepositParser:
    name = "truist_deposit"

    def detect(self, first_page: str) -> bool:
        return "Truist" in first_page and "Your account statement" in first_page

    def parse(self, pages: list[str]) -> ParsedStatement:
        lines = [line.strip() for page in pages for line in page.splitlines()]
        account = _account(lines)
        if account is None:
            raise StatementError(_NO_ACCOUNT)
        previous = _balance(lines, _PREVIOUS)
        if previous is None:
            raise StatementError(_NO_PREVIOUS)
        new = _balance(lines, _NEW)
        if new is None:
            raise StatementError(_NO_NEW)
        try:
            start = previous[0] + timedelta(days=1)
        except OverflowError:
            raise StatementError(_NO_PREVIOUS) from None
        end = new[0]
        account_type, last4 = account
        return ParsedStatement(
            parser_name=self.name,
            institution="Truist",
            account_type=account_type,
            account_last4=last4,
            period_start=start,
            period_end=end,
            opening_balance_cents=previous[1],
            closing_balance_cents=new[1],
            lines=_rows(lines, start, end),
            declared_section_totals=_declared_totals(lines),
        )


def _account(lines: list[str]) -> tuple[AccountType, str] | None:
    """Return the account type and last four digits from the first account line, or None."""
    for line in lines:
        kind = _KIND.search(line)
        number = _NUMBER_AT_END.fullmatch(line)
        if kind is not None and number is not None:
            return _TYPES[kind.group(1)], number.group(1)[-4:]
    return None


def _money(match: re.Match[str]) -> int | None:
    try:
        return parse_amount(match.group("money"))
    except ValueError:
        return None


def _date(match: re.Match[str]) -> date | None:
    month, day, year = (int(part) for part in squeeze(match.group("date")).split("/"))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _balance(lines: list[str], pattern: re.Pattern[str]) -> tuple[date, int] | None:
    """Return the date and amount of the first line that fits pattern with a real date and money."""
    for line in lines:
        for match in pattern.finditer(line):
            when = _date(match)
            amount = _money(match)
            if when is not None and amount is not None:
                return when, amount
    return None


def _first_money(lines: list[str], pattern: re.Pattern[str]) -> int | None:
    for line in lines:
        for match in pattern.finditer(line):
            amount = _money(match)
            if amount is not None:
                return amount
    return None


def _declared_totals(lines: list[str]) -> dict[Section, int]:
    totals: dict[Section, int] = {}
    for pattern, section, sign in _TOTALS:
        found = _first_money(lines, pattern)
        if found is not None:
            totals[section] = sign * found
    return totals


def _card_details(description: str, start: date, end: date) -> tuple[date | None, str | None]:
    """Return the purchase date and card of a debit card row, or None for each."""
    if not description.startswith("DEBIT CARD "):
        return None, None
    words = description.split()
    card = words[-1] if _CARD.fullmatch(words[-1]) else None
    days = [word for word in words if _MONTH_DAY.fullmatch(word)]
    if not days:
        return None, card
    try:
        return parse_month_day(days[-1], start, end), card
    except StatementError:
        return None, card


def _checks(line: str, start: date, end: date) -> list[StatementLine]:
    found: list[StatementLine] = []
    for match in _CHECK.finditer(line):
        day, number, amount = match.groups()
        cents = -parse_amount(amount)
        if cents == 0:
            continue
        found.append(
            StatementLine(
                parse_month_day(day, start, end),
                None,
                f"CHECK {number}",
                cents,
                Section.CHECKS,
                external_ref=number,
            )
        )
    return found


def _row(line: str, section: Section, start: date, end: date) -> StatementLine | None:
    match = _ROW.fullmatch(line)
    if match is None:
        return None
    day, text, amount = match.groups()
    cents = parse_amount(amount)
    if cents == 0:
        return None
    description = collapse_ws(text)
    bought, card = _card_details(description, start, end)
    return StatementLine(
        posted_date=parse_month_day(day, start, end),
        transaction_date=bought,
        description=description,
        amount_cents=-cents if section is Section.WITHDRAWALS else cents,
        section=section,
        card_last4=card,
    )


def _rows(lines: list[str], start: date, end: date) -> list[StatementLine]:
    rows: list[StatementLine] = []
    section: Section | None = None
    for line in lines:
        tight = squeeze(line)
        if tight in _SECTIONS:
            section = _SECTIONS[tight]
        elif tight.startswith("Total"):
            section = None
        elif section is Section.CHECKS:
            rows += _checks(line, start, end)
        elif section is not None:
            row = _row(line, section, start, end)
            if row is not None:
                rows.append(row)
    return rows
