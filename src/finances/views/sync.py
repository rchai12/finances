"""SimpleFIN status, sync results, and the setup offers for new SimpleFIN accounts."""

from dataclasses import dataclass

from finances.analysis.simplefin import MappingStatus
from finances.domain.models import SyncFailure
from finances.sync.runner import LinkRun
from finances.views.format import balance_date_text, drift_text, last_pull_text


@dataclass(frozen=True)
class StatusRow:
    link: str
    account: str
    feed_account: str
    keychain: str
    last_pull: str
    balance_date: str
    drift: str


@dataclass(frozen=True)
class RunRow:
    link: str
    account: str
    feed_account: str
    new: str
    changed: str
    removed: str
    same: str
    drift: str
    problem: str


def failure_lines(failures: list[SyncFailure]) -> list[str]:
    """One line per stored failure, with the time in UTC to the minute."""
    return [
        (
            f"Last failure of link {item.link}: "
            f"{item.failed_at.strftime('%Y-%m-%d %H:%M UTC')}: {item.message}."
        )
        for item in failures
    ]


def status_rows(statuses: list[MappingStatus]) -> list[StatusRow]:
    """One row per mapping: its keychain state, last pull, and last balance drift."""
    return [
        StatusRow(
            item.link,
            item.account,
            item.feed_account,
            item.keychain,
            last_pull_text(item.last_pull),
            balance_date_text(item.balanced),
            drift_text(item.balanced),
        )
        for item in statuses
    ]


def run_rows(runs: list[LinkRun], names: dict[int, str]) -> list[RunRow]:
    """One row per account of each link that ran."""
    rows = []
    for run in runs:
        if run.report is None:
            continue
        for item in run.report.accounts:
            pull = item.pull
            counts = (
                ("", "", "", "")
                if pull is None
                else (str(pull.inserted), str(pull.updated), str(pull.removed), str(pull.unchanged))
            )
            rows.append(
                RunRow(
                    run.link,
                    "" if item.account_id is None else names[item.account_id],
                    item.provider_account_id,
                    *counts,
                    drift_text(pull),
                    item.problem or "",
                )
            )
    return rows


def simplefin_messages(runs: list[LinkRun]) -> list[tuple[str, str]]:
    return [
        (run.link, message)
        for run in runs
        if run.report is not None
        for message in run.report.messages
    ]
