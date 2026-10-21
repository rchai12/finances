# Phase 27a: upcoming bills and recurring income

## Goal

The household sees what is coming. After this phase:

- `fin upcoming [--days 30] [--as-of DATE]` lists every bill and every payment of income expected in the next N days (today counted as the first), with the bills' total and the income's total;
- `fin recurring --income` lists income that arrives at a regular rhythm, as `fin recurring` lists charges.

Income is found with Phase 13a's series rules, plus a **two-week band** (12 to 16 days apart) for paychecks; pay on the 15th and the last day of the month fits it too (its gaps are 13 to 16 days). Income here is money in with an income category, or money in with no category; refunds and transfers are never income. Charges keep their four bands, so nothing earlier changes. The forecast is 27b; the web is 27c.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-13a-recurring-charges.md`; `src/finances/domain/recurring.py`, `src/finances/analysis/recurring.py`, `src/finances/views/recurring.py`
- `src/finances/domain/spending.py` (the kinds), `src/finances/cli/reports.py` (`fin recurring`)

## Starting state

N is `2932` when Phase 33 is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/recurring.py` | the two-week band, `INCOME_CADENCES`, `find_recurring_income` (R1 to R3) |
| `src/finances/domain/upcoming.py` | new (R4) |
| `src/finances/analysis/recurring.py` | new: `recurring_income` (R5) |
| `src/finances/analysis/upcoming.py` | new (R6) |
| `src/finances/views/recurring.py`, `src/finances/views/upcoming.py` | income summary (R7); new rows (R7) |
| `src/finances/cli/reports.py`, `src/finances/cli/main.py` | `fin upcoming`; `fin recurring --income` (R8) |
| `tests/unit/test_upcoming.py`, `tests/e2e/test_cli_upcoming.py` | new: given |
| `tests/integration/test_upcoming_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- The 30-day balance forecast (27b); pages, the dashboard, and charts (27c).
- Twice-a-month pay predicted on exact dates (it is predicted 14 days after the last); a two-week band for charges.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/recurring.py
INCOME_CADENCES = ("week", "two_weeks", "month", "quarter", "year")
# "two_weeks": gaps 12 to 16 days, at least 3 payments, next 14 days later, monthly cost amount x 26 / 12
def find_recurring_income(credits: Iterable[Charge], as_of: date) -> list[Recurring]: ...

# src/finances/domain/upcoming.py  (standard library and finances.domain only)
BILL = "bill"
INCOME = "income"


@dataclass(frozen=True)
class Upcoming:
    day: date
    kind: str          # BILL or INCOME
    merchant: str
    cadence: str
    amount_cents: int  # as the account holder sees it: a bill below zero, income above


def expected(bills: Iterable[Recurring], income: Iterable[Recurring], start: date, days: int) -> list[Upcoming]: ...

# src/finances/analysis/recurring.py
def recurring_income(session: Session, as_of: date) -> list[Recurring]: ...

# src/finances/analysis/upcoming.py
@dataclass(frozen=True)
class UpcomingReport:
    start: date
    end: date            # start + days - 1
    items: list[Upcoming]
    bills_cents: int     # sum of the bills (below zero, or 0)
    income_cents: int


def upcoming_report(session: Session, start: date, days: int = 30) -> UpcomingReport: ...

# src/finances/views/upcoming.py
@dataclass(frozen=True)
class UpcomingRow:
    date: str
    what: str      # "bill" or "income"
    merchant: str
    every: str     # the cadence
    amount: str    # format_cents, signed


def upcoming_rows(report: UpcomingReport) -> list[UpcomingRow]: ...
def upcoming_heading(report: UpcomingReport) -> str: ...  # "Expected from START to END."
def upcoming_summary(report: UpcomingReport) -> str: ...  # "Bills: $B. Income: $I."

