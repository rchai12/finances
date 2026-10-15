# Phase 13b: findings and merchant stats

## Goal

The household is told, for a month, what deserves a look and roughly what it could save. After this phase:

- `fin insights --month YYYY-MM` lists **findings**, most serious first, each with a type, what it is about, an estimate of what it could save a month, and a one-line detail; then how many and the total estimate;
- `fin merchants --month YYYY-MM` lists each merchant of the month: visits, spent, average ticket, its average month over the three months before, the change, and how many visits fell on a weekend.

The six findings, all local and rule-based, for month M against the **three calendar months before it** (the baseline):

| Type | When | Severity | Saves a month |
|---|---|---|---|
| `spike` | a category's spending in M is above its baseline by at least half the baseline and at least $50; the baseline is above zero; never `Uncategorized` | `high` when the excess is $200 or more, else `medium` | the excess |
| `frequent_small` | a merchant with at least 8 visits in M averaging $15 or less | `medium` when M's charges add to $100 or more, else `low` | half of M's charges |
| `subscription_overlap` | two or more active recurring charges (Phase 13a, as of M's last day) whose merchants are in one category, never `Uncategorized` | `low` | the smallest monthly cost among them |
| `price_increase` | an active recurring charge whose last charge, in M, costs more than the one before it | `medium` | the rise, as a monthly cost |
| `interest` | charges in M whose merchant has the word `INTEREST` | `high` | their total |
| `fees` | other charges in M whose merchant has the word `FEE` or `FEES` | `medium` | their total |

"Spending" and "charges" mean Phase 12a's spending: no transfers, no income, nothing pending; a charge is money out. Estimates are rough by design, and the words say "up to". The web is 13c. Findings are not stored; Phase 19 will key its statuses on `Finding.key`.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-12a-spending.md` and `docs/phases/phase-13a-recurring-charges.md`
- `src/finances/domain/spending.py`, `src/finances/domain/recurring.py`, `src/finances/domain/periods.py`, `src/finances/analysis/spending.py`, `src/finances/analysis/recurring.py`, `src/finances/cli/reports.py`

## Starting state

N is `2490` when Phase 13a is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/recurring.py` | `Recurring` gains `previous_cents` (R1) |
| `src/finances/domain/insights.py` | new (R2 to R9) |
| `src/finances/analysis/insights.py` | new (R10) |
| `src/finances/views/insights.py` | new (R11) |
| `src/finances/cli/reports.py` | new: `insights_command`, `merchants_command` (R12, R13) |
| `src/finances/cli/main.py` | registers `insights` and `merchants` |
| `tests/unit/test_insights.py`, `tests/e2e/test_cli_insights.py` | new: given |
| `tests/integration/test_insights_report.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Storing findings, dismissing them, or alerts (Phase 19); the web (13c).
- Correcting baselines for months that are only partly covered; per-person findings; findings for income.
- Changing any other field or rule of Phase 13a.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/recurring.py: one field added, last, with a default
    previous_cents: int | None = None  # the charge before the last, as a positive cost, when it differs from the last
```

```python
# src/finances/domain/insights.py  (standard library and finances.domain only)
TYPES = ("spike", "frequent_small", "subscription_overlap", "price_increase", "interest", "fees")
SEVERITIES = ("high", "medium", "low")


@dataclass(frozen=True)
class Finding:
    type: str
    severity: str
    month: date          # the first day of M
    subject: str         # a category, a merchant, or "" for interest and fees
    savings_cents: int
    detail: str

    @property
    def key(self) -> str: ...  # "TYPE:SUBJECT:YYYY-MM"


@dataclass(frozen=True)
class MerchantStat:
    merchant: str
    visits: int
    spent_cents: int
    average_cents: int
    baseline_cents: int
    change_cents: int
    weekend_visits: int


def merchant_stats(month_flows: Iterable[Flow], earlier_flows: Iterable[Flow]) -> list[MerchantStat]: ...
def spikes(month: date, month_flows: Iterable[Flow], earlier_flows: Iterable[Flow]) -> list[Finding]: ...
def frequent_small(month: date, month_flows: Iterable[Flow]) -> list[Finding]: ...
def charges_found(month: date, month_flows: Iterable[Flow]) -> list[Finding]: ...
def price_increases(month: date, series: Iterable[Recurring]) -> list[Finding]: ...
def overlaps(month: date, series: Iterable[Recurring], categories: Mapping[str, str]) -> list[Finding]: ...
def order_findings(findings: Iterable[Finding]) -> list[Finding]: ...
```

```python
# src/finances/analysis/insights.py
@dataclass(frozen=True)
class InsightsReport:
    month: date
    findings: list[Finding]
    merchants: list[MerchantStat]


def insights_report(session: Session, month: date) -> InsightsReport: ...

# src/finances/views/insights.py
@dataclass(frozen=True)
class FindingRow:
    severity: str
    type: str
    about: str
    saves: str     # format_cents
    detail: str


@dataclass(frozen=True)
class MerchantRow:
    merchant: str
    visits: str
    spent: str
    average: str
    baseline: str
    change: str    # as Phase 12b's month change: "+" above zero, "$0.00" at zero
    weekend: str


def finding_rows(report: InsightsReport) -> list[FindingRow]: ...
def findings_summary(report: InsightsReport) -> str: ...
def merchant_rows(report: InsightsReport) -> list[MerchantRow]: ...
```

Detail texts, in full (amounts through `format_cents`):

| Type | Detail |
|---|---|
| `spike` | `CATEGORY: $SPENT this month, against $BASELINE a month before.` |
| `frequent_small` | `MERCHANT: N visits averaging $AVERAGE.` |
| `subscription_overlap` | `CATEGORY: MERCHANT ($MONTHLY), MERCHANT ($MONTHLY).` in the order the series were given |
| `price_increase` | `MERCHANT went from $PREVIOUS to $AMOUNT.` |
| `interest` | `Interest charged: $TOTAL.` |
| `fees` | `Fees charged: $TOTAL.` |

No new messages: a bad `--month` gives Phase 12a's `month must be a year and month, like 2026-05`.

## Requirements

### Part 1: the rules (pure)

Throughout, a **charge** is a `SPENDING` flow with an amount below zero, a **baseline** is a total of the earlier flows divided by 3 and rounded half up to whole cents, and every division of cents rounds half up.

- **R1.** `find_recurring` sets `previous_cents` to the negated amount of the series' second-to-last charge (in the order of Phase 13a's R3) when it differs from `amount_cents`, otherwise `None`. Nothing else in Phase 13a changes.
- **R2.** `Finding.key` is `TYPE:SUBJECT:YYYY-MM`.
- **R3.** `merchant_stats` gives one stat per merchant with a `SPENDING` flow in `month_flows`: `visits` its charges; `spent_cents` the negated sum of its `SPENDING` amounts (refunds reduce it); `average_cents` the charges' total over `visits`, as a positive amount (0 without visits); `baseline_cents` from its `SPENDING` amounts in `earlier_flows`, negated; `change_cents` spent minus baseline; `weekend_visits` its charges on a Saturday or Sunday. Ordered by spent, largest first, then by merchant ignoring case, then by merchant.
- **R4.** `spikes` works per category over `SPENDING` flows (spent as in Phase 12a, negated sums), with the rule and severity of the table: the excess is spent minus baseline; "at least half" means excess × 2 ≥ baseline. Ordered by subject ignoring case, then subject.
- **R5.** `frequent_small` works per merchant over charges, with the rule and severity of the table; the average is the charges' total (positive) over their number. Ordered by subject ignoring case, then subject.
- **R6.** `charges_found` splits each charge's merchant into words (runs of letters and digits): with `INTEREST` it counts toward `interest`; otherwise with `FEE` or `FEES` toward `fees`. It returns the `interest` finding, then the `fees` finding, each only when its total is above zero.
- **R7.** `price_increases` takes the active series with `previous_cents` set, `amount_cents` above it, and `last_day` within M; savings `monthly_cost(amount - previous, cadence)`. Ordered by subject ignoring case, then subject.
- **R8.** `overlaps` groups the active series by `categories[merchant]` (a merchant missing from the mapping, or mapped to `Uncategorized`, is left out); each group of two or more series gives one finding. Ordered by subject ignoring case, then subject.
- **R9.** `order_findings` orders by severity (`SEVERITIES` order), then savings largest first, then type (`TYPES` order), then subject ignoring case, then subject.

### Part 2: loading, views, and the terminal

- **R10.** `insights_report(session, month)` takes the first day of M; loads Phase 12a's flows once from the first day of the third month before M to M's last day (`months_ending(month, 4)`), and splits them into M's flows and the earlier ones; takes `recurring_charges(session, M's last day)`; maps each merchant to the category of its latest charge up to M's last day (by day, then the order loaded); and returns `order_findings` of all six findings with `merchant_stats`.
- **R11.** `finding_rows` formats each finding (`saves` through `format_cents`). `findings_summary` is `Findings: N. Could save up to $X a month.` with X the sum of the savings. `merchant_rows` formats each stat.
- **R12.** `fin insights` takes `--month` (text; the current month when not given, as `fin spending`), checks the schema, and prints `Insights for YYYY-MM.`; then a table with columns `Severity`, `Type`, `About`, `Saves a month`, `Detail` and the summary line, or `No findings.` alone.
- **R13.** `fin merchants` takes `--month` the same way and prints `Merchants for YYYY-MM.`; then a table with columns `Merchant`, `Visits`, `Spent`, `Average`, `Baseline`, `Change`, `Weekend`, or `No spending.`
- **R14.** Each command uses one session and holds no rule.

## Given tests

21 tests in two files. The unit tests build `Recurring` with `previous_cents`, which R1 adds.

`tests/unit/test_insights.py`

```python
from datetime import date

import pytest

from finances.domain.insights import (
    TYPES,
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
from finances.domain.recurring import Charge, Recurring, find_recurring
from finances.domain.spending import INCOME, SPENDING, Flow

MAY = date(2026, 5, 1)


def flow(
    merchant: str, day: date, cents: int, category: str = "Dining", kind: str = SPENDING
) -> Flow:
    return Flow(
        amount_cents=cents,
        day=day,
        kind=kind,
        category=category,
        group="Food",
        merchant=merchant,
        person="Unassigned",
        account="Test Card",
        bank="Test Bank",
        card="No card",
    )


def series(
    merchant: str,
    amount: int,
    monthly: int,
    last: date,
    *,
    previous: int | None = None,
    active: bool = True,
    cadence: str = "month",
) -> Recurring:
    return Recurring(
        merchant=merchant,
        cadence=cadence,
        amount_cents=amount,
        monthly_cents=monthly,
        count=3,
        first_day=date(2026, 1, 1),
        last_day=last,
        next_day=date(2026, 6, 1),
        active=active,
        previous_cents=previous,
    )


def test_the_types() -> None:
    assert TYPES == (
        "spike",
        "frequent_small",
        "subscription_overlap",
        "price_increase",
        "interest",
        "fees",
    )


def test_a_finding_has_a_key_for_its_kind_subject_and_month() -> None:
    finding = Finding("spike", "medium", MAY, "Dining", 18000, "detail")
    assert finding.key == "spike:Dining:2026-05"


def test_recurring_remembers_a_changed_price() -> None:
    gym = [
        Charge("ACME GYM", date(2026, 1, 10), -3000),
        Charge("ACME GYM", date(2026, 2, 10), -3000),
        Charge("ACME GYM", date(2026, 3, 10), -3500),
    ]
    steady = [
        Charge("QUUX", day, -999) for day in (date(2026, 1, 3), date(2026, 2, 3), date(2026, 3, 3))
    ]
    found = find_recurring(gym + steady, date(2026, 3, 20))
    assert [(item.merchant, item.previous_cents) for item in found] == [
        ("ACME GYM", 3000),
        ("QUUX", None),
    ]


def test_merchant_stats() -> None:
    month = [
        flow("ACME COFFEE", date(2026, 5, 2), -500),
        flow("ACME COFFEE", date(2026, 5, 3), -450),
        flow("ACME COFFEE", date(2026, 5, 6), -550),
        flow("ACME COFFEE", date(2026, 5, 7), 100),
        flow("FOOBAR GROCERY", date(2026, 5, 4), -8000),
        flow("PAYCHECK EXAMPLE CORP", date(2026, 5, 15), 300000, "Paycheck", INCOME),
    ]
    earlier = [
        flow("ACME COFFEE", date(2026, 3, 1), -1000),
        flow("ACME COFFEE", date(2026, 4, 1), -2000),
        flow("FOOBAR GROCERY", date(2026, 3, 9), -9000),
        flow("BAZ BOOKS", date(2026, 2, 9), -700),
    ]
    assert merchant_stats(month, earlier) == [
        MerchantStat("FOOBAR GROCERY", 1, 8000, 8000, 3000, 5000, 0),
        MerchantStat("ACME COFFEE", 3, 1400, 500, 1000, 400, 2),
    ]


def test_spikes() -> None:
    month = [
        flow("ACME DINER", date(2026, 5, 9), -30000, "Dining"),
        flow("FOOBAR GROCERY", date(2026, 5, 9), -20000, "Groceries"),
        flow("QUUX AIR", date(2026, 5, 9), -50000, "Flights"),
        flow("BAZ GIFTS", date(2026, 5, 9), -8000, "Gifts & Donations"),
        flow("BAZ SHOES", date(2026, 5, 9), -15000, "Clothing"),
        flow("BAZ TECH", date(2026, 5, 9), -14999, "Electronics"),
        flow("UNKNOWN SHOP", date(2026, 5, 9), -90000, "Uncategorized"),
    ]
    earlier = [
        flow("ACME DINER", date(2026, 3, 9), -36000, "Dining"),
        flow("FOOBAR GROCERY", date(2026, 3, 9), -54000, "Groceries"),
        flow("QUUX AIR", date(2026, 3, 9), -15000, "Flights"),
        flow("BAZ SHOES", date(2026, 3, 9), -30000, "Clothing"),
        flow("BAZ TECH", date(2026, 3, 9), -30000, "Electronics"),
        flow("UNKNOWN SHOP", date(2026, 3, 9), -3000, "Uncategorized"),
    ]
    assert spikes(MAY, month, earlier) == [
        Finding(
            "spike",
            "medium",
            MAY,
            "Clothing",
            5000,
            "Clothing: $150.00 this month, against $100.00 a month before.",
        ),
        Finding(
            "spike",
            "medium",
            MAY,
            "Dining",
            18000,
            "Dining: $300.00 this month, against $120.00 a month before.",
        ),
        Finding(
            "spike",
            "high",
            MAY,
            "Flights",
            45000,
            "Flights: $500.00 this month, against $50.00 a month before.",
        ),
    ]


def test_frequent_small_purchases() -> None:
    month = (
        [flow("ACME COFFEE", date(2026, 5, day), -500) for day in range(1, 9)]
        + [flow("BAZ SNACKS", date(2026, 5, day), -300) for day in range(1, 8)]
        + [flow("QUUX DELI", date(2026, 5, day), -1600) for day in range(1, 11)]
        + [flow("FOOBAR BAR", date(2026, 5, day), -1500) for day in range(1, 21)]
        + [flow("BAZ CAFE", date(2026, 5, day), -333) for day in range(1, 10)]
    )
    assert frequent_small(MAY, month) == [
        Finding(
            "frequent_small",
            "low",
            MAY,
            "ACME COFFEE",
            2000,
            "ACME COFFEE: 8 visits averaging $5.00.",
        ),
        Finding(
            "frequent_small", "low", MAY, "BAZ CAFE", 1499, "BAZ CAFE: 9 visits averaging $3.33."
        ),
        Finding(
            "frequent_small",
            "medium",
            MAY,
            "FOOBAR BAR",
            15000,
            "FOOBAR BAR: 20 visits averaging $15.00.",
        ),
    ]


def test_interest_and_fees() -> None:
    month = [
        flow("PURCHASE INTEREST CHARGE", date(2026, 5, 28), -2345, "Uncategorized"),
        flow("INTEREST CHARGE ON PURCHASES", date(2026, 5, 28), -100, "Fees & Interest"),
        flow("LATE FEE", date(2026, 5, 20), -3500, "Fees & Interest"),
        flow("ANNUAL MEMBERSHIP FEE", date(2026, 5, 2), -9500, "Uncategorized"),
        flow("COFFEE FEED STORE", date(2026, 5, 2), -700),
        flow("INTEREST PAID", date(2026, 5, 31), 50, "Interest Income", INCOME),
    ]
    assert charges_found(MAY, month) == [
        Finding("interest", "high", MAY, "", 2445, "Interest charged: $24.45."),
        Finding("fees", "medium", MAY, "", 13000, "Fees charged: $130.00."),
    ]
    assert charges_found(MAY, [flow("LATE FEE", date(2026, 5, 20), -3500)]) == [
        Finding("fees", "medium", MAY, "", 3500, "Fees charged: $35.00.")
    ]


def test_price_increases() -> None:
    found = price_increases(
        MAY,
        [
            series("QUUX STREAMING", 1799, 1799, date(2026, 5, 5), previous=1599),
            series("BAZ VIDEO", 1799, 1799, date(2026, 5, 6), previous=1999),
            series("ACME GYM", 3500, 3500, date(2026, 4, 30), previous=3000),
            series("OLD TV", 1200, 1200, date(2026, 5, 2), previous=1000, active=False),
            series("QUUX CLOUD", 10900, 908, date(2026, 5, 3), previous=9900, cadence="year"),
            series("FOOBAR APPS", 299, 299, date(2026, 5, 3)),
        ],
    )
    assert found == [
        Finding(
            "price_increase",
            "medium",
            MAY,
            "QUUX CLOUD",
            83,
            "QUUX CLOUD went from $99.00 to $109.00.",
        ),
        Finding(
            "price_increase",
            "medium",
            MAY,
            "QUUX STREAMING",
            200,
            "QUUX STREAMING went from $15.99 to $17.99.",
        ),
    ]


def test_overlapping_subscriptions() -> None:
    found = overlaps(
        MAY,
        [
            series("QUUX STREAMING", 1799, 1799, date(2026, 5, 5)),
            series("ACME GYM", 3000, 3000, date(2026, 5, 5)),
            series("BAZ VIDEO", 999, 999, date(2026, 5, 12)),
            series("FOOBAR APPS", 299, 299, date(2026, 5, 3)),
            series("FOOBAR APPS", 999, 999, date(2026, 5, 20)),
            series("OLD TV", 1200, 1200, date(2026, 3, 2), active=False),
        ],
        {
            "QUUX STREAMING": "Subscriptions & Digital",
            "ACME GYM": "Fitness",
            "BAZ VIDEO": "Subscriptions & Digital",
            "FOOBAR APPS": "Uncategorized",
            "OLD TV": "Subscriptions & Digital",
        },
    )
    assert found == [
        Finding(
            "subscription_overlap",
            "low",
            MAY,
            "Subscriptions & Digital",
            999,
            "Subscriptions & Digital: QUUX STREAMING ($17.99), BAZ VIDEO ($9.99).",
        )
    ]


def test_order_findings() -> None:
    low = Finding("subscription_overlap", "low", MAY, "Subscriptions & Digital", 999, "")
    small = Finding("frequent_small", "low", MAY, "ACME COFFEE", 999, "")
    small_b = Finding("frequent_small", "low", MAY, "baz cafe", 999, "")
    medium = Finding("price_increase", "medium", MAY, "QUUX", 200, "")
    spike = Finding("spike", "medium", MAY, "Dining", 14000, "")
    high = Finding("interest", "high", MAY, "", 1, "")
    assert order_findings([low, small_b, medium, small, high, spike]) == [
        high,
        spike,
        medium,
        small,
        small_b,
        low,
    ]


@pytest.mark.parametrize("flows", [[], [flow("ACME", MAY, 500)]])
def test_nothing_to_find(flows: list[Flow]) -> None:
    assert spikes(MAY, flows, []) == []
    assert frequent_small(MAY, flows) == []
    assert charges_found(MAY, flows) == []
    assert price_increases(MAY, []) == []
    assert overlaps(MAY, [], {}) == []
```

`tests/e2e/test_cli_insights.py`

```python
from datetime import date

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account

runner = CliRunner(env={"COLUMNS": "250"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
MAY = ("--month", "2026-05")


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def plain_lines(output: str) -> list[str]:
    tables = ("│", "┃", "┏", "┡", "└")
    return [line for line in output.splitlines() if line and not line.startswith(tables)]


def failed_cleanly(result, message: str) -> bool:
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    return tmp_settings


@pytest.fixture
def money(migrated: Settings) -> Settings:
    """February to May 2026 on one card: dining that jumps in May, a streaming price rise, a
    second video subscription, coffee eight times in May, and an interest charge."""
    rows = [
        (date(2026, 2, 3), -6000, "ACME DINER"),
        (date(2026, 3, 17), -6000, "ACME DINER"),
        (date(2026, 4, 9), -6000, "ACME DINER"),
        (date(2026, 5, 22), -20000, "ACME DINER"),
        (date(2026, 2, 5), -1599, "QUUX STREAMING"),
        (date(2026, 3, 5), -1599, "QUUX STREAMING"),
        (date(2026, 4, 5), -1599, "QUUX STREAMING"),
        (date(2026, 5, 5), -1799, "QUUX STREAMING"),
        (date(2026, 3, 12), -999, "BAZ VIDEO"),
        (date(2026, 4, 12), -999, "BAZ VIDEO"),
        (date(2026, 5, 12), -999, "BAZ VIDEO"),
        (date(2026, 5, 28), -2345, "PURCHASE INTEREST CHARGE"),
    ] + [(date(2026, 5, day), -500, "ACME COFFEE") for day in (2, 3, 6, 9, 10, 13, 16, 17)]
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
        for number, (day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    for pattern, category in (
        ("ACME DINER", "Dining"),
        ("QUUX STREAMING", "Subscriptions & Digital"),
        ("BAZ VIDEO", "Subscriptions & Digital"),
        ("ACME COFFEE", "Coffee & Dessert"),
    ):
        assert run("rules", "add", "--pattern", pattern, "--category", category).exit_code == 0
    return migrated


@pytest.mark.parametrize("args", [("insights",), ("insights", *MAY), ("merchants", *MAY)])
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


def test_no_findings(migrated: Settings) -> None:
    result = run("insights", *MAY)
    assert (result.exit_code, result.stdout) == (
        0,
        "Insights for 2026-05.\nNo findings.\n",
    )
    assert run("merchants", *MAY).stdout == "Merchants for 2026-05.\nNo spending.\n"


def test_the_findings_of_a_month(money: Settings) -> None:
    result = run("insights", *MAY)
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        ["Severity", "Type", "About", "Saves a month", "Detail"],
        ["high", "interest", "", "$23.45", "Interest charged: $23.45."],
        [
            "medium",
            "spike",
            "Dining",
            "$140.00",
            "Dining: $200.00 this month, against $60.00 a month before.",
        ],
        [
            "medium",
            "price_increase",
            "QUUX STREAMING",
            "$2.00",
            "QUUX STREAMING went from $15.99 to $17.99.",
        ],
        [
            "low",
            "frequent_small",
            "ACME COFFEE",
            "$20.00",
            "ACME COFFEE: 8 visits averaging $5.00.",
        ],
        [
            "low",
            "subscription_overlap",
            "Subscriptions & Digital",
            "$9.99",
            "Subscriptions & Digital: QUUX STREAMING ($17.99), BAZ VIDEO ($9.99).",
        ],
    ]
    assert plain_lines(result.stdout) == [
        "Insights for 2026-05.",
        "Findings: 5. Could save up to $195.44 a month.",
    ]


def test_the_merchants_of_a_month(money: Settings) -> None:
    result = run("merchants", *MAY)
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        ["Merchant", "Visits", "Spent", "Average", "Baseline", "Change", "Weekend"],
        ["ACME DINER", "1", "$200.00", "$200.00", "$60.00", "+$140.00", "0"],
        ["ACME COFFEE", "8", "$40.00", "$5.00", "$0.00", "+$40.00", "6"],
        ["PURCHASE INTEREST CHARGE", "1", "$23.45", "$23.45", "$0.00", "+$23.45", "0"],
        ["QUUX STREAMING", "1", "$17.99", "$17.99", "$15.99", "+$2.00", "0"],
        ["BAZ VIDEO", "1", "$9.99", "$9.99", "$6.66", "+$3.33", "0"],
    ]
    assert plain_lines(result.stdout) == ["Merchants for 2026-05."]


def test_an_earlier_month(money: Settings) -> None:
    result = run("insights", "--month", "2026-04")
    assert table_rows(result.stdout) == []
    assert plain_lines(result.stdout) == ["Insights for 2026-04.", "No findings."]
    rows = table_rows(run("merchants", "--month", "2026-04").stdout)
    assert rows[1:] == [
        ["ACME DINER", "1", "$60.00", "$60.00", "$40.00", "+$20.00", "0"],
        ["QUUX STREAMING", "1", "$15.99", "$15.99", "$10.66", "+$5.33", "1"],
        ["BAZ VIDEO", "1", "$9.99", "$9.99", "$3.33", "+$6.66", "1"],
    ]


@pytest.mark.parametrize("command", ["insights", "merchants"])
def test_a_month_that_is_not_one(money: Settings, command: str) -> None:
    result = run(command, "--month", "2026-13")
    assert failed_cleanly(result, "month must be a year and month, like 2026-05")
```

## Tests to write

`tests/integration/test_insights_report.py`:

- `insights_report` reads flows from exactly the three months before M (a charge on the day before that window does not count);
- the category of a merchant whose category changed is the latest one;
- `merchant_stats` for a merchant with only a refund in M (0 visits, average 0, negative spent);
- the spike threshold exactly at half the baseline and exactly at $50, and just below each;
- `frequent_small` ignores refunds (they are neither visits nor part of the average);
- `fin insights` and `fin merchants` without `--month` use the current month.

Phase 13a's given tests must still pass unchanged.

## Rules for this phase

- `domain/insights.py` imports only the standard library and `finances.domain`; money stays integer cents, and no `float` appears.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_insights.py tests/e2e/test_cli_insights.py`, 21 tests;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.insights --cov=finances.domain.recurring --cov=finances.analysis.insights --cov=finances.views.insights --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)|float" -- src/finances/domain/insights.py src/finances/domain/recurring.py` and `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|sorted\(|timedelta|spikes\(|merchant_stats\(" -- src/finances/cli/reports.py`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 13b: findings and merchant stats (YYYY-MM-DD)`.
