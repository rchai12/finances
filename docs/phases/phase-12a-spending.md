# Phase 12a: spending

## Goal

The household sees where its money went in a month or any range of days. After this phase, `fin spending` shows spending grouped by category, group, merchant, person, account, bank, or card, with the total spent, the income, how many transfers were left out, and the money that came in without a category.

What counts:

- **Spending** is every money-out and refund that is not a transfer and not income. A refund (money in with a spending category) **reduces** its line, so a line can be negative.
- **Transfers** are left out: transactions in a transfer pair (Phase 11c), and transactions whose category is a transfer category (the Transfers group). This is what keeps a card payment from counting twice.
- **Income** is a transaction whose category is an income category. It is totalled, never mixed into spending.
- **Money in without a category** (a positive amount with no category) is neither spending nor income until someone categorizes it; it is totalled on its own line so it is not lost.
- **Pending** transactions are left out.
- A transaction belongs to the day it was **bought** (`transaction_date`) when the statement gives one, otherwise the day it posted.

Balances, net worth, and month over month are Phase 12b; the web pages are 12c.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/analysis/people.py` (`load_attribution`: whose money a transaction is), `src/finances/domain/merchants.py` (`clean_merchant`), `src/finances/domain/models.py` (`Category`: `group_id`, `is_transfer`, `is_income`)
- `src/finances/cli/categories.py` and `src/finances/cli/listing.py`: how commands read options and fail

## Starting state

N is `2342` when Phase 11d is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/spending.py` | new (R1 to R5) |
| `src/finances/db/repositories.py` | new: `list_transactions_between` (R6) |
| `src/finances/analysis/spending.py` | new (R7, R8) |
| `src/finances/views/spending.py` | new (R9) |
| `src/finances/cli/reports.py` | new (R10 to R12) |
| `src/finances/cli/main.py` | registers `spending` |
| `tests/unit/test_spending.py`, `tests/e2e/test_cli_spending.py` | new: given |
| `tests/integration/test_spending_report.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Balances, net worth, month over month, coverage of months (12b); web pages (12c).
- Budgets, averages, charts, exporting, or a filter by person or account (a `--by` grouping is enough for now).
- Changing any category, rule, or pair.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/spending.py  (standard library and finances.domain only)
SPENDING = "spending"
INCOME = "income"
TRANSFER = "transfer"
UNSORTED_IN = "unsorted_in"
UNCATEGORIZED = "Uncategorized"   # the category and group label without a category
UNASSIGNED = "Unassigned"         # the person label when no person is found
NO_CARD = "No card"               # the card label without card digits
BY = ("category", "group", "merchant", "person", "account", "bank", "card")


@dataclass(frozen=True)
class Flow:
    amount_cents: int
    day: date
    kind: str       # SPENDING, INCOME, TRANSFER, or UNSORTED_IN
    category: str
    group: str
    merchant: str
    person: str
    account: str    # the account's name
    bank: str       # the account's institution
    card: str       # the card's last four digits, or NO_CARD


@dataclass(frozen=True)
class SpendingLine:
    label: str
    spent_cents: int  # money out is positive here; refunds reduce it
    count: int


@dataclass(frozen=True)
class SpendingSummary:
    spent_cents: int
    income_cents: int
    transfers: int
    unsorted_in_cents: int
    unsorted_in_count: int


def flow_kind(amount_cents: int, *, paired: bool, category: Category | None) -> str: ...
def spending_lines(flows: Iterable[Flow], by: str) -> list[SpendingLine]: ...
def summarize(flows: Iterable[Flow]) -> SpendingSummary: ...
def month_range(text: str) -> tuple[date, date]: ...
def month_bounds(day: date) -> tuple[date, date]: ...
```

```python
# src/finances/db/repositories.py
def list_transactions_between(session: Session, start: date, end: date) -> list[Transaction]: ...

# src/finances/analysis/spending.py
@dataclass(frozen=True)
class SpendingReport:
    start: date
    end: date
    by: str
    lines: list[SpendingLine]
    summary: SpendingSummary


def load_flows(session: Session, start: date, end: date) -> list[Flow]: ...
def spending_report(session: Session, start: date, end: date, by: str = "category") -> SpendingReport: ...

# src/finances/views/spending.py
@dataclass(frozen=True)
class SpendingRow:
    label: str
    spent: str   # format_cents
    count: str


def spending_rows(report: SpendingReport) -> list[SpendingRow]: ...
def spending_heading(report: SpendingReport) -> str: ...
def spending_summary(report: SpendingReport) -> list[str]: ...
```

