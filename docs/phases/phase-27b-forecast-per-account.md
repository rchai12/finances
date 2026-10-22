# Phase 27b: a 30-day forecast per account

## Goal

The household sees where each account is heading. After this phase, `fin forecast [--days 30] [--as-of DATE] [--account NAME]` takes each account's balance and walks it forward through the bills and income expected in the next N days (today counted as the first), showing the expected money in and out, the balance at the end, and the lowest point with its day. With `--account` it lists that account's expected items day by day with the running balance.

Each account is forecast from **its own** history only: a series found on the card is never applied to checking. Transfers that recur (a card payment) count here, unlike in 27a, because they move an account's balance. The web is 27c.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-27a-upcoming-bills-and-income.md`; `src/finances/domain/upcoming.py`, `src/finances/domain/recurring.py`, `src/finances/analysis/recurring.py`
- `src/finances/analysis/spending.py` (`load_flows`), `src/finances/domain/spending.py` (the kinds), `src/finances/db/repositories.py` (`list_accounts`, `get_account_by_name`, `list_balance_snapshots`), `src/finances/cli/reports.py` (`fin upcoming`)

## Starting state

N is `2954` when Phase 27a is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/forecast.py` | new (R1) |
| `src/finances/analysis/forecast.py` | new (R2 to R5) |
| `src/finances/views/forecast.py` | new (R6) |
| `src/finances/cli/reports.py`, `src/finances/cli/main.py` | `fin forecast` (R7, R8) |
| `tests/unit/test_forecast.py`, `tests/e2e/test_cli_forecast.py` | new: given |
| `tests/integration/test_forecast_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Pages, the dashboard, and charts (27c).
- One-off or planned bills a person types in; budgets in the forecast; a household total across accounts; more than 90 days.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/forecast.py  (standard library and finances.domain only)
@dataclass(frozen=True)
class Step:
    item: Upcoming
    balance_cents: int   # the balance just after this item


@dataclass(frozen=True)
class Walk:
    steps: list[Step]
    in_cents: int        # sum of the items above zero (or 0)
    out_cents: int       # sum of the items below zero (or 0)
    end_cents: int
    lowest_cents: int
    lowest_day: date


def walk(balance_cents: int, start: date, items: Iterable[Upcoming]) -> Walk: ...

# src/finances/analysis/forecast.py
@dataclass(frozen=True)
class AccountForecast:
    account: str          # the account's stored name
    balance_cents: int    # the starting balance
    balance_day: date     # its snapshot's as_of_date
    walk: Walk


@dataclass(frozen=True)
class ForecastReport:
    start: date
    end: date             # start + days - 1
    accounts: list[AccountForecast]
    no_balance: list[str] # names of accounts with no balance on or before start


def forecast_report(
    session: Session, start: date, days: int = 30, account: str | None = None
) -> ForecastReport: ...

# src/finances/views/forecast.py
@dataclass(frozen=True)
class ForecastRow:      # Account, Balance, As of, Expected in, Expected out, End, Lowest, Lowest on
    account: str
    balance: str
    as_of: str
    expected_in: str
    expected_out: str
    end: str
    lowest: str
    lowest_on: str


@dataclass(frozen=True)
class StepRow:          # Date, Merchant, Amount, Balance
    date: str
    merchant: str
    amount: str
    balance: str


