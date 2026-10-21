"""When the household's data is out of date or incomplete. Pure: no database."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from finances.domain.models import SyncFailure
from finances.domain.money import format_cents

BACKUP_STALE_DAYS = 2
SYNC_STALE_DAYS = 3
STATEMENT_STALE_DAYS = 45
KINDS = ("backup", "sync", "drift", "statements", "gap")

_BACKUP_ACTION = "Run fin backup run, or press Back up now on the Backups page."
_SYNC_ACTION = "Run fin sync run; if it fails, link SimpleFIN again (docs/sync-setup.md)."
_DRIFT_ACTION = "Look for a missing or extra transaction, or import the statement for that period."
_STATEMENTS_ACTION = (
    "Upload the newest statement on the Statements page, or run fin import statement."
)
_GAP_ACTION = "Upload the statement for those days."


@dataclass(frozen=True)
class AccountFacts:
    name: str
    mapped: bool
    last_pull: date | None
    drift_cents: int | None
    drift_date: date | None
    newest_statement_end: date | None
    has_data: bool
    gaps: tuple[tuple[date, date], ...] = ()


@dataclass(frozen=True)
class Problem:
    kind: str
    account: str
    detail: str
    action: str


def health_problems(
    accounts: Iterable[AccountFacts],
    newest_backup: date | None,
    as_of: date,
    *,
    failures: Iterable[SyncFailure] = (),
) -> list[Problem]:
    """Every problem for the accounts and backup, ordered by kind then account then detail."""
    found: list[Problem] = []
    if newest_backup is None:
        found.append(Problem("backup", "", "No backup yet.", _BACKUP_ACTION))
    else:
        days = (as_of - newest_backup).days
        if days > BACKUP_STALE_DAYS:
            found.append(
                Problem(
                    "backup",
                    "",
                    f"The newest backup is {days} days old (taken {newest_backup.isoformat()}).",
                    _BACKUP_ACTION,
                )
            )
    for account in accounts:
        if account.mapped:
            if account.last_pull is None:
                found.append(
                    Problem(
                        "sync",
                        account.name,
                        "Mapped to SimpleFIN but never synced.",
                        _SYNC_ACTION,
                    )
                )
            else:
                days = (as_of - account.last_pull).days
                if days > SYNC_STALE_DAYS:
                    found.append(
                        Problem(
                            "sync",
                            account.name,
                            (
                                f"No SimpleFIN pull for {days} days "
                                f"(last on {account.last_pull.isoformat()})."
                            ),
                            _SYNC_ACTION,
                        )
                    )
            if account.drift_cents is not None and account.drift_cents != 0:
                when = "" if account.drift_date is None else account.drift_date.isoformat()
                found.append(
                    Problem(
                        "drift",
                        account.name,
                        (
                            "The balance differs from SimpleFIN's by "
                            f"{format_cents(account.drift_cents)} on {when}."
                        ),
                        _DRIFT_ACTION,
                    )
                )
        elif account.newest_statement_end is None and not account.has_data:
            found.append(
                Problem("statements", account.name, "No statements yet.", _STATEMENTS_ACTION)
            )
        elif account.newest_statement_end is not None:
            days = (as_of - account.newest_statement_end).days
            if days > STATEMENT_STALE_DAYS:
                found.append(
                    Problem(
                        "statements",
                        account.name,
                        (
                            f"The newest statement ends {account.newest_statement_end.isoformat()} "
                            f"({days} days ago)."
                        ),
                        _STATEMENTS_ACTION,
                    )
                )
        for start, end in account.gaps:
            found.append(
                Problem(
                    "gap",
                    account.name,
                    f"No statement covers {start.isoformat()} to {end.isoformat()}.",
                    _GAP_ACTION,
                )
            )
    for item in failures:
        found.append(
            Problem(
                "sync",
                "",
                (
                    f"The last sync of link {item.link} failed on "
                    f"{item.failed_at.date().isoformat()}: {item.message}."
                ),
                _SYNC_ACTION,
            )
        )
    order = {kind: index for index, kind in enumerate(KINDS)}

    def sort_key(problem: Problem) -> tuple[int, str, str, str]:
        return order[problem.kind], problem.account.lower(), problem.account, problem.detail

    return sorted(found, key=sort_key)
