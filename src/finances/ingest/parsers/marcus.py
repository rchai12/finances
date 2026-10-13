"""The parser for Marcus by Goldman Sachs online savings statements."""

import re
from datetime import date

from finances.domain.models import AccountType
from finances.ingest.parsers.helpers import collapse_ws, parse_amount
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

_MONEY = r"\$(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\.[0-9]{2}"
_FULL_DATE = r"([0-9]{2})/([0-9]{2})/([0-9]{4})"

_ACCOUNT = re.compile(r"Account Number\s+([0-9]{4,})")
_PERIOD = re.compile(rf"Statement Period\s+{_FULL_DATE}\s*to\s*{_FULL_DATE}")
_BALANCE_LINE = re.compile(rf"{_FULL_DATE}\s+(.+?)\s+(-?{_MONEY})")
_ROW = re.compile(rf"{_FULL_DATE}\s+(.+?)\s+({_MONEY})\s+(-?{_MONEY})")

_NO_ACCOUNT = "marcus: account number not found"
_NO_PERIOD = "marcus: statement period not found"
_NO_BEGINNING = "marcus: beginning balance not found"
_NO_ENDING = "marcus: ending balance not found"


class MarcusSavingsParser:
    name = "marcus_savings"

    def detect(self, first_page: str) -> bool:
        return (
            "Goldman Sachs Bank USA" in first_page
            and "ONLINE SAVINGS ACCOUNT STATEMENT" in first_page
        )

    def parse(self, pages: list[str]) -> ParsedStatement:
        lines = [line.strip() for page in pages for line in page.splitlines()]
        text = "\n".join(lines)
        account = _ACCOUNT.search(text)
        if account is None:
            raise StatementError(_NO_ACCOUNT)
        start, end = _period(text)
        opening = _balance(lines, "BeginningBalance")
        if opening is None:
            raise StatementError(_NO_BEGINNING)
        closing = _balance(lines, "EndingBalance")
        if closing is None:
            raise StatementError(_NO_ENDING)
        return ParsedStatement(
            parser_name=self.name,
            institution="Marcus by Goldman Sachs",
            account_type=AccountType.SAVINGS,
            account_last4=account.group(1)[-4:],
            period_start=start,
            period_end=end,
            opening_balance_cents=opening,
            closing_balance_cents=closing,
            lines=_rows(lines, opening),
        )


def _period(text: str) -> tuple[date, date]:
    match = _PERIOD.search(text)
    if match is None:
        raise StatementError(_NO_PERIOD)
    numbers = [int(part) for part in match.groups()]
    try:
        start = date(numbers[2], numbers[0], numbers[1])
        end = date(numbers[5], numbers[3], numbers[4])
    except ValueError:
        raise StatementError(_NO_PERIOD) from None
    return start, end


def _squeezed(text: str) -> str:
    return "".join(text.split())


def _balance(lines: list[str], label: str) -> int | None:
    """Return the money of the first balance line whose label, without spaces, is label."""
    for line in lines:
        match = _BALANCE_LINE.fullmatch(line)
        if match is not None and _squeezed(match.group(4)) == label:
            return parse_amount(match.group(5))
    return None


def _rows(lines: list[str], opening: int) -> list[StatementLine]:
    rows: list[StatementLine] = []
    balance = opening
    number = 0
    for line in lines:
        match = _ROW.fullmatch(line)
        if match is None:
            continue
        number += 1
        month, day, year, text, printed, after = match.groups()
        try:
            posted = date(int(year), int(month), int(day))
        except ValueError:
            raise StatementError(f"marcus: row {number} has an impossible date") from None
        new_balance = parse_amount(after)
        cents = new_balance - balance
        if abs(cents) != parse_amount(printed):
            raise StatementError(f"marcus: row {number} does not match its balance")
        balance = new_balance
        if cents == 0:
            continue
        description = collapse_ws(text)
        if _squeezed(description) == "InterestPaid":
            section = Section.INTEREST
        elif cents > 0:
            section = Section.DEPOSITS
        else:
            section = Section.WITHDRAWALS
        rows.append(StatementLine(posted, None, description, cents, section))
    return rows
