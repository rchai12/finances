"""Gaps between statement periods, per account."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from finances.db.repositories import list_accounts, statement_periods
from finances.domain.periods import statement_gaps


@dataclass(frozen=True)
class StatementGap:
    account: str
    start: date
    end: date


def statement_gap_lines(session: Session) -> list[StatementGap]:
    """Gaps for every account that has statements, by account name then start."""
    accounts = sorted(
        list_accounts(session, include_inactive=True),
        key=lambda account: (account.name.lower(), account.name),
    )
    lines: list[StatementGap] = []
    for account in accounts:
        periods = statement_periods(session, account.id)
        if not periods:
            continue
        for start, end in statement_gaps(periods):
            lines.append(StatementGap(account.name, start, end))
    return lines