def forecast_rows(report: ForecastReport) -> list[ForecastRow]: ...
def forecast_heading(report: ForecastReport) -> str: ...      # "Forecast from START to END."
def no_balance_line(report: ForecastReport) -> str | None: ... # "No balance yet: A, B." or None
def account_heading(report: ForecastReport) -> str: ...       # "Forecast for NAME from START to END."
def starting_line(forecast: AccountForecast) -> str: ...      # "Starting balance: $X (as of DATE)."
def step_rows(forecast: AccountForecast) -> list[StepRow]: ...
def lowest_line(forecast: AccountForecast) -> str: ...        # "Lowest: $Y on DATE."
```

## Requirements

### Part 1: the walk (pure)

- **R1.** `walk` adds each item's `amount_cents` to the balance in the order given (27a's `expected` order), giving one `Step` per item with the balance after it. `in_cents` and `out_cents` are the sums of the items above and below zero. `end_cents` is the balance after the last item (the starting balance when there are none). The lowest point starts as (`balance_cents`, `start`), and a step replaces it only when its balance is **strictly** lower, so a tie keeps the earliest day and a forecast that never dips reports the start.

### Part 2: loading and the report

- **R2.** One account's series come from **that account's** flows only (Phase 12a's flows from `date.min` to `start`, kept where `flow.account` is the account's name). Bills: `find_recurring` over the flows of kind `SPENDING` or `TRANSFER` below zero. Income: `find_recurring_income` over the flows of kind `INCOME`, `UNSORTED_IN`, or `TRANSFER` above zero. Both as of `start`. Refunds and pending flows are left out by their kind. The items are 27a's `expected(bills, income, start, days)`.
- **R3.** An account's starting balance is its newest snapshot whose `as_of_date` is on or before `start` (by `list_balance_snapshots`' order); a snapshot after `start` is never used. An account with none goes to `no_balance` and gets no forecast; it is never counted from zero.
- **R4.** Without `account`, `forecast_report` covers the active accounts in `list_accounts`' order (name, ignoring case): `accounts` holds those with a starting balance, `no_balance` the names of the rest, in the same order. Flows are loaded once.
- **R5.** With `account`, it finds the account by `get_account_by_name` (ignoring case; an inactive account is found too) and returns a report whose `accounts` holds that one only and whose `no_balance` is empty. It raises `ValueError("account not found")` when there is no such account, and `ValueError("NAME has no balance yet")` (the stored name) when R3 finds no balance.

### Part 3: views and the terminal

- **R6.** The views format with `format_cents` (signed) and ISO dates. `forecast_rows` gives one row per forecast account; `as_of` is the snapshot's day, `expected_out` is `$0.00` when nothing goes out. `no_balance_line` joins the names with `, ` and is `None` when the list is empty.
- **R7.** `fin forecast` takes `--as-of` and `--days` exactly as `fin upcoming` does, and `--account NAME`; it checks the schema and opens one session. Without `--account` it prints `forecast_heading`, then a table with the columns `Account`, `Balance`, `As of`, `Expected in`, `Expected out`, `End`, `Lowest`, `Lowest on` or `No accounts with a balance.`, then `no_balance_line` when there is one.
- **R8.** With `--account` it prints `account_heading`, `starting_line`, then a table with the columns `Date`, `Merchant`, `Amount`, `Balance` or `Nothing expected.`, then `lowest_line`. A `ValueError` from R5 fails the command with its message (exit 1). No rule in the command.

## Given tests

16 tests in two files. The fixture's balances are dated 2026-05-24 and the window runs 2026-05-25 to 2026-06-23.

`tests/unit/test_forecast.py`

```python
from datetime import date

from finances.domain.forecast import Step, Walk, walk
from finances.domain.upcoming import BILL, INCOME, Upcoming

START = date(2026, 5, 25)


def bill(day: date, merchant: str, cents: int) -> Upcoming:
    return Upcoming(day, BILL, merchant, "month", -cents)


def pay(day: date, merchant: str, cents: int) -> Upcoming:
    return Upcoming(day, INCOME, merchant, "two_weeks", cents)


def test_a_dip_before_payday() -> None:
    items = [
        bill(date(2026, 5, 27), "ACME UTILITY", 12000),
        pay(date(2026, 5, 29), "PAYCHECK EXAMPLE CORP", 300000),
        bill(date(2026, 6, 2), "PAYMENT TO TEST CARD", 50000),
        pay(date(2026, 6, 12), "PAYCHECK EXAMPLE CORP", 300000),
    ]
    assert walk(30000, START, items) == Walk(
        steps=[
            Step(items[0], 18000),
            Step(items[1], 318000),
            Step(items[2], 268000),
            Step(items[3], 568000),
        ],
        in_cents=600000,
        out_cents=-62000,
        end_cents=568000,
        lowest_cents=18000,
        lowest_day=date(2026, 5, 27),
    )


