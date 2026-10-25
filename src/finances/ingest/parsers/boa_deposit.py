"""The parser for Bank of America checking and savings statements."""

import re
from datetime import date

from finances.domain.models import AccountType
from finances.ingest.parsers.helpers import MONTHS, collapse_ws, infer_year, parse_amount, squeeze
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

_AMOUNT = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\.[0-9]{2}"
_LAST_MONEY = re.compile(rf"(-?\$?{_AMOUNT})\s*$")
_ACCOUNT = re.compile(r"Account number:\s*((?:[0-9]+\s*)*[0-9]+)")
_PERIOD = re.compile(
    r"for\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})\s+to\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
    re.IGNORECASE,
)
_BEGIN = re.compile(
    rf"Beginning balance on\s+[A-Za-z]+\s+\d{{1,2}},\s+\d{{4}}\s+(-\${_AMOUNT}|\${_AMOUNT})"
)
_END = re.compile(
    rf"Ending balance on\s+[A-Za-z]+\s+\d{{1,2}},\s+\d{{4}}\s+(-\${_AMOUNT}|\${_AMOUNT})"
)
_ROW = re.compile(rf"^(\d{{2}}/\d{{2}}/\d{{2}})\s+(.+?)\s+(-?{_AMOUNT})$")
_CHECK = re.compile(rf"(\d{{2}}/\d{{2}}/\d{{2}})\s+(\*?[0-9]+\*?)\s+(-?{_AMOUNT})")
_PURCHASE = re.compile(r"^(?:CHECKCARD|PURCHASE) (\d{4})\b")

_HEADINGS = {
    squeeze("Deposits and other additions"): Section.DEPOSITS,
    squeeze("ATM and debit card subtractions"): Section.WITHDRAWALS,
    squeeze("Other subtractions"): Section.WITHDRAWALS,
    squeeze("Checks"): Section.CHECKS,
    squeeze("Service fees"): Section.FEES,
}
_TOTAL_LABELS = (
    (squeeze("Total deposits and other additions"), Section.DEPOSITS),
    (squeeze("Total ATM and debit card subtractions"), Section.WITHDRAWALS),
    (squeeze("Total other subtractions"), Section.WITHDRAWALS),
    (squeeze("Total checks"), Section.CHECKS),
    (squeeze("Total service fees"), Section.FEES),
)

_NO_ACCOUNT = "boa_deposit: account number not found"
_NO_PERIOD = "boa_deposit: statement period not found"
_NO_BEGIN = "boa_deposit: beginning balance not found"
_NO_END = "boa_deposit: ending balance not found"
_BAD_DATE = "boa_deposit: invalid date"


class BoaDepositParser:
    name = "boa_deposit"

    def detect(self, first_page: str) -> bool:
        return (
            "bankofamerica.com" in first_page
            and "Account number:" in first_page
            and "Beginning balance on" in first_page
        )

    def parse(self, pages: list[str]) -> ParsedStatement:
        lines = [line.strip() for page in pages for line in page.splitlines()]
        account_index, last4 = _account(lines)
        if last4 is None:
            raise StatementError(_NO_ACCOUNT)
        period = _period(lines)
        if period is None:
            raise StatementError(_NO_PERIOD)
        start, end = period
        opening = _first_amount(lines, _BEGIN)
        if opening is None:
            raise StatementError(_NO_BEGIN)
        closing = _first_amount(lines, _END)
        if closing is None:
            raise StatementError(_NO_END)
        return ParsedStatement(
            parser_name=self.name,
            institution="Bank of America",
            account_type=_account_type(lines, account_index),
            account_last4=last4,
            period_start=start,
            period_end=end,
            opening_balance_cents=opening,
            closing_balance_cents=closing,
            lines=_rows(lines, start, end),
            declared_section_totals=_declared_totals(lines),
        )


def _month(name: str) -> int | None:
    key = name[:3].lower()
    if key not in MONTHS:
        return None
    return MONTHS.index(key) + 1


