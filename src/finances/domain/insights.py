"""Findings worth a look in a month, and each merchant's month. Pure: no database.

A charge is a spending flow with money going out; a baseline is the three months before the
month, totalled and divided by 3. Every division of cents rounds half up.
"""

import re
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from finances.domain.budgets import BudgetLine
from finances.domain.money import format_cents
from finances.domain.recurring import Recurring, monthly_cost
from finances.domain.spending import SPENDING, UNCATEGORIZED, Flow, month_bounds

TYPES = (
    "spike",
    "frequent_small",
    "subscription_overlap",
    "price_increase",
    "interest",
    "fees",
    "over_budget",
    "duplicate",
    "large_first_charge",
)
SEVERITIES = ("high", "medium", "low")

_BASELINE_MONTHS = 3
_SPIKE_MIN_CENTS = 5000
_SPIKE_HIGH_CENTS = 20000
_SMALL_MIN_VISITS = 8
_SMALL_MAX_AVERAGE_CENTS = 1500
_SMALL_MEDIUM_CENTS = 10000
_DUPLICATE_MEDIUM_CENTS = 2000
_FIRST_CHARGE_MIN_CENTS = 25000
_FIRST_CHARGE_TIMES = 3
_WEEKEND = (5, 6)
_WORD = re.compile(r"[^\W_]+")
_INTEREST_WORDS = {"INTEREST"}
_FEE_WORDS = {"FEE", "FEES"}


@dataclass(frozen=True)
class Finding:
    type: str
    severity: str
    month: date
    subject: str
    savings_cents: int
    detail: str

    @property
    def key(self) -> str:
        return f"{self.type}:{self.subject}:{self.month.isoformat()[:7]}"


@dataclass(frozen=True)
class MerchantStat:
    merchant: str
    visits: int
    spent_cents: int
    average_cents: int
    baseline_cents: int
    change_cents: int
    weekend_visits: int


def _divide(cents: int, count: int) -> int:
    return (2 * cents + count) // (2 * count)


def _spending(flows: Iterable[Flow]) -> list[Flow]:
    return [flow for flow in flows if flow.kind == SPENDING]


def _charges(flows: Iterable[Flow]) -> list[Flow]:
    return [flow for flow in _spending(flows) if flow.amount_cents < 0]


def _by_subject(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda finding: (finding.subject.lower(), finding.subject))


def _spent_by(flows: Iterable[Flow], field: str) -> dict[str, int]:
    spent: defaultdict[str, int] = defaultdict(int)
    for flow in _spending(flows):
        spent[getattr(flow, field)] -= flow.amount_cents
    return spent


def merchant_stats(
    month_flows: Iterable[Flow], earlier_flows: Iterable[Flow]
) -> list[MerchantStat]:
    month = _spending(month_flows)
    spent = _spent_by(month, "merchant")
    earlier = _spent_by(earlier_flows, "merchant")
    charges: defaultdict[str, list[Flow]] = defaultdict(list)
    for flow in _charges(month):
        charges[flow.merchant].append(flow)
    stats = []
    for merchant, spent_cents in spent.items():
        visits = charges[merchant]
        total = -sum(flow.amount_cents for flow in visits)
        baseline = _divide(earlier.get(merchant, 0), _BASELINE_MONTHS)
        stats.append(
            MerchantStat(
                merchant=merchant,
                visits=len(visits),
                spent_cents=spent_cents,
                average_cents=_divide(total, len(visits)) if visits else 0,
                baseline_cents=baseline,
                change_cents=spent_cents - baseline,
                weekend_visits=sum(1 for flow in visits if flow.day.weekday() in _WEEKEND),
            )
        )
    return sorted(stats, key=lambda stat: (-stat.spent_cents, stat.merchant.lower(), stat.merchant))