# src/finances/views/recurring.py
def recurring_income_summary(items: list[Recurring]) -> str: ...  # "Recurring income: N active, $X a month."
```

## Requirements

### Part 1: the rules (pure)

- **R1.** `next_charge` and `monthly_cost` accept `two_weeks` (14 days later; × 26 / 12, rounded half up as the others). `find_recurring` and `CADENCES` do not change: charges never use the two-week band.
- **R2.** `find_recurring_income` applies Phase 13a's series rules (R3, R4 of that spec) to amounts **above** zero (ignoring the rest), trying the cadences of `INCOME_CADENCES`; for two weeks the fewest payments are 3 and the band is 12 to 16 days. Its `Recurring` items carry the amounts as they are (positive), and `active` follows the band's top as for charges. A cadence is chosen when every gap fits its band; the bands do not overlap.
- **R3.** `INCOME_CADENCES` lists the cadences in this order.
- **R4.** `expected` takes the **active** series only. For each, it starts at its `next_day` and steps with `next_charge` while the day is on or before the window's last day (`start` + `days` − 1), keeping the days on or after `start` (a series whose `next_day` is already past still gives its later days). Bills give `amount_cents` below zero, income above. The list is ordered by day, then income before bills, then by merchant ignoring case, then by merchant, then by amount.

### Part 2: loading, views, and the terminal

- **R5.** `recurring_income` loads Phase 12a's flows from `date.min` to `as_of`, keeps those whose kind is `INCOME`, or `UNSORTED_IN` (money in without a category), makes a `Charge` of each, and returns `find_recurring_income`. Refunds (`SPENDING` above zero) and transfers are left out by their kind.
- **R6.** `upcoming_report` takes Phase 13a's `recurring_charges(session, start)` as the bills and `recurring_income(session, start)` as the income, and returns `expected` over the window with the two totals.
- **R7.** `upcoming_rows` formats each item (ISO date; `format_cents` of the signed amount). `upcoming_summary` is `Bills: $B. Income: $I.` with B the bills' total (below zero, or `$0.00`). `recurring_income_summary` is `Recurring income: N active, $X a month.`
- **R8.** `fin upcoming` takes `--as-of` (as `fin recurring` does) and `--days` (a whole number from 1 to 90, Typer's own check, default 30), checks the schema, and prints the heading, then a table with columns `Date`, `What`, `Merchant`, `Every`, `Amount` or `Nothing expected.`, then the summary. `fin recurring --income` lists `recurring_income` with the same columns and rules as `fin recurring` (inactive only with `--all`), or `No recurring income.`, then `recurring_income_summary`. One session each; no rule in the commands.

## Given tests

17 tests in two files.

`tests/unit/test_upcoming.py`

```python
from datetime import date

import pytest

from finances.domain.recurring import (
    INCOME_CADENCES,
    Charge,
    Recurring,
    find_recurring,
    find_recurring_income,
    monthly_cost,
    next_charge,
)
from finances.domain.upcoming import BILL, INCOME, Upcoming, expected

AS_OF = date(2026, 5, 25)


def charges(merchant: str, cents: int, *days: date) -> list[Charge]:
    return [Charge(merchant, day, cents) for day in days]


def series(
    merchant: str, cadence: str, amount: int, last: date, next_day: date, active: bool = True
) -> Recurring:
    return Recurring(
        merchant=merchant,
        cadence=cadence,
        amount_cents=amount,
        monthly_cents=0,
        count=3,
        first_day=date(2026, 1, 1),
        last_day=last,
        next_day=next_day,
        active=active,
    )


def test_income_has_a_two_week_band() -> None:
    assert INCOME_CADENCES == ("week", "two_weeks", "month", "quarter", "year")
    assert next_charge(date(2026, 5, 15), "two_weeks") == date(2026, 5, 29)
    assert monthly_cost(300000, "two_weeks") == 650000
    assert monthly_cost(100001, "two_weeks") == 216669


def test_a_paycheck_every_two_weeks() -> None:
    found = find_recurring_income(
        charges(
            "PAYCHECK EXAMPLE CORP",
            300000,
            date(2026, 4, 3),
            date(2026, 4, 17),
            date(2026, 5, 1),
            date(2026, 5, 15),
        ),
        AS_OF,
    )
    assert found == [
        Recurring(
            merchant="PAYCHECK EXAMPLE CORP",
            cadence="two_weeks",
            amount_cents=300000,
            monthly_cents=650000,
            count=4,
            first_day=date(2026, 4, 3),
            last_day=date(2026, 5, 15),
            next_day=date(2026, 5, 29),
            active=True,
        )
    ]


def test_pay_on_the_15th_and_the_last_day_counts_as_every_two_weeks() -> None:
    days = (date(2026, 1, 15), date(2026, 1, 31), date(2026, 2, 15), date(2026, 2, 28))
    found = find_recurring_income(charges("PAYCHECK", 250000, *days), date(2026, 3, 1))
    assert [(item.cadence, item.count, item.next_day) for item in found] == [
        ("two_weeks", 4, date(2026, 3, 14))
    ]


