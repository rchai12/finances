"""A month's findings and merchant stats, against the three months before it."""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from finances.analysis.budgets import budget_report
from finances.analysis.recurring import recurring_charges
from finances.analysis.spending import load_flows
from finances.db.repositories.findings import list_finding_statuses
from finances.domain.findings import ClosedFinding, finding_text, split_findings
from finances.domain.insights import (
    TYPES,
    Finding,
    MerchantStat,
    charges_found,
    duplicates,
    frequent_small,
    large_first_charges,
    merchant_stats,
    order_findings,
    over_budget,
    overlaps,
    price_increases,
    spikes,
)
from finances.domain.periods import months_ending
from finances.domain.spending import SPENDING, Flow

_WINDOW_MONTHS = 4


@dataclass(frozen=True)
class InsightsReport:
    month: date
    findings: list[Finding]
    merchants: list[MerchantStat]
    closed: list[ClosedFinding] = field(default_factory=list)


def _categories(flows: list[Flow]) -> dict[str, str]:
    """Each merchant's category on its latest charge: by day, then the order loaded."""
    charges = [flow for flow in flows if flow.kind == SPENDING and flow.amount_cents < 0]
    return {flow.merchant: flow.category for flow in sorted(charges, key=lambda flow: flow.day)}


def _seen_before(flows: list[Flow], first: date) -> set[str]:
    return {
        flow.merchant
        for flow in flows
        if flow.day < first and flow.kind == SPENDING and flow.amount_cents < 0
    }


def insights_report(session: Session, month: date) -> InsightsReport:
    window = months_ending(month, _WINDOW_MONTHS)
    (start, _), (first, last) = window[0], window[-1]
    history = load_flows(session, date.min, last)
    history_parts = load_flows(session, date.min, last, parts=True)
    flows = [flow for flow in history if flow.day >= start]
    month_flows = [flow for flow in flows if flow.day >= first]
    earlier_flows = [flow for flow in flows if flow.day < first]
    part_flows = [flow for flow in history_parts if flow.day >= start]
    month_parts = [flow for flow in part_flows if flow.day >= first]
    earlier_parts = [flow for flow in part_flows if flow.day < first]
    series = recurring_charges(session, last)
    findings = [
        *spikes(first, month_parts, earlier_parts),
        *frequent_small(first, month_flows),
        *overlaps(first, series, _categories(history)),
        *price_increases(first, series),
        *charges_found(first, month_flows),
        *over_budget(first, budget_report(session, first, last)),
        *duplicates(first, month_flows),
        *large_first_charges(first, month_flows, earlier_flows, _seen_before(history, first)),
    ]
    ordered = order_findings(findings)
    open_ones, closed = split_findings(ordered, list_finding_statuses(session))
    return InsightsReport(
        month=first,
        findings=open_ones,
        merchants=merchant_stats(month_flows, earlier_flows),
        closed=closed,
    )


def find_finding(session: Session, month: date, type: str, subject: str) -> Finding:
    if type not in TYPES:
        raise ValueError("type must be one of: " + ", ".join(TYPES))
    report = insights_report(session, month)
    wanted = subject.strip().casefold()
    for finding in (*report.findings, *(item.finding for item in report.closed)):
        if finding.type == type and finding.subject.casefold() == wanted:
            return finding
    raise ValueError(f"no such finding: {finding_text(type, subject.strip(), month)}")
