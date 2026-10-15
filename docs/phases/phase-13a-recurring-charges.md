# Phase 13a: recurring charges

## Goal

The household sees what it pays for again and again. After this phase `fin recurring` lists each subscription or other regular charge: the merchant, how often (every week, month, quarter, or year), the latest amount, what it costs a month, how many charges were seen, the last one, when the next is expected, and whether it is still active; then how many are active and what they cost a month together.

How a charge is recognised, all local and rule-based:

- Only **spending** counts (Phase 12a: no transfers, no income, nothing pending), and only money out; refunds are not charges.
- A merchant's charges form a **series** when the days between one charge and the next all fall in one band: 6 to 8 days (week), 27 to 33 (month), 85 to 97 (quarter), or 350 to 380 (year); with at least 3 charges, or 2 for a year.
- The price may change within a series; the latest amount is shown.
- When a merchant's charges together are not a series (an app store billing several subscriptions, each on its own day), each **amount** of that merchant is tried on its own, so each subscription is found.
- A series is **active** until the latest day its next charge could come (the last charge plus the band's top).

Merchant stats and the findings list are Phase 13b; the web is 13c.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-12a-spending.md` and `src/finances/analysis/spending.py` (`load_flows`, `Flow`, the kinds)
- `src/finances/cli/reports.py`: the commands this one sits beside

## Starting state

N is `2449` when Phase 12c is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/recurring.py` | new (R1 to R4) |
| `src/finances/analysis/recurring.py` | new (R5) |
| `src/finances/views/recurring.py` | new (R6) |
| `src/finances/cli/reports.py` | new: `recurring_command` (R7) |
| `src/finances/cli/main.py` | registers `recurring` |
| `tests/unit/test_recurring.py`, `tests/e2e/test_cli_recurring.py` | new: given |
| `tests/integration/test_recurring_report.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Allowing a missed charge inside a series, every-two-weeks or every-six-months bands, or fuzzy merchant matching (two names for one merchant).
- Storing what was found, marking a charge "not a subscription", or alerts; findings (13b); the web (13c).

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/recurring.py  (standard library and finances.domain only)
CADENCES = ("week", "month", "quarter", "year")


@dataclass(frozen=True)
class Charge:
    merchant: str
    day: date
    amount_cents: int  # as stored: money out is below zero


@dataclass(frozen=True)
class Recurring:
    merchant: str
    cadence: str        # one of CADENCES
    amount_cents: int   # the latest charge, as a positive cost
    monthly_cents: int
    count: int
    first_day: date
    last_day: date
    next_day: date
    active: bool


def find_recurring(charges: Iterable[Charge], as_of: date) -> list[Recurring]: ...
def monthly_cost(amount_cents: int, cadence: str) -> int: ...
def next_charge(day: date, cadence: str) -> date: ...
```

| Cadence | Days between charges | Fewest charges | Next charge | Monthly cost |
|---|---|---|---|---|
| `week` | 6 to 8 | 3 | 7 days later | amount × 52 / 12 |
| `month` | 27 to 33 | 3 | 1 calendar month later | amount |
| `quarter` | 85 to 97 | 3 | 3 calendar months later | amount / 3 |
| `year` | 350 to 380 | 2 | 12 calendar months later | amount / 12 |

```python
# src/finances/analysis/recurring.py
def recurring_charges(session: Session, as_of: date) -> list[Recurring]: ...

# src/finances/views/recurring.py
@dataclass(frozen=True)
class RecurringRow:
    merchant: str
    every: str     # the cadence
    amount: str    # format_cents
    monthly: str   # format_cents
    count: str
    last: str      # ISO date
    next: str      # ISO date
    active: str    # "yes" or "no"


def recurring_rows(items: list[Recurring], *, include_inactive: bool = False) -> list[RecurringRow]: ...
def recurring_summary(items: list[Recurring]) -> str: ...
```

No new messages: a bad `--as-of` is refused by Typer's own date check (exit code 2), as `fin transactions list --from` is.

## Requirements

### Part 1: the rules (pure)

- **R1.** `monthly_cost` multiplies by the table's factor exactly (no floats), then rounds half up to whole cents.
- **R2.** `next_charge` adds the table's step; a calendar step keeps the day of the month, or the month's last day when the month is shorter.
- **R3.** `find_recurring` ignores charges at or above zero, groups the rest by merchant, and orders each merchant's charges by day, then amount. A list of charges is a **series** of a cadence when every gap between consecutive days falls in that cadence's band and there are at least its fewest charges. If a merchant's charges together are a series, they give one `Recurring`; otherwise the merchant's charges are split by exact amount and each split that is a series gives one.
- **R4.** Each `Recurring` has: `amount_cents` the negated amount of the series' last charge; `monthly_cents` from `monthly_cost`; `count`, `first_day`, `last_day` of the series; `next_day` from `next_charge(last_day, cadence)`; `active` when `as_of` is on or before `last_day` plus the band's top. The list comes active first, then the largest `monthly_cents`, then by merchant ignoring case, then by merchant, then the largest `amount_cents`.

### Part 2: loading and the terminal

- **R5.** `recurring_charges` loads Phase 12a's flows from the earliest date (`date.min`) to `as_of`, keeps the `SPENDING` flows, makes a `Charge` of each (`merchant`, `day`, `amount_cents`), and returns `find_recurring` of them.
- **R6.** `recurring_rows` formats each item (inactive ones only when asked). `recurring_summary` is `Recurring: N active, $X a month.`, N the active items and X the sum of their `monthly_cents` through `format_cents`.
- **R7.** `fin recurring` takes `--as-of` (`YYYY-MM-DD`, read as `fin transactions list` reads `--from`; today when not given) and `--all`. It checks the schema, then prints a table with columns `Merchant`, `Every`, `Amount`, `Monthly`, `Count`, `Last`, `Next`, `Active` (inactive rows only with `--all`), or `No recurring charges.` when it has no rows; then the summary line, always. One session; no rule in the command.

## Given tests

33 tests in two files.

`tests/unit/test_recurring.py`

```python
from datetime import date

import pytest

from finances.domain.recurring import (
    CADENCES,
    Charge,
    Recurring,
    find_recurring,
    monthly_cost,
    next_charge,
)

AS_OF = date(2026, 5, 1)


def charges(merchant: str, cents: int, *days: date) -> list[Charge]:
    return [Charge(merchant, day, cents) for day in days]


def test_the_cadences() -> None:
    assert CADENCES == ("week", "month", "quarter", "year")


def test_a_monthly_subscription() -> None:
    found = find_recurring(
        charges(
            "QUUX STREAMING",
            -1599,
            date(2026, 1, 5),
            date(2026, 2, 5),
            date(2026, 3, 5),
            date(2026, 4, 5),
        ),
        AS_OF,
    )
    assert found == [
        Recurring(
            merchant="QUUX STREAMING",
            cadence="month",
            amount_cents=1599,
            monthly_cents=1599,
            count=4,
            first_day=date(2026, 1, 5),
            last_day=date(2026, 4, 5),
            next_day=date(2026, 5, 5),
            active=True,
        )
    ]


def test_a_price_rise_keeps_one_series_at_the_latest_amount() -> None:
    found = find_recurring(
        charges("ACME GYM", -3000, date(2026, 1, 10), date(2026, 2, 10))
        + charges("ACME GYM", -3500, date(2026, 3, 10)),
        AS_OF,
    )
    assert [(item.merchant, item.amount_cents, item.count) for item in found] == [
        ("ACME GYM", 3500, 3)
    ]


def test_one_merchant_billing_several_subscriptions() -> None:
    found = find_recurring(
        charges("FOOBAR APPS", -299, date(2026, 1, 3), date(2026, 2, 3), date(2026, 3, 3))
        + charges("FOOBAR APPS", -999, date(2026, 1, 20), date(2026, 2, 20), date(2026, 3, 20)),
        AS_OF,
    )
    assert [(item.merchant, item.cadence, item.amount_cents) for item in found] == [
        ("FOOBAR APPS", "month", 999),
        ("FOOBAR APPS", "month", 299),
    ]


def test_each_cadence_and_its_monthly_cost() -> None:
    found = find_recurring(
        charges(
            "BAZ BOX",
            -1200,
            date(2026, 4, 3),
            date(2026, 4, 10),
            date(2026, 4, 17),
            date(2026, 4, 24),
        )
        + charges("QUUX INSURANCE", -4500, date(2025, 10, 15), date(2026, 1, 15), date(2026, 4, 15))
        + charges("QUUX CLOUD", -9900, date(2025, 3, 1), date(2026, 3, 1)),
        AS_OF,
    )
    assert [(item.merchant, item.cadence, item.monthly_cents, item.next_day) for item in found] == [
        ("BAZ BOX", "week", 5200, date(2026, 5, 1)),
        ("QUUX INSURANCE", "quarter", 1500, date(2026, 7, 15)),
        ("QUUX CLOUD", "year", 825, date(2027, 3, 1)),
    ]


@pytest.mark.parametrize(
    "items",
    [
        charges("ACME COFFEE", -450, date(2026, 1, 2), date(2026, 1, 9), date(2026, 1, 30)),
        charges("ACME COFFEE", -450, date(2026, 2, 5), date(2026, 3, 5)),
        charges("ACME COFFEE", -450, date(2026, 1, 5), date(2026, 1, 5), date(2026, 2, 5)),
        charges("ACME COFFEE", -450, date(2026, 1, 5), date(2026, 3, 5), date(2026, 4, 5)),
        charges("ACME COFFEE", -450, date(2025, 3, 1)),
        [],
    ],
    ids=["irregular", "two-months", "same-day", "a-missed-month", "one-year-charge", "none"],
)
def test_not_recurring(items: list[Charge]) -> None:
    assert find_recurring(items, AS_OF) == []


@pytest.mark.parametrize(("as_of", "active"), [(date(2026, 5, 8), True), (date(2026, 5, 9), False)])
def test_active_until_the_latest_a_next_charge_could_come(as_of: date, active: bool) -> None:
    found = find_recurring(
        charges("QUUX STREAMING", -1599, date(2026, 2, 5), date(2026, 3, 5), date(2026, 4, 5)),
        as_of,
    )
    assert [item.active for item in found] == [active]


def test_the_largest_monthly_cost_comes_first_then_the_name() -> None:
    found = find_recurring(
        charges("beta", -500, date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5))
        + charges("Alpha", -500, date(2026, 1, 6), date(2026, 2, 6), date(2026, 3, 6))
        + charges("Gamma", -800, date(2026, 1, 7), date(2026, 2, 7), date(2026, 3, 7)),
        AS_OF,
    )
    assert [item.merchant for item in found] == ["Gamma", "Alpha", "beta"]


@pytest.mark.parametrize(
    ("cents", "cadence", "monthly"),
    [
        (1000, "week", 4333),
        (1001, "week", 4338),
        (1000, "month", 1000),
        (1000, "quarter", 333),
        (1001, "quarter", 334),
        (1000, "year", 83),
        (1002, "year", 84),
    ],
)
def test_monthly_cost_rounds_half_up(cents: int, cadence: str, monthly: int) -> None:
    assert monthly_cost(cents, cadence) == monthly


@pytest.mark.parametrize(
    ("day", "cadence", "after"),
    [
        (date(2026, 1, 31), "week", date(2026, 2, 7)),
        (date(2026, 1, 31), "month", date(2026, 2, 28)),
        (date(2026, 11, 30), "quarter", date(2027, 2, 28)),
        (date(2024, 2, 29), "year", date(2025, 2, 28)),
    ],
)
def test_next_charge_keeps_the_day_of_the_month_where_it_can(
    day: date, cadence: str, after: date
) -> None:
    assert next_charge(day, cadence) == after
```

`tests/e2e/test_cli_recurring.py`

```python
from datetime import date

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
HEADINGS = ["Merchant", "Every", "Amount", "Monthly", "Count", "Last", "Next", "Active"]
STREAMING = ["QUUX STREAMING", "month", "$15.99", "$15.99", "4", "2026-04-05", "2026-05-05", "yes"]
APPS_999 = ["FOOBAR APPS", "month", "$9.99", "$9.99", "4", "2026-04-20", "2026-05-20", "yes"]
APPS_299 = ["FOOBAR APPS", "month", "$2.99", "$2.99", "4", "2026-04-03", "2026-05-03", "yes"]
OLD_GYM = ["OLD GYM", "month", "$25.00", "$25.00", "3", "2025-12-01", "2026-01-01", "no"]


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def plain_lines(output: str) -> list[str]:
    tables = ("│", "┃", "┏", "┡", "└")
    return [line for line in output.splitlines() if line and not line.startswith(tables)]


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    return tmp_settings


@pytest.fixture
def money(migrated: Settings) -> Settings:
    """Three subscriptions on the card, one that stopped, coffee at no set rhythm, and a monthly
    card payment from checking that is a transfer, not a subscription."""
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
        rows = []
        for month in (1, 2, 3, 4):
            rows.append((card, date(2026, month, 5), -1599, "QUUX STREAMING"))
            rows.append((card, date(2026, month, 3), -299, "FOOBAR APPS"))
            rows.append((card, date(2026, month, 20), -999, "FOOBAR APPS"))
        for month in (1, 2, 3):
            rows.append((checking, date(2026, month, 20), -50000, "PAYMENT TO TEST CARD"))
            rows.append((card, date(2026, month, 21), 50000, "PAYMENT THANK YOU"))
        for year, month in ((2025, 10), (2025, 11), (2025, 12)):
            rows.append((card, date(year, month, 1), -2500, "OLD GYM"))
        for day in (2, 9, 30):
            rows.append((card, date(2026, 1, day), -450, "ACME COFFEE"))
        for number, (account, day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    assert run("transfers", "find").stdout == "Transfers: 3 paired, 0 waiting for review.\n"
    return migrated


@pytest.mark.parametrize("args", [(), ("--all",), ("--as-of", "2026-05-01")])
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run("recurring", *args)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


def test_nothing_recurring(migrated: Settings) -> None:
    result = run("recurring", "--as-of", "2026-05-01")
    assert (result.exit_code, result.stdout) == (
        0,
        "No recurring charges.\nRecurring: 0 active, $0.00 a month.\n",
    )


def test_the_active_subscriptions(money: Settings) -> None:
    result = run("recurring", "--as-of", "2026-05-01")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [HEADINGS, STREAMING, APPS_999, APPS_299]
    assert plain_lines(result.stdout) == ["Recurring: 3 active, $28.97 a month."]


def test_all_includes_the_ones_that_stopped(money: Settings) -> None:
    result = run("recurring", "--as-of", "2026-05-01", "--all")
    assert table_rows(result.stdout) == [HEADINGS, STREAMING, APPS_999, APPS_299, OLD_GYM]
    assert plain_lines(result.stdout) == ["Recurring: 3 active, $28.97 a month."]


def test_only_what_happened_by_the_day_counts(money: Settings) -> None:
    result = run("recurring", "--as-of", "2026-02-10")
    assert result.stdout == "No recurring charges.\nRecurring: 0 active, $0.00 a month.\n"
    result = run("recurring", "--as-of", "2026-02-10", "--all")
    assert table_rows(result.stdout) == [HEADINGS, OLD_GYM]


def test_a_day_that_is_not_one(money: Settings) -> None:
    result = run("recurring", "--as-of", "2026-02-30")
    assert result.exit_code == 2
    assert "'--as-of'" in result.stderr
```

## Tests to write

`tests/integration/test_recurring_report.py`:

- `recurring_charges` leaves out a pending charge, a paired transfer, a charge with an income category, and a refund; it ignores charges after `as_of`;
- `find_recurring` ignores a charge at zero or above inside a merchant's charges;
- `fin recurring` without `--as-of` uses today (a series whose window depends on it).

## Rules for this phase

- `domain/recurring.py` imports only the standard library and `finances.domain`; money stays integer cents.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_recurring.py tests/e2e/test_cli_recurring.py`, 33 tests;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.recurring --cov=finances.analysis.recurring --cov=finances.views.recurring --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` and `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|sorted\(|timedelta|find_recurring\(" -- src/finances/cli/reports.py`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 13a: recurring charges (YYYY-MM-DD)`.