def test_income_ignores_money_out_and_charges_ignore_the_new_band() -> None:
    days = (date(2026, 4, 3), date(2026, 4, 17), date(2026, 5, 1), date(2026, 5, 15))
    assert find_recurring_income(charges("ACME CLEANING", -9000, *days), AS_OF) == []
    assert find_recurring(charges("ACME CLEANING", -9000, *days), AS_OF) == []


def test_expected_bills_and_income_in_a_window() -> None:
    bills = [
        series("QUUX STREAMING", "month", 1599, date(2026, 5, 5), date(2026, 6, 5)),
        series("BAZ BOX", "week", 1200, date(2026, 5, 22), date(2026, 5, 29)),
        series("QUUX CLOUD", "year", 9900, date(2025, 6, 10), date(2026, 6, 10)),
        series("OLD GYM", "month", 2500, date(2026, 1, 1), date(2026, 2, 1), active=False),
        series("LATE BILL", "month", 4000, date(2026, 4, 20), date(2026, 5, 20)),
    ]
    income = [
        series("PAYCHECK EXAMPLE CORP", "two_weeks", 300000, date(2026, 5, 15), date(2026, 5, 29))
    ]
    assert expected(bills, income, AS_OF, 30) == [
        Upcoming(date(2026, 5, 29), INCOME, "PAYCHECK EXAMPLE CORP", "two_weeks", 300000),
        Upcoming(date(2026, 5, 29), BILL, "BAZ BOX", "week", -1200),
        Upcoming(date(2026, 6, 5), BILL, "BAZ BOX", "week", -1200),
        Upcoming(date(2026, 6, 5), BILL, "QUUX STREAMING", "month", -1599),
        Upcoming(date(2026, 6, 10), BILL, "QUUX CLOUD", "year", -9900),
        Upcoming(date(2026, 6, 12), INCOME, "PAYCHECK EXAMPLE CORP", "two_weeks", 300000),
        Upcoming(date(2026, 6, 12), BILL, "BAZ BOX", "week", -1200),
        Upcoming(date(2026, 6, 19), BILL, "BAZ BOX", "week", -1200),
        Upcoming(date(2026, 6, 20), BILL, "LATE BILL", "month", -4000),
    ]


@pytest.mark.parametrize(("days", "last"), [(1, date(2026, 5, 25)), (5, date(2026, 5, 29))])
def test_the_window_counts_today_as_its_first_day(days: int, last: date) -> None:
    bills = [series("BAZ BOX", "week", 1200, date(2026, 5, 18), date(2026, 5, 25))]
    found = expected(bills, [], AS_OF, days)
    assert [item.day for item in found] == [date(2026, 5, 25)]
    assert all(item.day <= last for item in found)


def test_nothing_expected() -> None:
    assert expected([], [], AS_OF, 30) == []
```

`tests/e2e/test_cli_upcoming.py`

```python
from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from tests.support import CLI_NOT_MIGRATED, plain_lines, run, table_rows

AS_OF = ("--as-of", "2026-05-25")
UPCOMING = ["Date", "What", "Merchant", "Every", "Amount"]
RECURRING = ["Merchant", "Every", "Amount", "Monthly", "Count", "Last", "Next", "Active"]


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    """A streaming plan, a weekly box, a yearly cloud plan, a paycheck every two weeks; and,
    never income, a grocery refund each month and a monthly move into savings."""
    assert run("db", "upgrade").exit_code == 0
    rows = [
        *((date(2026, month, 5), -1599, "QUUX STREAMING") for month in (2, 3, 4, 5)),
        *((date(2026, 5, day), -1200, "BAZ BOX") for day in (1, 8, 15, 22)),
        (date(2024, 6, 10), -9900, "QUUX CLOUD"),
        (date(2025, 6, 10), -9900, "QUUX CLOUD"),
        *(
            (day, 300000, "PAYCHECK EXAMPLE CORP")
            for day in (date(2026, 4, 3), date(2026, 4, 17), date(2026, 5, 1), date(2026, 5, 15))
        ),
        *((date(2026, month, 9), 599, "FOOBAR GROCERY") for month in (3, 4, 5)),
        *((date(2026, month, 1), 2000, "TRANSFER FROM CHECKING") for month in (3, 4, 5)),
    ]
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
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
        ("PAYCHECK", "Paycheck"),
        ("FOOBAR", "Groceries"),
        ("TRANSFER FROM", "Transfer"),
    ):
        assert run("rules", "add", "--pattern", pattern, "--category", category).exit_code == 0
    return tmp_settings