Messages, in full. Each is a `ValueError`; the command prints `Error: <message>` and exits with code 1.

| When | Message |
|---|---|
| `--month` is not `YYYY-MM` with a month from 01 to 12 | `month must be a year and month, like 2026-05` |
| `--month` with `--from` or `--to` | `give --month, or --from and --to, not both` |
| only one of `--from` and `--to` | `give both --from and --to` |
| the start is after the end | `the start date is after the end date` |
| `--by` not in `BY` | `by must be one of: category, group, merchant, person, account, bank, card` |

## Requirements

### Part 1: the rules (pure)

- **R1.** `flow_kind` returns, checking in this order: `TRANSFER` when `paired` or the category is a transfer category; `INCOME` when the category is an income category; `UNSORTED_IN` when there is no category and the amount is above zero; otherwise `SPENDING`.
- **R2.** `spending_lines` keeps only `SPENDING` flows, groups them by the field named `by`, and gives each label its spent amount (the negated sum of its amounts) and count. Lines come largest spent first, then by label ignoring case, then by label. An unknown `by` raises the message above, even with no flows.
- **R3.** `summarize` gives the spent amount of all `SPENDING` flows (negated sum), the sum of `INCOME` amounts as they are, the number of `TRANSFER` flows, and the sum and number of `UNSORTED_IN` flows.
- **R4.** `month_range("YYYY-MM")` returns the first and last day of that month; anything else (including a day, a one-digit month, or month 00 or 13) raises the message above.
- **R5.** `month_bounds(day)` returns the first and last day of the day's month.

### Part 2: loading and the report

- **R6.** `list_transactions_between` returns the transactions that are not pending and whose day (`transaction_date` when it is set, otherwise `posted_date`) is from `start` to `end` inclusive, ordered by id. It uses `func.coalesce`, which every dialect has.
- **R7.** `load_flows` builds one `Flow` per transaction of `list_transactions_between`: `day` as above; `kind` from `flow_kind` with `paired` true for any transaction in a transfer pair and the transaction's category (from its assignment) or `None`; `category` the category's name and `group` its group's name, both `UNCATEGORIZED` without a category; `merchant` from `clean_merchant(description)`; `person` from `load_attribution(session).person(transaction)`, or `UNASSIGNED`; `account` and `bank` the account's name and institution; `card` the transaction's `card_last4`, or `NO_CARD`.
- **R8.** `spending_report` checks, in this order, that `by` is in `BY` and that `start` is not after `end` (the messages above), then returns the report of `load_flows`, `spending_lines`, and `summarize`.

### Part 3: the terminal

- **R9.** `spending_rows` formats each line (`format_cents`, the count as text). `spending_heading` is `Spending from START to END, by BY.` (ISO dates). `spending_summary` is `Spent: $S. Income: $I.`, then `Transfers left out: T.`, then `Money in without a category: $M (count: C).` only when C is above zero, each amount through `format_cents`.
- **R10.** `fin spending` takes `--month` (text), `--from` and `--to` (`YYYY-MM-DD`, as `fin transactions list` reads them), and `--by` (text, default `category`). It checks the schema first, as other commands do. The range is the month given; or from and to; or, with none of the three, the current month (`month_bounds(date.today())`). Before the database is read it refuses, in this order, `--month` with `--from` or `--to`, only one of `--from` and `--to`, and a `--month` that `month_range` refuses; `spending_report` then checks `--by` and the order of the dates (R8).
- **R11.** It prints the heading; then a table whose columns are `BY` with its first letter capitalised, `Spent`, and `Count`, one row per line, or `No spending.` when there is none; then the summary lines.
- **R12.** One session, read only. The command holds no rule: kinds, grouping, and totals come from `domain`, `analysis`, and `views`.

## Given tests

43 tests in two files.

`tests/unit/test_spending.py`

