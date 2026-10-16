"""A month's findings and merchant stats, against the three months before it."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from finances.analysis.budgets import budget_report
from finances.analysis.recurring import recurring_charges
from finances.analysis.spending import load_flows
from finances.domain.insights import (
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
    flows = [flow for flow in history if flow.day >= start]
    month_flows = [flow for flow in flows if flow.day >= first]
    earlier_flows = [flow for flow in flows if flow.day < first]
    series = recurring_charges(session, last)
    findings = [
        *spikes(first, month_flows, earlier_flows),
        *frequent_small(first, month_flows),
        *overlaps(first, series, _categories(history)),
        *price_increases(first, series),
        *charges_found(first, month_flows),
        *over_budget(first, budget_report(session, first, last)),
        *duplicates(first, month_flows),
        *large_first_charges(first, month_flows, earlier_flows, _seen_before(history, first)),
    ]
    return InsightsReport(
        month=first,
        findings=order_findings(findings),
        merchants=merchant_stats(month_flows, earlier_flows),
    )