@pytest.mark.parametrize("args", [("upcoming",), ("upcoming", *AS_OF), ("recurring", "--income")])
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


def test_the_next_30_days(money: Settings) -> None:
    result = run("upcoming", *AS_OF)
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        UPCOMING,
        ["2026-05-29", "income", "PAYCHECK EXAMPLE CORP", "two_weeks", "$3,000.00"],
        ["2026-05-29", "bill", "BAZ BOX", "week", "-$12.00"],
        ["2026-06-05", "bill", "BAZ BOX", "week", "-$12.00"],
        ["2026-06-05", "bill", "QUUX STREAMING", "month", "-$15.99"],
        ["2026-06-10", "bill", "QUUX CLOUD", "year", "-$99.00"],
        ["2026-06-12", "income", "PAYCHECK EXAMPLE CORP", "two_weeks", "$3,000.00"],
        ["2026-06-12", "bill", "BAZ BOX", "week", "-$12.00"],
        ["2026-06-19", "bill", "BAZ BOX", "week", "-$12.00"],
    ]
    assert plain_lines(result.stdout) == [
        "Expected from 2026-05-25 to 2026-06-23.",
        "Bills: -$162.99. Income: $6,000.00.",
    ]


def test_a_shorter_window(money: Settings) -> None:
    result = run("upcoming", *AS_OF, "--days", "7")
    assert [row[2] for row in table_rows(result.stdout)[1:]] == ["PAYCHECK EXAMPLE CORP", "BAZ BOX"]
    assert plain_lines(result.stdout) == [
        "Expected from 2026-05-25 to 2026-05-31.",
        "Bills: -$12.00. Income: $3,000.00.",
    ]


def test_nothing_expected(tmp_settings: Settings) -> None:
    assert run("db", "upgrade").exit_code == 0
    assert run("upcoming", *AS_OF).stdout == (
        "Expected from 2026-05-25 to 2026-06-23.\nNothing expected.\nBills: $0.00. Income: $0.00.\n"
    )
    assert run("recurring", "--income", *AS_OF).stdout == (
        "No recurring income.\nRecurring income: 0 active, $0.00 a month.\n"
    )


def test_recurring_income(money: Settings) -> None:
    result = run("recurring", "--income", *AS_OF)
    assert table_rows(result.stdout) == [
        RECURRING,
        [
            "PAYCHECK EXAMPLE CORP",
            "two_weeks",
            "$3,000.00",
            "$6,500.00",
            "4",
            "2026-05-15",
            "2026-05-29",
            "yes",
        ],
    ]
    assert plain_lines(result.stdout) == ["Recurring income: 1 active, $6,500.00 a month."]


@pytest.mark.parametrize("days", ["0", "91"])
def test_a_window_out_of_range(money: Settings, days: str) -> None:
    result = run("upcoming", *AS_OF, "--days", days)
    assert result.exit_code == 2
    assert "'--days'" in result.stderr
```

## Tests to write

`tests/integration/test_upcoming_more.py`: a quarterly bill in the window; a paired transfer that recurs (left out of income); income with no category (counted); `fin upcoming` without `--as-of` uses today; `fin recurring --income --all` with income that stopped.

## Rules for this phase

- `domain/upcoming.py` imports only the standard library and `finances.domain`; money stays integer cents.
- Phase 13a's given tests pass unchanged.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_upcoming.py tests/e2e/test_cli_upcoming.py`, 17 tests;
- also `.venv/bin/python -m pytest tests/unit/test_recurring.py tests/e2e/test_cli_recurring.py tests/unit/test_insights.py --no-cov`: all pass;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.recurring --cov=finances.domain.upcoming --cov=finances.analysis.recurring --cov=finances.analysis.upcoming --cov=finances.views.recurring --cov=finances.views.upcoming --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` and `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|sorted\(|timedelta" -- src/finances/cli/reports.py`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 27a: upcoming bills and recurring income (YYYY-MM-DD)`.