def spikes(
    month: date, month_flows: Iterable[Flow], earlier_flows: Iterable[Flow]
) -> list[Finding]:
    earlier = _spent_by(earlier_flows, "category")
    found = []
    for category, spent in _spent_by(month_flows, "category").items():
        baseline = _divide(earlier.get(category, 0), _BASELINE_MONTHS)
        excess = spent - baseline
        if (
            category == UNCATEGORIZED
            or baseline <= 0
            or excess * 2 < baseline
            or excess < _SPIKE_MIN_CENTS
        ):
            continue
        found.append(
            Finding(
                type="spike",
                severity="high" if excess >= _SPIKE_HIGH_CENTS else "medium",
                month=month,
                subject=category,
                savings_cents=excess,
                detail=(
                    f"{category}: {format_cents(spent)} this month, "
                    f"against {format_cents(baseline)} a month before."
                ),
            )
        )
    return _by_subject(found)


def frequent_small(month: date, month_flows: Iterable[Flow]) -> list[Finding]:
    totals: defaultdict[str, int] = defaultdict(int)
    visits: defaultdict[str, int] = defaultdict(int)
    for flow in _charges(month_flows):
        totals[flow.merchant] -= flow.amount_cents
        visits[flow.merchant] += 1
    found = []
    for merchant, total in totals.items():
        average = _divide(total, visits[merchant])
        if visits[merchant] < _SMALL_MIN_VISITS or average > _SMALL_MAX_AVERAGE_CENTS:
            continue
        found.append(
            Finding(
                type="frequent_small",
                severity="medium" if total >= _SMALL_MEDIUM_CENTS else "low",
                month=month,
                subject=merchant,
                savings_cents=_divide(total, 2),
                detail=(
                    f"{merchant}: {visits[merchant]} visits averaging {format_cents(average)}."
                ),
            )
        )
    return _by_subject(found)


def charges_found(month: date, month_flows: Iterable[Flow]) -> list[Finding]:
    """Interest charged, then fees charged, each only when there was some."""
    interest = fees = 0
    for flow in _charges(month_flows):
        words = {word.upper() for word in _WORD.findall(flow.merchant)}
        if words & _INTEREST_WORDS:
            interest -= flow.amount_cents
        elif words & _FEE_WORDS:
            fees -= flow.amount_cents
    found = []
    if interest > 0:
        detail = f"Interest charged: {format_cents(interest)}."
        found.append(Finding("interest", "high", month, "", interest, detail))
    if fees > 0:
        found.append(
            Finding("fees", "medium", month, "", fees, f"Fees charged: {format_cents(fees)}.")
        )
    return found


def price_increases(month: date, series: Iterable[Recurring]) -> list[Finding]:
    first, last = month_bounds(month)
    found = []
    for item in series:
        previous = item.previous_cents
        if (
            not item.active
            or previous is None
            or item.amount_cents <= previous
            or not first <= item.last_day <= last
        ):
            continue
        found.append(
            Finding(
                type="price_increase",
                severity="medium",
                month=month,
                subject=item.merchant,
                savings_cents=monthly_cost(item.amount_cents - previous, item.cadence),
                detail=(
                    f"{item.merchant} went from {format_cents(previous)} "
                    f"to {format_cents(item.amount_cents)}."
                ),
            )
        )
    return _by_subject(found)


def overlaps(
    month: date, series: Iterable[Recurring], categories: Mapping[str, str]
) -> list[Finding]:
    groups: defaultdict[str, list[Recurring]] = defaultdict(list)
    for item in series:
        category = categories.get(item.merchant)
        if item.active and category is not None and category != UNCATEGORIZED:
            groups[category].append(item)
    found = []
    for category, items in groups.items():
        if len(items) < 2:
            continue
        named = ", ".join(f"{item.merchant} ({format_cents(item.monthly_cents)})" for item in items)
        found.append(
            Finding(
                type="subscription_overlap",
                severity="low",
                month=month,
                subject=category,
                savings_cents=min(item.monthly_cents for item in items),
                detail=f"{category}: {named}.",
            )
        )
    return _by_subject(found)


