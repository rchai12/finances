"""Gather account and backup facts for data-health problems."""

from datetime import UTC, date
from pathlib import Path

from sqlalchemy.orm import Session

from finances.db.backup import list_backups, taken_at
from finances.db.repositories import (
    account_data_span,
    latest_feed_pull,
    list_accounts,
    list_feed_accounts,
    list_statements,
    list_sync_failures,
    statement_periods,
)
from finances.domain.health import AccountFacts, Problem, health_problems
from finances.domain.periods import statement_gaps


def account_facts(session: Session) -> list[AccountFacts]:
    """One facts row per active account, in list_accounts order."""
    mapped = {item.account_id for item in list_feed_accounts(session)}
    rows: list[AccountFacts] = []
    for account in list_accounts(session):
        pull = latest_feed_pull(session, account.id)
        balance_pull = latest_feed_pull(session, account.id, with_balance=True)
        statements = list_statements(session, account.id)
        newest_end = None if not statements else statements[0].period_end
        last_pull = None if pull is None else pull.pulled_at.astimezone(UTC).date()
        drift_cents = None if balance_pull is None else balance_pull.drift_cents
        drift_date = None if balance_pull is None else balance_pull.balance_date
        rows.append(
            AccountFacts(
                name=account.name,
                mapped=account.id in mapped,
                last_pull=last_pull,
                drift_cents=drift_cents,
                drift_date=drift_date,
                newest_statement_end=newest_end,
                has_data=account_data_span(session, account.id) is not None,
                gaps=tuple(statement_gaps(statement_periods(session, account.id))),
            )
        )
    return rows


def gather_health(session: Session, backup_folder: Path, as_of: date) -> list[Problem]:
    """Problems for the active accounts and the newest backup in the folder."""
    backups = list_backups(backup_folder)
    newest = None if not backups else taken_at(backups[0]).astimezone(UTC).date()
    return health_problems(
        account_facts(session), newest, as_of, failures=list_sync_failures(session)
    )
