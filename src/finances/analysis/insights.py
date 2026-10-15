"""A month's findings and merchant stats, against the three months before it."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from finances.analysis.recurring import recurring_charges
from finances.analysis.spending import load_flows
from finances.domain.insights import (
    Finding,
    MerchantStat,
    charges_found,
    frequent_small,
    merchant_stats,
    order_findings,
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


def insights_report(session: Session, month: date) -> InsightsReport:
    window = months_ending(month, _WINDOW_MONTHS)
    (start, _), (first, last) = window[0], window[-1]
    flows = load_flows(session, start, last)
    month_flows = [flow for flow in flows if flow.day >= first]
    earlier_flows = [flow for flow in flows if flow.day < first]
    series = recurring_charges(session, last)
    findings = [
        *spikes(first, month_flows, earlier_flows),
        *frequent_small(first, month_flows),
        *overlaps(first, series, _categories(load_flows(session, date.min, last))),
        *price_increases(first, series),
        *charges_found(first, month_flows),
    ]
    return InsightsReport(
        month=first,
        findings=order_findings(findings),
        merchants=merchant_stats(month_flows, earlier_flows),
    )