def _account(lines: list[str]) -> tuple[int, str | None]:
    for index, line in enumerate(lines):
        match = _ACCOUNT.search(line)
        if match is None:
            continue
        digits = "".join(character for character in match.group(1) if character.isdigit())
        if len(digits) >= 4:
            return index, digits[-4:]
    return -1, None


def _account_type(lines: list[str], account_index: int) -> AccountType:
    product = None
    for line in lines[:account_index]:
        if line.startswith("Your "):
            product = line
    if product is not None and "Savings" in product:
        return AccountType.SAVINGS
    return AccountType.CHECKING


def _period(lines: list[str]) -> tuple[date, date] | None:
    for line in lines:
        match = _PERIOD.search(line)
        if match is None:
            continue
        start_month = _month(match.group(1))
        end_month = _month(match.group(4))
        if start_month is None or end_month is None:
            return None
        try:
            start = date(int(match.group(3)), start_month, int(match.group(2)))
            end = date(int(match.group(6)), end_month, int(match.group(5)))
        except ValueError:
            return None
        return start, end
    return None


def _first_amount(lines: list[str], pattern: re.Pattern[str]) -> int | None:
    for line in lines:
        match = pattern.search(line)
        if match is None:
            continue
        return parse_amount(match.group(1))
    return None


def _posted(text: str) -> date:
    month, day, year = (int(part) for part in text.split("/"))
    try:
        return date(2000 + year, month, day)
    except ValueError:
        raise StatementError(_BAD_DATE) from None


def _purchase_date(description: str, start: date, end: date) -> date | None:
    match = _PURCHASE.match(description)
    if match is None:
        return None
    stamp = match.group(1)
    try:
        return infer_year(int(stamp[:2]), int(stamp[2:]), start, end)
    except StatementError:
        return None


def _row(line: str, section: Section, start: date, end: date) -> StatementLine | None:
    match = _ROW.fullmatch(line)
    if match is None:
        return None
    day, text, amount = match.groups()
    cents = parse_amount(amount)
    if cents == 0:
        return None
    description = collapse_ws(text)
    return StatementLine(
        posted_date=_posted(day),
        transaction_date=_purchase_date(description, start, end),
        description=description,
        amount_cents=cents,
        section=section,
    )


def _checks(line: str) -> list[StatementLine]:
    found: list[StatementLine] = []
    for match in _CHECK.finditer(line):
        day, number, amount = match.groups()
        cents = parse_amount(amount)
        if cents == 0:
            continue
        check = number.strip("*")
        found.append(
            StatementLine(
                _posted(day),
                None,
                f"CHECK {check}",
                cents,
                Section.CHECKS,
                external_ref=check,
            )
        )
    return found


def _rows(lines: list[str], start: date, end: date) -> list[StatementLine]:
    rows: list[StatementLine] = []
    section: Section | None = None
    for line in lines:
        tight = squeeze(line)
        if tight in _HEADINGS:
            section = _HEADINGS[tight]
        elif tight.startswith("Total"):
            section = None
        elif section is Section.CHECKS:
            rows += _checks(line)
        elif section is not None:
            row = _row(line, section, start, end)
            if row is not None:
                rows.append(row)
    return rows


def _declared_totals(lines: list[str]) -> dict[Section, int]:
    totals: dict[Section, int] = {}
    withdrawals = 0
    seen: set[str] = set()
    for line in lines:
        tight = squeeze(line)
        for label, section in _TOTAL_LABELS:
            if label in seen or not tight.startswith(label):
                continue
            match = _LAST_MONEY.search(line)
            if match is None:
                continue
            amount = parse_amount(match.group(1))
            seen.add(label)
            if section is Section.WITHDRAWALS:
                withdrawals += amount
                totals[Section.WITHDRAWALS] = withdrawals
            else:
                totals[section] = amount
            break
    return totals
