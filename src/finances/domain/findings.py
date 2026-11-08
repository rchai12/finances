"""Statuses a person set on a finding: handled for that month, or ignored in every month."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from finances.domain.insights import Finding

HANDLED = "handled"
IGNORED = "ignored"
FINDING_STATUSES = (HANDLED, IGNORED)


@dataclass(frozen=True)
class FindingStatus:
    id: int
    type: str
    subject: str
    month: date | None
    status: str
    set_at: datetime


@dataclass(frozen=True)
class ClosedFinding:
    finding: Finding
    status: str


def finding_text(type: str, subject: str, month: date | None) -> str:
    when = "every month" if month is None else month.isoformat()[:7]
    if subject:
        return f"{type} for {subject} in {when}"
    return f"{type} in {when}"


def status_for(
    type: str, subject: str, month: date, statuses: Iterable[FindingStatus]
) -> str | None:
    items = list(statuses)
    for item in items:
        if (
            item.status == IGNORED
            and item.type == type
            and item.subject.casefold() == subject.casefold()
        ):
            return IGNORED
    for item in items:
        if (
            item.status == HANDLED
            and item.type == type
            and item.subject.casefold() == subject.casefold()
            and item.month == month
        ):
            return HANDLED
    return None


def status_of(finding: Finding, statuses: Iterable[FindingStatus]) -> str | None:
    return status_for(finding.type, finding.subject, finding.month, statuses)


def split_findings(
    findings: Iterable[Finding], statuses: Iterable[FindingStatus]
) -> tuple[list[Finding], list[ClosedFinding]]:
    items = list(statuses)
    open_ones: list[Finding] = []
    closed: list[ClosedFinding] = []
    for finding in findings:
        status = status_of(finding, items)
        if status is None:
            open_ones.append(finding)
        else:
            closed.append(ClosedFinding(finding, status))
    return open_ones, closed
