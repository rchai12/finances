# Phase 12b: balances and months

## Goal

The household sees what it has and how its months compare. After this phase:

- `fin balances` lists each active account's newest balance, with its date and where it came from (a statement or SimpleFIN), then the cash, the cards, other accounts, and the **net worth**; accounts with no balance yet are named, not guessed;
- `fin months` lists the last N calendar months (6 unless told otherwise) with what was spent, the income, the change in spending from the month before, and whether the data **covers the whole month**; for each month that is only partly covered it names the accounts whose data does not reach across it.

Spent and income mean exactly what they mean in `fin spending` (Phase 12a). The web pages are 12c.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-12a-spending.md` and `src/finances/analysis/spending.py`: spent and income
- `src/finances/db/repositories.py`: `latest_balance`, `list_accounts`, `list_statements`; `src/finances/db/orm.py`: `StatementRow`, `FeedPullRow`, `BalanceSnapshotRow`
- `src/finances/cli/reports.py`: the command this phase sits beside

## Starting state

N is `2403` when Phase 12a is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/periods.py` | new (R1, R2) |
| `src/finances/db/repositories.py` | new: `account_data_span` (R3) |
| `src/finances/analysis/balances.py` | new (R4) |
| `src/finances/analysis/months.py` | new (R5) |
| `src/finances/views/balances.py`, `src/finances/views/months.py` | new (R6, R7) |
| `src/finances/cli/reports.py` | new: `balances_command`, `months_command` (R8, R9) |
| `src/finances/cli/main.py` | registers `balances` and `months` |
| `tests/unit/test_periods.py`, `tests/e2e/test_cli_balances_months.py` | new: given |
| `tests/integration/test_balances_months.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Balances worked forward from transactions after the newest snapshot, balance history, or charts.
- Gaps between statements inside an account's data (a missing month in the middle); Phase 14's `data_coverage` handles exact periods.
- Inactive accounts (left out of both reports), currencies, web pages (12c).

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/periods.py  (standard library and finances.domain only)
MONTHS_MAX = 24


def months_ending(day: date, count: int) -> list[tuple[date, date]]: ...
def uncovered(spans: Mapping[str, tuple[date, date] | None], start: date, end: date) -> list[str]: ...
```

```python
# src/finances/db/repositories.py
def account_data_span(session: Session, account_id: int) -> tuple[date, date] | None: ...

# src/finances/analysis/balances.py
@dataclass(frozen=True)
class BalanceLine:
    account: str
    type: str                    # the account type's value
    balance_cents: int | None
    as_of: date | None
    source: str | None           # DataSource value


@dataclass(frozen=True)
class BalanceReport:
    lines: list[BalanceLine]
    cash_cents: int              # checking and savings
    cards_cents: int             # credit cards
    other_cents: int             # other
    net_worth_cents: int         # the three added
    without_balance: list[str]   # account names, in line order


def balance_report(session: Session) -> BalanceReport: ...

# src/finances/analysis/months.py
@dataclass(frozen=True)
class MonthLine:
    start: date
    spent_cents: int
    income_cents: int
    uncovered: list[str]


def month_report(session: Session, day: date, count: int) -> list[MonthLine]: ...

# src/finances/views/balances.py
@dataclass(frozen=True)
class BalanceRow:
    account: str
    type: str
    balance: str
    as_of: str
    source: str


def balance_rows(report: BalanceReport) -> list[BalanceRow]: ...
def balance_summary(report: BalanceReport) -> list[str]: ...

# src/finances/views/months.py
@dataclass(frozen=True)
class MonthRow:
    month: str
    spent: str
    income: str
    change: str
    covered: str


def month_rows(lines: list[MonthLine]) -> list[MonthRow]: ...
def month_heading(lines: list[MonthLine]) -> str: ...
def month_notes(lines: list[MonthLine]) -> list[str]: ...
```

Messages, in full. Each is a `ValueError`; the command prints `Error: <message>` and exits with code 1.

| When | Message |
|---|---|
| `--to` is not a month (`month_range` of Phase 12a) | `month must be a year and month, like 2026-05` |
| a count below 1 or above `MONTHS_MAX` | `count must be from 1 to 24` |

## Requirements

### Part 1: periods (pure)

- **R1.** `months_ending(day, count)` returns the first and last day of `count` calendar months, oldest first, the last being `day`'s month. A count below 1 or above `MONTHS_MAX` raises the message above.
- **R2.** `uncovered(spans, start, end)` returns the names whose span is `None`, or does not start on or before `start` and end on or after `end`, ordered by name ignoring case, then by name.

### Part 2: data and reports

- **R3.** `account_data_span` returns the earliest and latest of these days for the account, or `None` when there are none: each stored statement's `period_start` and `period_end`; each transaction's day (`transaction_date` when set, otherwise `posted_date`) that is not pending; and the UTC date of each feed pull's `pulled_at`.
- **R4.** `balance_report` makes one line per active account (`list_accounts`, in its order), with the account's `latest_balance` or `None`s. The cash, cards, and other totals add the balances of checking and savings, credit card, and other accounts; the net worth adds the three. Accounts with no balance are listed in `without_balance` and add nothing.
- **R5.** `month_report(session, day, count)` returns one line per month of `months_ending(day, count)`, oldest first: `spent_cents` and `income_cents` from Phase 12a's `summarize(load_flows(session, start, end))`, and `uncovered` from `uncovered` over every active account's `account_data_span`, keyed by account name.

