# Phase 13d: unusual charges

## Goal

Two more findings in the Phase 13b engine, for a month M:

| Type | When | Severity | Saves a month |
|---|---|---|---|
| `duplicate` | a merchant charged the **same amount, on the same day, to the same account** more than once in M | `medium` when the repeats add to $20 or more, else `low` | the repeats (every charge of a group but one) |
| `large_first_charge` | a merchant with **no charge before M** whose largest charge in M is at least **$250** and at least **3 times** the average charge of its category in the three months before M (only the $250 rule when that category had no charge then, or is `Uncategorized`) | `medium` | nothing (`$0.00`): it asks for a look, not a saving |

They appear wherever findings do: `fin insights`, the Insights page (their merchant links to its transactions), and the dashboard's top findings.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-13b-findings-and-merchant-stats.md`; `src/finances/domain/insights.py`, `src/finances/analysis/insights.py`

## Starting state

N is `2829` when Phase 16k is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/insights.py` | `TYPES` gains two types; new `duplicates`, `large_first_charges` (R1 to R3) |
| `src/finances/analysis/insights.py` | the report includes them (R4) |
| `src/finances/web/templates/insights.html` | replaced: given (the two types link to their merchant's transactions) |
| `tests/unit/test_unusual_charges.py`, `tests/e2e/test_cli_unusual_charges.py` | new: given |
| `tests/unit/test_insights.py` | `test_the_types`: given change (below) |
| `tests/unit/test_unusual_charges_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Merging merchants that appear under two names (Phase 28); marking a duplicate as expected (Phase 19's statuses).
- Any change to the other six findings or their order among themselves.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/insights.py
TYPES = (
    "spike", "frequent_small", "subscription_overlap", "price_increase", "interest", "fees",
    "duplicate", "large_first_charge",
)


def duplicates(month: date, month_flows: Iterable[Flow]) -> list[Finding]: ...
def large_first_charges(
    month: date,
    month_flows: Iterable[Flow],
    earlier_flows: Iterable[Flow],
    seen: Collection[str],
) -> list[Finding]: ...
```

Detail texts, in full (amounts through `format_cents`, dates ISO):

| Type | Detail |
|---|---|
| `duplicate` | `MERCHANT: N charges of $X on DATE.`, and for each further group of that merchant `; N charges of $X on DATE`, before the final `.`, groups ordered by day, then by amount |
| `large_first_charge` | `MERCHANT: first seen this month, with a charge of $X on DATE.` |

## Requirements

A **charge** is a `SPENDING` flow below zero, as in Phase 13b; amounts below are positive.

- **R1.** The two types come last in `TYPES`, so `order_findings` puts them after the others of the same severity and savings.
- **R2.** `duplicates` groups M's charges by account, merchant, day, and amount; every group of two or more charges counts. It gives one finding per merchant (subject the merchant): savings the sum, over its groups, of (charges − 1) × amount; severity `medium` when that is 2000 or more, else `low`; detail as above. Findings ordered by subject ignoring case, then subject.
- **R3.** `large_first_charges` takes the merchants of M's charges that are not in `seen`. For each, its largest charge in M (the earliest day when two are equal) must be at least 25000 cents, and, when its category is not `Uncategorized` and `earlier_flows` hold charges in that category, at least 3 times their average (rounded half up). Each such merchant gives a finding: severity `medium`, savings 0, subject the merchant, detail as above. Ordered by subject ignoring case, then subject.
- **R4.** `insights_report` adds both to the findings it orders: `duplicates` of M's flows; `large_first_charges` of M's flows, the three earlier months' flows, and `seen`, the merchants of every charge **before M's first day** in all the data (the report already reads all flows up to M's end for its categories; use them).

## Given template

`src/finances/web/templates/insights.html`

```html
{% extends "layout.html" %}
{% block title %}Insights · Finances{% endblock %}
{% block content %}
<h1>Insights</h1>
{% include "messages.html" %}
<form method="get" action="/insights" class="fields">
  <label>Month <input type="month" name="month" value="{{ form.month }}"></label>
  <button type="submit">Show</button>
</form>
{% if report %}
<p class="summary">{{ report.heading }}</p>
<h2>Findings</h2>
{% if report.findings %}
<table>
<thead><tr><th>Severity</th><th>Type</th><th>About</th><th class="amount">Saves a month</th><th>Detail</th></tr></thead>
<tbody>
{% for row in report.findings %}<tr><td>{{ row.severity }}</td><td>{{ row.type }}</td><td>{% if row.type in ("spike", "subscription_overlap") %}<a href="/transactions?from={{ report.start }}&amp;to={{ report.end }}&amp;category={{ row.about|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.about }}</a>{% elif row.type in ("frequent_small", "price_increase", "duplicate", "large_first_charge") %}<a href="/transactions?from={{ report.start }}&amp;to={{ report.end }}&amp;merchant={{ row.about|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.about }}</a>{% else %}{{ row.about }}{% endif %}</td><td class="amount">{{ row.saves }}</td><td>{{ row.detail }}</td></tr>
{% endfor %}</tbody>
</table>
<p class="summary">{{ report.findings_summary }}</p>
{% else %}
<p class="empty">No findings.</p>
{% endif %}
<h2>Recurring charges</h2>
{% if report.recurring %}
<table>
<thead><tr><th>Merchant</th><th>Every</th><th class="amount">Amount</th><th class="amount">Monthly</th><th class="amount">Count</th><th>Last</th><th>Next</th></tr></thead>
<tbody>
{% for row in report.recurring %}<tr><td><a href="/transactions?merchant={{ row.merchant|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.merchant }}</a></td><td>{{ row.every }}</td><td class="amount">{{ row.amount }}</td><td class="amount">{{ row.monthly }}</td><td class="amount">{{ row.count }}</td><td>{{ row.last }}</td><td>{{ row.next }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No recurring charges.</p>
{% endif %}
<p class="summary">{{ report.recurring_summary }}</p>
<h2>Merchants</h2>
{% if report.merchants %}
<table>
<thead><tr><th>Merchant</th><th class="amount">Visits</th><th class="amount">Spent</th><th class="amount">Average</th><th class="amount">Baseline</th><th class="amount">Change</th><th class="amount">Weekend</th></tr></thead>
<tbody>
{% for row in report.merchants %}<tr><td><a href="/transactions?from={{ report.start }}&amp;to={{ report.end }}&amp;merchant={{ row.merchant|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.merchant }}</a></td><td class="amount">{{ row.visits }}</td><td class="amount">{{ row.spent }}</td><td class="amount">{{ row.average }}</td><td class="amount">{{ row.baseline }}</td><td class="amount">{{ row.change }}</td><td class="amount">{{ row.weekend }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No spending.</p>
{% endif %}
{% endif %}
{% endblock %}
```

## Given tests

6 tests in two files; `test_a_shop_seen_in_an_earlier_month_is_not_new` already passes and must keep passing. The end-to-end figures for the spike come from today's `fin insights`.

`tests/unit/test_unusual_charges.py`

```python
from datetime import date

from finances.domain.insights import TYPES, Finding, duplicates, large_first_charges
from finances.domain.spending import SPENDING, Flow

MAY = date(2026, 5, 1)


def flow(
    merchant: str,
    day: date,
    cents: int,
    category: str = "Dining",
    account: str = "Test Card",
) -> Flow:
    return Flow(
        amount_cents=cents,
        day=day,
        kind=SPENDING,
        category=category,
        group="Food",
        merchant=merchant,
        person="Unassigned",
        account=account,
        bank="Test Bank",
        card="No card",
    )


def test_the_two_new_types_come_last() -> None:
    assert TYPES[-2:] == ("duplicate", "large_first_charge")


def test_duplicates() -> None:
    month = [
        flow("ACME COFFEE", date(2026, 5, 3), -450),
        flow("ACME COFFEE", date(2026, 5, 3), -450),
        flow("ACME COFFEE", date(2026, 5, 4), -450),
        flow("ACME COFFEE", date(2026, 5, 10), -1200),
        flow("ACME COFFEE", date(2026, 5, 10), -1200),
        flow("ACME COFFEE", date(2026, 5, 10), -1200),
        flow("BAZ BOOKS", date(2026, 5, 5), -3000, account="Test Card"),
        flow("BAZ BOOKS", date(2026, 5, 5), -3000, account="Test Checking"),
        flow("QUUX DELI", date(2026, 5, 6), -500),
        flow("QUUX DELI", date(2026, 5, 6), 500),
        flow("FOOBAR", date(2026, 5, 7), -2500),
        flow("FOOBAR", date(2026, 5, 7), -2500),
        flow("baz cafe", date(2026, 5, 8), -300),
        flow("baz cafe", date(2026, 5, 8), -300),
    ]
    assert duplicates(MAY, month) == [
        Finding(
            "duplicate",
            "medium",
            MAY,
            "ACME COFFEE",
            2850,
            "ACME COFFEE: 2 charges of $4.50 on 2026-05-03; 3 charges of $12.00 on 2026-05-10.",
        ),
        Finding(
            "duplicate", "low", MAY, "baz cafe", 300, "baz cafe: 2 charges of $3.00 on 2026-05-08."
        ),
        Finding(
            "duplicate", "medium", MAY, "FOOBAR", 2500, "FOOBAR: 2 charges of $25.00 on 2026-05-07."
        ),
    ]
    assert duplicates(MAY, []) == []


def test_large_first_charges() -> None:
    earlier = [
        flow("BAZ TECH", date(2026, 3, 10), -10000, "Electronics"),
        flow("BAZ TECH", date(2026, 4, 10), -20000, "Electronics"),
        flow("OLD SHOP", date(2026, 4, 1), -100, "General Shopping"),
    ]
    month = [
        flow("NEW TV", date(2026, 5, 2), -1000, "Electronics"),
        flow("NEW TV", date(2026, 5, 8), -60000, "Electronics"),
        flow("NEW CAMERA", date(2026, 5, 9), -40000, "Electronics"),
        flow("NEW SOFA", date(2026, 5, 11), -30000, "Home & Garden"),
        flow("NEW SOFA", date(2026, 5, 20), -30000, "Home & Garden"),
        flow("NEW GYM", date(2026, 5, 12), -26000, "Uncategorized"),
        flow("SMALL NEW", date(2026, 5, 13), -24999, "Uncategorized"),
        flow("OLD SHOP", date(2026, 5, 14), -90000, "General Shopping"),
        flow("REFUND ONLY", date(2026, 5, 15), 50000, "Electronics"),
    ]
    seen = {"BAZ TECH", "OLD SHOP", "SOMEWHERE LONG AGO"}
    assert large_first_charges(MAY, month, earlier, seen) == [
        Finding(
            "large_first_charge",
            "medium",
            MAY,
            "NEW GYM",
            0,
            "NEW GYM: first seen this month, with a charge of $260.00 on 2026-05-12.",
        ),
        Finding(
            "large_first_charge",
            "medium",
            MAY,
            "NEW SOFA",
            0,
            "NEW SOFA: first seen this month, with a charge of $300.00 on 2026-05-11.",
        ),
        Finding(
            "large_first_charge",
            "medium",
            MAY,
            "NEW TV",
            0,
            "NEW TV: first seen this month, with a charge of $600.00 on 2026-05-08.",
        ),
    ]


def test_three_times_the_category_average_exactly() -> None:
    earlier = [flow("BAZ TECH", date(2026, 4, 10), -10000, "Electronics")]
    at = [flow("NEW TV", date(2026, 5, 8), -30000, "Electronics")]
    below = [flow("NEW TV", date(2026, 5, 8), -29999, "Electronics")]
    assert [item.subject for item in large_first_charges(MAY, at, earlier, set())] == ["NEW TV"]
    assert large_first_charges(MAY, below, earlier, set()) == []
```

`tests/e2e/test_cli_unusual_charges.py`

```python
from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from tests.support import plain_lines, run, table_rows

HEADINGS = ["Severity", "Type", "About", "Saves a month", "Detail"]


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    """December: a hotel. April: a coffee and a gadget. May: the same coffee twice on one
    day, a television from a shop never used before (five times April's gadget), and the hotel
    again, which is not new because it was used in December. June: the television shop again."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (day, cents, description) in enumerate(
            (
                (date(2025, 12, 1), -40000, "BIG HOTEL"),
                (date(2026, 4, 2), -450, "ACME COFFEE"),
                (date(2026, 4, 10), -10000, "BAZ TECH"),
                (date(2026, 5, 3), -450, "ACME COFFEE"),
                (date(2026, 5, 3), -450, "ACME COFFEE"),
                (date(2026, 5, 8), -50000, "QUUX TV"),
                (date(2026, 5, 9), -40000, "BIG HOTEL"),
                (date(2026, 6, 8), -50000, "QUUX TV"),
            ),
            start=1,
        ):
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
    for pattern, category in (("BAZ TECH", "Electronics"), ("QUUX TV", "Electronics")):
        assert run("rules", "add", "--pattern", pattern, "--category", category).exit_code == 0
    return tmp_settings


def test_duplicates_and_a_large_first_charge(money: Settings) -> None:
    result = run("insights", "--month", "2026-05")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        HEADINGS,
        [
            "high",
            "spike",
            "Electronics",
            "$466.67",
            "Electronics: $500.00 this month, against $33.33 a month before.",
        ],
        [
            "medium",
            "large_first_charge",
            "QUUX TV",
            "$0.00",
            "QUUX TV: first seen this month, with a charge of $500.00 on 2026-05-08.",
        ],
        [
            "low",
            "duplicate",
            "ACME COFFEE",
            "$4.50",
            "ACME COFFEE: 2 charges of $4.50 on 2026-05-03.",
        ],
    ]
    assert plain_lines(result.stdout) == [
        "Insights for 2026-05.",
        "Findings: 3. Could save up to $471.17 a month.",
    ]


def test_a_shop_seen_in_an_earlier_month_is_not_new(money: Settings) -> None:
    """June's television comes from a shop first seen in May: only the spike is left."""
    rows = table_rows(run("insights", "--month", "2026-06").stdout)
    assert rows[1:] == [
        [
            "high",
            "spike",
            "Electronics",
            "$300.00",
            "Electronics: $500.00 this month, against $200.00 a month before.",
        ]
    ]
```

The change to `tests/unit/test_insights.py`, exactly this diff:

```diff
diff --git a/tests/unit/test_insights.py b/tests/unit/test_insights.py
index 5b21e41..14cc91d 100644
--- a/tests/unit/test_insights.py
+++ b/tests/unit/test_insights.py
@@ -69,6 +69,8 @@ def test_the_types() -> None:
         "price_increase",
         "interest",
         "fees",
+        "duplicate",
+        "large_first_charge",
     )
 
 
```

## Tests to write

`tests/unit/test_unusual_charges_more.py`: repeats of exactly $20.00 (`medium`) and $19.99 (`low`); a category average that rounds half up; a merchant whose only May flows are refunds (no finding).

## Rules for this phase

- `domain/insights.py` keeps importing only the standard library and `finances.domain`; money stays integer cents.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_unusual_charges.py tests/e2e/test_cli_unusual_charges.py`, 6 tests;
- also `.venv/bin/python -m pytest tests/unit/test_insights.py tests/e2e/test_cli_insights.py tests/integration/test_web_insights.py tests/integration/test_web_search.py tests/integration/test_web_dashboard.py --no-cov`: all pass (no earlier data meets the new rules);
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.insights --cov=finances.analysis.insights --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the search: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` (no output).

## Report

As in `docs/phase-conventions.md`, headed `## Phase 13d: unusual charges (YYYY-MM-DD)`.