def over_budget(month: date, lines: Iterable[BudgetLine]) -> list[Finding]:
    """Each budget whose spent is more than its target."""
    found = []
    for line in lines:
        if line.spent_cents <= line.target_cents:
            continue
        excess = line.spent_cents - line.target_cents
        found.append(
            Finding(
                type="over_budget",
                severity="high" if line.spent_cents * 2 >= line.target_cents * 3 else "medium",
                month=month,
                subject=line.name,
                savings_cents=excess,
                detail=(
                    f"{line.name}: {format_cents(line.spent_cents)} spent against a budget of "
                    f"{format_cents(line.target_cents)}."
                ),
            )
        )
    return _by_subject(found)


def duplicates(month: date, month_flows: Iterable[Flow]) -> list[Finding]:
    """Same merchant, account, day, and amount more than once."""
    groups: defaultdict[tuple[str, str, date, int], int] = defaultdict(int)
    for flow in _charges(month_flows):
        groups[(flow.account, flow.merchant, flow.day, -flow.amount_cents)] += 1
    by_merchant: defaultdict[str, list[tuple[date, int, int]]] = defaultdict(list)
    for (_account, merchant, day, amount), count in groups.items():
        if count >= 2:
            by_merchant[merchant].append((day, amount, count))
    found = []
    for merchant, items in by_merchant.items():
        items.sort(key=lambda item: (item[0], item[1]))
        savings = sum((count - 1) * amount for _day, amount, count in items)
        parts = [
            f"{count} charges of {format_cents(amount)} on {day.isoformat()}"
            for day, amount, count in items
        ]
        detail = f"{merchant}: {parts[0]}"
        if len(parts) > 1:
            detail += "".join(f"; {part}" for part in parts[1:])
        detail += "."
        found.append(
            Finding(
                type="duplicate",
                severity="medium" if savings >= _DUPLICATE_MEDIUM_CENTS else "low",
                month=month,
                subject=merchant,
                savings_cents=savings,
                detail=detail,
            )
        )
    return _by_subject(found)


def large_first_charges(
    month: date,
    month_flows: Iterable[Flow],
    earlier_flows: Iterable[Flow],
    seen: Collection[str],
) -> list[Finding]:
    """A new merchant with a large first charge for its category."""
    by_merchant: defaultdict[str, list[Flow]] = defaultdict(list)
    for flow in _charges(month_flows):
        if flow.merchant not in seen:
            by_merchant[flow.merchant].append(flow)
    by_category: defaultdict[str, list[int]] = defaultdict(list)
    for flow in _charges(earlier_flows):
        by_category[flow.category].append(-flow.amount_cents)
    found = []
    for merchant, items in by_merchant.items():
        amount = max(-flow.amount_cents for flow in items)
        chosen = min(
            (flow for flow in items if -flow.amount_cents == amount),
            key=lambda flow: flow.day,
        )
        if amount < _FIRST_CHARGE_MIN_CENTS:
            continue
        category = chosen.category
        prior = by_category.get(category)
        if category != UNCATEGORIZED and prior:
            average = _divide(sum(prior), len(prior))
            if amount < _FIRST_CHARGE_TIMES * average:
                continue
        found.append(
            Finding(
                type="large_first_charge",
                severity="medium",
                month=month,
                subject=merchant,
                savings_cents=0,
                detail=(
                    f"{merchant}: first seen this month, with a charge of "
                    f"{format_cents(amount)} on {chosen.day.isoformat()}."
                ),
            )
        )
    return _by_subject(found)


def order_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Most serious first, then the largest savings."""
    return sorted(
        findings,
        key=lambda finding: (
            SEVERITIES.index(finding.severity),
            -finding.savings_cents,
            TYPES.index(finding.type),
            finding.subject.lower(),
            finding.subject,
        ),
    )