def test_the_start_is_the_lowest_when_nothing_dips() -> None:
    found = walk(100000, START, [pay(date(2026, 5, 30), "INTEREST PAID", 100)])
    assert (found.end_cents, found.lowest_cents, found.lowest_day) == (100100, 100000, START)


def test_a_tie_keeps_the_earliest_day() -> None:
    items = [
        bill(date(2026, 5, 26), "A", 500),
        pay(date(2026, 5, 27), "B", 500),
        bill(date(2026, 5, 28), "C", 500),
    ]
    found = walk(1000, START, items)
    assert (found.lowest_cents, found.lowest_day) == (500, date(2026, 5, 26))


def test_a_card_owed_more() -> None:
    items = [
        bill(date(2026, 5, 29), "BAZ BOX", 1200),
        pay(date(2026, 6, 3), "PAYMENT THANK YOU", 50000),
    ]
    found = walk(-45000, START, items)
    assert (found.end_cents, found.lowest_cents, found.lowest_day) == (
        3800,
        -46200,
        date(2026, 5, 29),
    )


def test_nothing_expected() -> None:
    assert walk(-2500, START, []) == Walk([], 0, 0, -2500, -2500, START)
```

`tests/e2e/test_cli_forecast.py`

```python
from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    get_account_by_name,
    set_balance_snapshot,
)
from finances.domain.models import DataSource
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, plain_lines, run, table_rows