```python
from datetime import date

import pytest

from finances.domain.models import Category
from finances.domain.spending import (
    BY,
    INCOME,
    SPENDING,
    TRANSFER,
    UNSORTED_IN,
    Flow,
    SpendingLine,
    SpendingSummary,
    flow_kind,
    month_bounds,
    month_range,
    spending_lines,
    summarize,
)

DINING = Category(10, "Dining", 1, False, False, False)
PAYCHECK = Category(20, "Paycheck", 2, False, True, False)
CARD_PAYMENT = Category(30, "Credit Card Payment", 3, True, False, False)


def flow(
    cents: int, kind: str = SPENDING, category: str = "Dining", merchant: str = "ACME"
) -> Flow:
    return Flow(
        amount_cents=cents,
        day=date(2026, 5, 1),
        kind=kind,
        category=category,
        group="Food",
        merchant=merchant,
        person="Unassigned",
        account="Test Card",
        bank="Test Bank",
        card="No card",
    )


@pytest.mark.parametrize(
    ("cents", "paired", "category", "kind"),
    [
        (-500, False, DINING, SPENDING),
        (500, False, DINING, SPENDING),
        (-500, False, None, SPENDING),
        (500, False, None, UNSORTED_IN),
        (300000, False, PAYCHECK, INCOME),
        (-50000, False, CARD_PAYMENT, TRANSFER),
        (-50000, True, None, TRANSFER),
        (300000, True, PAYCHECK, TRANSFER),
    ],
    ids=[
        "a-purchase",
        "a-refund",
        "uncategorized-out",
        "uncategorized-in",
        "income",
        "transfer-category",
        "paired",
        "paired-wins",
    ],
)
def test_flow_kind(cents: int, paired: bool, category: Category | None, kind: str) -> None:
    assert flow_kind(cents, paired=paired, category=category) == kind


def test_the_ways_to_group() -> None:
    assert BY == ("category", "group", "merchant", "person", "account", "bank", "card")


def test_refunds_net_and_the_largest_comes_first() -> None:
    flows = [
        flow(-450, category="Coffee & Dessert"),
        flow(-2599, category="Groceries"),
        flow(599, category="Groceries"),
        flow(-1250, category="Coffee & Dessert"),
        flow(-12000, category="Utilities & Internet"),
        flow(300000, INCOME, category="Paycheck"),
        flow(-50000, TRANSFER, category="Uncategorized"),
        flow(2500, UNSORTED_IN, category="Uncategorized"),
    ]
    assert spending_lines(flows, "category") == [
        SpendingLine("Utilities & Internet", 12000, 1),
        SpendingLine("Groceries", 2000, 2),
        SpendingLine("Coffee & Dessert", 1700, 2),
    ]


def test_a_tie_goes_by_name_ignoring_case_and_a_refund_can_win() -> None:
    flows = [
        flow(-500, merchant="beta"),
        flow(-500, merchant="Alpha"),
        flow(700, merchant="QUUX"),
        flow(-200, merchant="QUUX"),
    ]
    assert spending_lines(flows, "merchant") == [
        SpendingLine("Alpha", 500, 1),
        SpendingLine("beta", 500, 1),
        SpendingLine("QUUX", -500, 2),
    ]


def test_group_by_another_field() -> None:
    assert spending_lines([flow(-450), flow(-50)], "group") == [SpendingLine("Food", 500, 2)]


def test_an_unknown_way_to_group() -> None:
    with pytest.raises(ValueError) as caught:
        spending_lines([], "vendor")
    assert str(caught.value) == (
        "by must be one of: category, group, merchant, person, account, bank, card"
    )


def test_summarize() -> None:
    flows = [
        flow(-2599),
        flow(599),
        flow(300000, INCOME),
        flow(-1000, INCOME),
        flow(-50000, TRANSFER),
        flow(50000, TRANSFER),
        flow(2500, UNSORTED_IN),
    ]
    assert summarize(flows) == SpendingSummary(
        spent_cents=2000,
        income_cents=299000,
        transfers=2,
        unsorted_in_cents=2500,
        unsorted_in_count=1,
    )
    assert summarize([]) == SpendingSummary(0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    ("text", "bounds"),
    [
        ("2026-05", (date(2026, 5, 1), date(2026, 5, 31))),
        ("2026-02", (date(2026, 2, 1), date(2026, 2, 28))),
        ("2024-02", (date(2024, 2, 1), date(2024, 2, 29))),
        ("2026-12", (date(2026, 12, 1), date(2026, 12, 31))),
    ],
)
def test_month_range(text: str, bounds: tuple[date, date]) -> None:
    assert month_range(text) == bounds


@pytest.mark.parametrize("text", ["2026-13", "2026-00", "2026-5", "May 2026", "", "2026-05-01"])
def test_a_month_that_is_not_one(text: str) -> None:
    with pytest.raises(ValueError) as caught:
        month_range(text)
    assert str(caught.value) == "month must be a year and month, like 2026-05"


def test_month_bounds() -> None:
    assert month_bounds(date(2026, 12, 15)) == (date(2026, 12, 1), date(2026, 12, 31))
```