### Part 3: the terminal

- **R6.** `balance_rows` formats each line: the balance with `format_cents`, the date in ISO form, the source `statement` for a statement and `SimpleFIN` for the aggregator, and empty text for each missing value. `balance_summary` is `Cash: $C. Cards: $D. Other: $O.`, then `Net worth: $N.`, then `No balance yet: A, B.` only when some account has none.
- **R7.** `month_rows` formats each line: the month as `YYYY-MM`; spent and income with `format_cents`; the change, empty for the first month, otherwise this month's spent minus the previous month's, with a leading `+` when above zero (`format_cents` already gives `-` below zero, and zero is `$0.00`); `covered` is `yes` when no account is uncovered, otherwise `partly`. `month_heading` is `Months from FIRST to LAST.` (as `YYYY-MM`). `month_notes` gives, for each partly covered month in order, `YYYY-MM: no data for the whole month from A, B.`
- **R8.** `fin balances` checks the schema, then prints the table (`Account`, `Type`, `Balance`, `As of`, `From`) and the summary lines; with no active account it prints `No accounts.` only.
- **R9.** `fin months` takes `--to` (text, a month; the current month when not given) and `--count` (a whole number, default 6). It checks the schema, reads `--to` with `month_range`, and calls `month_report` with that month's first day (or `date.today()`), which refuses a bad count. It prints the heading, the table (`Month`, `Spent`, `Income`, `Change`, `Covered`), then the notes.
- **R10.** Each command uses one session and holds no rule: totals, coverage, and the change come from `domain`, `analysis`, and `views`.

## Given tests

17 tests in two files.

`tests/unit/test_periods.py`

```python
from datetime import date

import pytest

from finances.domain.periods import MONTHS_MAX, months_ending, uncovered


def test_at_most_two_years() -> None:
    assert MONTHS_MAX == 24


def test_months_ending_in_a_month_oldest_first() -> None:
    assert months_ending(date(2026, 3, 17), 4) == [
        (date(2025, 12, 1), date(2025, 12, 31)),
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2026, 3, 1), date(2026, 3, 31)),
    ]
    assert months_ending(date(2026, 3, 1), 1) == [(date(2026, 3, 1), date(2026, 3, 31))]
    assert len(months_ending(date(2026, 3, 1), 24)) == 24


@pytest.mark.parametrize("count", [0, -1, 25])
def test_a_count_out_of_range(count: int) -> None:
    with pytest.raises(ValueError) as caught:
        months_ending(date(2026, 3, 1), count)
    assert str(caught.value) == "count must be from 1 to 24"


def test_uncovered_names_the_accounts_missing_part_of_the_range() -> None:
    spans = {
        "whole": (date(2026, 3, 1), date(2026, 3, 31)),
        "Wider": (date(2026, 1, 9), date(2026, 5, 2)),
        "starts late": (date(2026, 3, 2), date(2026, 5, 2)),
        "Ends early": (date(2026, 1, 1), date(2026, 3, 30)),
        "no data": None,
        "after": (date(2026, 4, 1), date(2026, 4, 30)),
    }
    assert uncovered(spans, date(2026, 3, 1), date(2026, 3, 31)) == [
        "after",
        "Ends early",
        "no data",
        "starts late",
    ]
    assert uncovered({}, date(2026, 3, 1), date(2026, 3, 31)) == []
```

`tests/e2e/test_cli_balances_months.py`