AS_OF = ("--as-of", "2026-05-25")
HEADINGS = [
    "Account",
    "Balance",
    "As of",
    "Expected in",
    "Expected out",
    "End",
    "Lowest",
    "Lowest on",
]
CARD = [
    "Test Card",
    "-$450.00",
    "2026-05-24",
    "$500.00",
    "-$63.99",
    "-$13.99",
    "-$462.00",
    "2026-05-29",
]
CHECKING = [
    "Test Checking",
    "$300.00",
    "2026-05-24",
    "$6,000.00",
    "-$620.00",
    "$5,680.00",
    "$180.00",
    "2026-05-27",
]
SAVINGS = [
    "Test Savings",
    "$1,000.00",
    "2026-05-24",
    "$1.00",
    "$0.00",
    "$1,001.00",
    "$1,000.00",
    "2026-05-25",
]


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    """Checking: a utility on the 27th, pay every two weeks, a card payment on the 2nd.
    Card: streaming, a weekly box, the payment arriving on the 3rd. Savings: monthly interest.
    Brokerage: no balance."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        create_account(session, "Test Brokerage", "Test Bank", "other")
        set_balance_snapshot(session, checking.id, date(2026, 5, 24), 30000, DataSource.AGGREGATOR)
        set_balance_snapshot(session, card.id, date(2026, 5, 24), -45000, DataSource.AGGREGATOR)
        add_balance_snapshot(session, savings.id, date(2026, 5, 24), 100000, DataSource.STATEMENT)
        rows = [
            *((checking, date(2026, month, 27), -12000, "ACME UTILITY") for month in (2, 3, 4)),
            *(
                (checking, day, 300000, "PAYCHECK EXAMPLE CORP")
                for day in (
                    date(2026, 4, 3),
                    date(2026, 4, 17),
                    date(2026, 5, 1),
                    date(2026, 5, 15),
                )
            ),
            *(
                (checking, date(2026, month, 2), -50000, "PAYMENT TO TEST CARD")
                for month in (3, 4, 5)
            ),
            *((card, date(2026, month, 3), 50000, "PAYMENT THANK YOU") for month in (3, 4, 5)),
            *((card, date(2026, month, 5), -1599, "QUUX STREAMING") for month in (2, 3, 4, 5)),
            *((card, date(2026, 5, day), -1200, "BAZ BOX") for day in (1, 8, 15, 22)),
            *(
                (savings, day, 100, "INTEREST PAID")
                for day in (date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30))
            ),
        ]
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
    for pattern, category in (("PAYCHECK", "Paycheck"), ("INTEREST PAID", "Interest Income")):
        assert run("rules", "add", "--pattern", pattern, "--category", category).exit_code == 0
    return tmp_settings


@pytest.mark.parametrize(
    "args", [("forecast",), ("forecast", *AS_OF), ("forecast", "--account", "X")]
)
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


def test_every_account(money: Settings) -> None:
    result = run("forecast", *AS_OF)
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [HEADINGS, CARD, CHECKING, SAVINGS]
    assert plain_lines(result.stdout) == [
        "Forecast from 2026-05-25 to 2026-06-23.",
        "No balance yet: Test Brokerage.",
    ]


def test_one_account_day_by_day(money: Settings) -> None:
    result = run("forecast", *AS_OF, "--account", "test checking")
    assert table_rows(result.stdout) == [
        ["Date", "Merchant", "Amount", "Balance"],
        ["2026-05-27", "ACME UTILITY", "-$120.00", "$180.00"],
        ["2026-05-29", "PAYCHECK EXAMPLE CORP", "$3,000.00", "$3,180.00"],
        ["2026-06-02", "PAYMENT TO TEST CARD", "-$500.00", "$2,680.00"],
        ["2026-06-12", "PAYCHECK EXAMPLE CORP", "$3,000.00", "$5,680.00"],
    ]
    assert plain_lines(result.stdout) == [
        "Forecast for Test Checking from 2026-05-25 to 2026-06-23.",
        "Starting balance: $300.00 (as of 2026-05-24).",
        "Lowest: $180.00 on 2026-05-27.",
    ]


def test_a_shorter_window(money: Settings) -> None:
    rows = table_rows(run("forecast", *AS_OF, "--days", "7").stdout)
    assert rows[2] == [
        "Test Checking",
        "$300.00",
        "2026-05-24",
        "$3,000.00",
        "-$120.00",
        "$3,180.00",
        "$180.00",
        "2026-05-27",
    ]


def test_nothing_to_forecast(tmp_settings: Settings) -> None:
    assert run("db", "upgrade").exit_code == 0
    assert run("forecast", *AS_OF).stdout == (
        "Forecast from 2026-05-25 to 2026-06-23.\nNo accounts with a balance.\n"
    )


@pytest.mark.parametrize(
    ("account", "message"),
    [("Nope", "account not found"), ("Test Brokerage", "Test Brokerage has no balance yet")],
)
def test_a_refused_account(money: Settings, account: str, message: str) -> None:
    assert failed_cleanly(run("forecast", *AS_OF, "--account", account), message)


def test_one_account_with_nothing_expected(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        quiet = create_account(session, "Test Quiet", "Test Bank", "checking")
        add_balance_snapshot(session, quiet.id, date(2026, 5, 20), 500, DataSource.STATEMENT)
    engine.dispose()
    assert run("forecast", *AS_OF, "--account", "Test Quiet").stdout == (
        "Forecast for Test Quiet from 2026-05-25 to 2026-06-23.\n"
        "Starting balance: $5.00 (as of 2026-05-20).\n"
        "Nothing expected.\n"
        "Lowest: $5.00 on 2026-05-25.\n"
    )


def test_a_balance_after_the_start_is_not_used(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        savings = get_account_by_name(session, "Test Savings")
        add_balance_snapshot(session, savings.id, date(2026, 6, 1), 200000, DataSource.STATEMENT)
    engine.dispose()
    assert table_rows(run("forecast", *AS_OF).stdout)[3] == SAVINGS
```

## Tests to write

`tests/integration/test_forecast_more.py`: an inactive account left out of the summary but found by `--account`; a refund that recurs (not income); a pending charge (left out); two accounts without a balance (both named, in order); `fin forecast` without `--as-of` uses today; `--days 91` refused by Typer.

## Rules for this phase

- `domain/forecast.py` imports only the standard library and `finances.domain`; money stays integer cents.
- Phase 27a's given tests pass unchanged; `fin upcoming` does not change (it still leaves transfers out).

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_forecast.py tests/e2e/test_cli_forecast.py`, 16 tests;
- also `.venv/bin/python -m pytest tests/unit/test_upcoming.py tests/e2e/test_cli_upcoming.py tests/e2e/test_cli_recurring.py --no-cov`: all pass;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.forecast --cov=finances.analysis.forecast --cov=finances.views.forecast --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` and `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|sorted\(|timedelta" -- src/finances/cli/reports.py`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 27b: a 30-day forecast per account (YYYY-MM-DD)`.