`tests/e2e/test_cli_spending.py`

```python
from datetime import date

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_person, set_account_owner

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
MAY = ("--month", "2026-05")


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def plain_lines(output: str) -> list[str]:
    return [
        line
        for line in output.splitlines()
        if line and not line.startswith(("│", "┃", "┏", "┡", "└"))
    ]


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
    """A month of synthetic money; see each row's note. Rules and pairing run through the CLI."""
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
        pat = create_person(session, "Pat Example")
        set_account_owner(session, card.id, pat.id)
        rows = (
            # account, posted, transaction date, cents, description, card, pending
            (card, 2, None, -450, "SQ *ACME COFFEE", "1111", False),
            (card, 3, None, -2599, "FOOBAR GROCERY #77", "1111", False),
            (card, 10, None, 599, "FOOBAR GROCERY #77", "1111", False),  # a refund
            (card, 32, 31, -1250, "ACME COFFEE #12", None, False),  # posted 1 June, bought 31 May
            (card, 1, 0, -800, "BAZ BOOKS", None, False),  # posted 1 May, bought 30 April
            (checking, 20, None, -50000, "PAYMENT TO TEST CARD", None, False),  # a transfer
            (card, 21, None, 50000, "PAYMENT THANK YOU", None, False),  # its other side
            (checking, 15, None, 300000, "PAYCHECK EXAMPLE CORP", None, False),  # income
            (checking, 16, None, 2500, "VENMO CASHOUT", None, False),  # money in, no category
            (card, 18, None, -999, "QUUX STREAMING", None, True),  # pending
            (checking, 25, None, -12000, "ACME UTILITY", None, False),
            (card, 12, None, -1500, "BAZ BOOKS", None, False),  # spending, no category
        )
        for number, (account, posted, bought, cents, description, last4, pending) in enumerate(
            rows, start=1
        ):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=_day(posted),
                    transaction_date=None if bought is None else _day(bought),
                    amount_cents=cents,
                    description=description,
                    card_last4=last4,
                    is_pending=pending,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    for pattern, category in (
        ("ACME COFFEE", "Coffee & Dessert"),
        ("FOOBAR GROCERY", "Groceries"),
        ("PAYCHECK", "Paycheck"),
        ("ACME UTILITY", "Utilities & Internet"),
    ):
        assert run("rules", "add", "--pattern", pattern, "--category", category).exit_code == 0
    return migrated


def _day(number: int) -> date:
    """Day numbers count from 1 May 2026: 0 is 30 April, 32 is 1 June."""
    return date.fromordinal(date(2026, 4, 30).toordinal() + number)


@pytest.mark.parametrize("args", [(), MAY, ("--by", "merchant")])
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run("spending", *args)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


def test_a_month_by_category(money: Settings) -> None:
    result = run("spending", *MAY)
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        ["Category", "Spent", "Count"],
        ["Utilities & Internet", "$120.00", "1"],
        ["Groceries", "$20.00", "2"],
        ["Coffee & Dessert", "$17.00", "2"],
        ["Uncategorized", "$15.00", "1"],
    ]
    assert plain_lines(result.stdout) == [
        "Spending from 2026-05-01 to 2026-05-31, by category.",
        "Spent: $172.00. Income: $3,000.00.",
        "Transfers left out: 2.",
        "Money in without a category: $25.00 (count: 1).",
    ]


@pytest.mark.parametrize(
    ("by", "rows"),
    [
        (
            "group",
            [
                ["Group", "Spent", "Count"],
                ["Home", "$120.00", "1"],
                ["Food", "$37.00", "4"],
                ["Uncategorized", "$15.00", "1"],
            ],
        ),
        (
            "merchant",
            [
                ["Merchant", "Spent", "Count"],
                ["ACME UTILITY", "$120.00", "1"],
                ["FOOBAR GROCERY", "$20.00", "2"],
                ["ACME COFFEE", "$17.00", "2"],
                ["BAZ BOOKS", "$15.00", "1"],
            ],
        ),
        (
            "person",
            [
                ["Person", "Spent", "Count"],
                ["Unassigned", "$120.00", "1"],
                ["Pat Example", "$52.00", "5"],
            ],
        ),
        (
            "account",
            [
                ["Account", "Spent", "Count"],
                ["Test Checking", "$120.00", "1"],
                ["Test Card", "$52.00", "5"],
            ],
        ),
        (
            "bank",
            [
                ["Bank", "Spent", "Count"],
                ["Test Bank", "$120.00", "1"],
                ["Example Card Co", "$52.00", "5"],
            ],
        ),
        (
            "card",
            [
                ["Card", "Spent", "Count"],
                ["No card", "$147.50", "3"],
                ["1111", "$24.50", "3"],
            ],
        ),
    ],
)
def test_a_month_by_another_field(money: Settings, by: str, rows: list[list[str]]) -> None:
    result = run("spending", *MAY, "--by", by)
    assert table_rows(result.stdout) == rows
    assert plain_lines(result.stdout)[0] == f"Spending from 2026-05-01 to 2026-05-31, by {by}."


def test_the_day_bought_decides_the_month(money: Settings) -> None:
    result = run("spending", "--month", "2026-04")
    assert table_rows(result.stdout) == [
        ["Category", "Spent", "Count"],
        ["Uncategorized", "$8.00", "1"],
    ]
    assert plain_lines(result.stdout) == [
        "Spending from 2026-04-01 to 2026-04-30, by category.",
        "Spent: $8.00. Income: $0.00.",
        "Transfers left out: 0.",
    ]
    result = run("spending", "--month", "2026-06")
    assert result.stdout == (
        "Spending from 2026-06-01 to 2026-06-30, by category.\n"
        "No spending.\n"
        "Spent: $0.00. Income: $0.00.\n"
        "Transfers left out: 0.\n"
    )


def test_a_range_where_refunds_win(money: Settings) -> None:
    result = run("spending", "--from", "2026-05-10", "--to", "2026-05-20")
    assert table_rows(result.stdout) == [
        ["Category", "Spent", "Count"],
        ["Uncategorized", "$15.00", "1"],
        ["Groceries", "-$5.99", "1"],
    ]
    assert plain_lines(result.stdout) == [
        "Spending from 2026-05-10 to 2026-05-20, by category.",
        "Spent: $9.01. Income: $3,000.00.",
        "Transfers left out: 1.",
        "Money in without a category: $25.00 (count: 1).",
    ]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--month", "2026-13"), "month must be a year and month, like 2026-05"),
        (
            ("--month", "2026-05", "--from", "2026-05-01"),
            "give --month, or --from and --to, not both",
        ),
        (("--from", "2026-05-01"), "give both --from and --to"),
        (("--to", "2026-05-01"), "give both --from and --to"),
        (("--from", "2026-05-20", "--to", "2026-05-10"), "the start date is after the end date"),
        (
            ("--month", "2026-05", "--by", "vendor"),
            "by must be one of: category, group, merchant, person, account, bank, card",
        ),
    ],
)
def test_a_refused_report(money: Settings, args, message: str) -> None:
    assert failed_cleanly(run("spending", *args), message)
```

## Tests to write

`tests/integration/test_spending_report.py`:

- `list_transactions_between`: the day bought decides, pending left out, both ends included, id order;
- `load_flows`: a transaction in a pair, one with a transfer category, one with an income category, a category added to a group by hand (its group's name), a cardholder mapped to a person, an account with no owner (`UNASSIGNED`);
- `spending_report`: both messages, in their order;
- `fin spending` with no options reports the current month (the heading names it).

## Rules for this phase

- `domain/spending.py` imports only the standard library and `finances.domain`.
- Money stays integer cents throughout; `format_cents` only in `views`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_spending.py tests/e2e/test_cli_spending.py`, 43 tests;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.spending --cov=finances.analysis.spending --cov=finances.views.spending --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` and `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|flow_kind|spending_lines|summarize|sum\(|sorted\(" -- src/finances/cli/reports.py`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 12a: spending (YYYY-MM-DD)`.