```python
from datetime import UTC, date, datetime

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import FeedPullRow, TransactionRow
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    create_statement,
    set_balance_snapshot,
)
from finances.domain.models import DataSource

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
BALANCES = ["Account", "Type", "Balance", "As of", "From"]
MONTHS = ["Month", "Spent", "Income", "Change", "Covered"]


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


def statement(session, account, number: int, start: date, end: date, closing: int) -> None:
    create_statement(
        session,
        account_id=account.id,
        source_filename=f"statement-{number}.pdf",
        file_sha256=f"s{number:02d}".ljust(64, "0"),
        parser_name="test",
        period_start=start,
        period_end=end,
        opening_balance_cents=0,
        closing_balance_cents=closing,
        lines_parsed=0,
        rows_inserted=0,
        rows_duplicate=0,
    )
    add_balance_snapshot(session, account.id, end, closing, DataSource.STATEMENT)


@pytest.fixture
def money(migrated: Settings) -> Settings:
    """Checking: statements for March and April. Card: one statement from 5 March to 4 April,
    then a SimpleFIN pull on 20 May. Savings: a quarterly statement, March to May."""
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        statement(session, checking, 1, date(2026, 3, 1), date(2026, 3, 31), 250000)
        statement(session, checking, 2, date(2026, 4, 1), date(2026, 4, 30), 310000)
        statement(session, card, 3, date(2026, 3, 5), date(2026, 4, 4), -45000)
        statement(session, savings, 4, date(2026, 3, 1), date(2026, 5, 31), 1000000)
        set_balance_snapshot(session, card.id, date(2026, 5, 20), -61234, DataSource.AGGREGATOR)
        session.add(
            FeedPullRow(
                account_id=card.id,
                inserted=1,
                updated=0,
                removed=0,
                unchanged=0,
                feed_total_cents=-1500,
                balance_cents=-61234,
                balance_date=date(2026, 5, 20),
                drift_cents=None,
                pulled_at=datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
            )
        )
        for number, (account, day, cents, description) in enumerate(
            (
                (card, date(2026, 3, 10), -2000, "FOOBAR GROCERY"),
                (card, date(2026, 4, 12), -3000, "FOOBAR GROCERY"),
                (card, date(2026, 5, 3), -1500, "BAZ BOOKS"),
                (checking, date(2026, 3, 15), 300000, "PAYCHECK EXAMPLE CORP"),
                (checking, date(2026, 4, 15), 300000, "PAYCHECK EXAMPLE CORP"),
                (checking, date(2026, 4, 25), -12000, "ACME UTILITY"),
            ),
            start=1,
        ):
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
    assert run("rules", "add", "--pattern", "PAYCHECK", "--category", "Paycheck").exit_code == 0
    return migrated


@pytest.mark.parametrize("args", [("balances",), ("months",), ("months", "--to", "2026-05")])
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


# Balances


def test_no_accounts(migrated: Settings) -> None:
    assert run("balances").stdout == "No accounts.\n"


def test_balances_and_net_worth(money: Settings) -> None:
    result = run("balances")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        BALANCES,
        ["Test Card", "credit_card", "-$612.34", "2026-05-20", "SimpleFIN"],
        ["Test Checking", "checking", "$3,100.00", "2026-04-30", "statement"],
        ["Test Savings", "savings", "$10,000.00", "2026-05-31", "statement"],
    ]
    assert plain_lines(result.stdout) == [
        "Cash: $13,100.00. Cards: -$612.34. Other: $0.00.",
        "Net worth: $12,487.66.",
    ]


def test_an_account_without_a_balance(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Brokerage", "Test Bank", "other")
    engine.dispose()
    result = run("balances")
    assert table_rows(result.stdout)[1] == ["Test Brokerage", "other", "", "", ""]
    assert plain_lines(result.stdout) == [
        "Cash: $13,100.00. Cards: -$612.34. Other: $0.00.",
        "Net worth: $12,487.66.",
        "No balance yet: Test Brokerage.",
    ]


# Months


def test_three_months(money: Settings) -> None:
    result = run("months", "--to", "2026-05", "--count", "3")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        MONTHS,
        ["2026-03", "$20.00", "$3,000.00", "", "partly"],
        ["2026-04", "$150.00", "$3,000.00", "+$130.00", "yes"],
        ["2026-05", "$15.00", "$0.00", "-$135.00", "partly"],
    ]
    assert plain_lines(result.stdout) == [
        "Months from 2026-03 to 2026-05.",
        "2026-03: no data for the whole month from Test Card.",
        "2026-05: no data for the whole month from Test Card, Test Checking.",
    ]


def test_one_month_and_the_default_count(money: Settings) -> None:
    result = run("months", "--to", "2026-04", "--count", "1")
    assert result.stdout.splitlines()[0] == "Months from 2026-04 to 2026-04."
    assert table_rows(result.stdout) == [MONTHS, ["2026-04", "$150.00", "$3,000.00", "", "yes"]]
    rows = table_rows(run("months", "--to", "2026-05").stdout)
    assert [row[0] for row in rows] == [
        "Month",
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
        "2026-05",
    ]
    assert rows[1] == ["2025-12", "$0.00", "$0.00", "", "partly"]
    assert rows[2][3] == "$0.00"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--to", "2026-13"), "month must be a year and month, like 2026-05"),
        (("--to", "2026-05", "--count", "0"), "count must be from 1 to 24"),
        (("--to", "2026-05", "--count", "25"), "count must be from 1 to 24"),
    ],
)
def test_a_refused_report(money: Settings, args, message: str) -> None:
    assert failed_cleanly(run("months", *args), message)
```

## Tests to write

`tests/integration/test_balances_months.py`:

- `account_data_span`: no data; statements only; a transaction bought before its statement starts; a pending transaction left out; a feed pull later than every transaction;
- `balance_report`: an inactive account left out; the newest of two snapshots on different days;
- `month_report`: an inactive account never uncovered; an account with no data uncovered in every month;
- `fin months` without `--to` ends at the current month (the heading names it).

## Rules for this phase

- `domain/periods.py` imports only the standard library and `finances.domain`.
- Money stays integer cents; `format_cents` only in `views`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_periods.py tests/e2e/test_cli_balances_months.py`, 17 tests;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.periods --cov=finances.analysis.balances --cov=finances.analysis.months --cov=finances.views.balances --cov=finances.views.months --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` and `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|sorted\(|timedelta|uncovered\(" -- src/finances/cli/reports.py`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 12b: balances and months (YYYY-MM-DD)`.
