"""How far each open account's data can be trusted."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from finances.analysis.health import account_facts, gather_health
from finances.db.repositories import account_data_span, list_accounts, statement_periods
from finances.domain.health import AccountFacts, Problem
from finances.domain.periods import joined_periods


@dataclass(frozen=True)
class AccountCoverage:
    type: str
    facts: AccountFacts
    span: tuple[date, date] | None
    audited: list[tuple[date, date]]


@dataclass(frozen=True)
class CoverageReport:
    as_of: date
    accounts: list[AccountCoverage]
    problems: list[Problem]


def coverage_report(session: Session, backup_folder: Path, as_of: date) -> CoverageReport:
    facts = account_facts(session)
    accounts = []
    for account, row in zip(list_accounts(session), facts, strict=True):
        accounts.append(
            AccountCoverage(
                type=account.type.value,
                facts=row,
                span=account_data_span(session, account.id),
                audited=joined_periods(statement_periods(session, account.id)),
            )
        )
    return CoverageReport(as_of, accounts, gather_health(session, backup_folder, as_of))
