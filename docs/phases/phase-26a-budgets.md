# Phase 26a: budgets

## Goal

The household sets a monthly target for a category or a group and sees how each month is going. After this phase:

- `fin budgets set --name NAME --amount 250.00` sets (or replaces) the monthly target of a category or a group; `fin budgets remove --name NAME` removes it;
- `fin budgets list [--month YYYY-MM]` shows each budget for the month: target, spent, what is left, the share used, and the share of the month gone;
- spending over a budget is a finding, `over_budget`, in `fin insights`, the Insights page, and the dashboard.

"Spent" is Phase 12a's spending (refunds reduce it; transfers, income, and pending are left out); a group's spent is all of its categories'. One amount repeats every month; nothing rolls over. The Budgets web page and the dashboard's budget block are Phase 26b.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-12a-spending.md`; `src/finances/analysis/spending.py`, `src/finances/domain/spending.py`
- `src/finances/domain/insights.py`, `src/finances/analysis/insights.py`
- `src/finances/db/repositories.py`: `_category_row`, `delete_category`; `src/finances/domain/money.py` (`parse_money`)
- `tests/support.py`

## Starting state

N is `2838` when Phase 13d is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0010_budgets.py` | new: given |
| `src/finances/db/orm.py` | new: `BudgetRow` |
| `src/finances/domain/models.py` | new: `Budget` |
| `src/finances/db/repositories.py` | new: `set_budget`, `remove_budget`, `list_budgets`; `delete_category` removes the budget (R1, R2) |
| `src/finances/domain/budgets.py` | new (R3, R4) |
| `src/finances/domain/insights.py` | `TYPES` gains `over_budget`; new `over_budget` (R5) |
| `src/finances/analysis/budgets.py` | new (R6) |
| `src/finances/analysis/insights.py` | the report includes `over_budget` (R7) |
| `src/finances/views/budgets.py` | new (R8) |
| `src/finances/cli/budgets.py`, `src/finances/cli/main.py` | `fin budgets` (R9) |
| `tests/unit/test_budgets.py`, `tests/integration/test_migration_0010.py`, `tests/e2e/test_cli_budgets.py` | new: given |
| `tests/unit/test_insights.py` | `test_the_types`: given change (below) |
| `tests/integration/test_budgets_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- The web (26b); rollover; a budget per person or per account; yearly budgets; alerts.

## Dependencies

None new. Migration `0010` (given).

## Design

```python
# src/finances/domain/models.py
@dataclass(frozen=True)
class Budget:
    id: int
    category_id: int  # a category or a group
    amount_cents: int


# src/finances/domain/budgets.py  (standard library and finances.domain only)
@dataclass(frozen=True)
class BudgetTarget:
    name: str
    is_group: bool
    target_cents: int


@dataclass(frozen=True)
class BudgetLine:
    name: str
    is_group: bool
    target_cents: int
    spent_cents: int
    left_cents: int
    used_percent: int
    month_gone_percent: int


def month_gone_percent(start: date, end: date, today: date) -> int: ...
def budget_lines(
    targets: Iterable[BudgetTarget],
    spent_by_category: Mapping[str, int],
    spent_by_group: Mapping[str, int],
    start: date,
    end: date,
    today: date,
) -> list[BudgetLine]: ...

# src/finances/domain/insights.py
TYPES = (..., "fees", "over_budget", "duplicate", "large_first_charge")
def over_budget(month: date, lines: Iterable[BudgetLine]) -> list[Finding]: ...

# src/finances/db/repositories.py
def set_budget(session: Session, name: str, amount_cents: int) -> tuple[str, Budget]: ...  # (stored name, budget)
def remove_budget(session: Session, name: str) -> str: ...                                # the stored name
def list_budgets(session: Session) -> list[Budget]: ...

# src/finances/analysis/budgets.py
def budget_report(session: Session, start: date, today: date) -> list[BudgetLine]: ...

# src/finances/views/budgets.py
@dataclass(frozen=True)
class BudgetTableRow:
    budget: str
    kind: str        # "group" or "category"
    target: str
    spent: str
    left: str
    used: str        # "120%"
    month_gone: str  # "100%"


def budget_rows(lines: list[BudgetLine]) -> list[BudgetTableRow]: ...
def budgets_summary(lines: list[BudgetLine]) -> str: ...  # "Over budget: N."
```

Messages, in full (each a `ValueError`; the command prints `Error: <message>`, exit code 1):

| When | Message |
|---|---|
| no group or category has the name | the existing `category not found` |
| the amount is not money text, or not from 1 to 100000000 cents | `a budget must be an amount from $0.01 to $1,000,000.00` |
| removing a budget that does not exist | `there is no budget for NAME` (the stored name) |
| `--month` | Phase 12a's `month must be a year and month, like 2026-05` |

The `over_budget` detail: `NAME: $SPENT spent against a budget of $TARGET.`

## Requirements

### Part 1: storage

- **R1.** The given migration, and `BudgetRow` matching it. `set_budget` finds the group or category by name (ignoring case and outer spaces), checks the amount (1 to 100000000 cents), and stores it, replacing an earlier budget of the same row. `remove_budget` deletes it. `list_budgets` returns every budget, in id order. None commit.
- **R2.** `delete_category` deletes the budget of the row it deletes (a group or a category) before deleting the row; a budget of the category its uses move to is unchanged.

### Part 2: the rules (pure)

- **R3.** `month_gone_percent` is 0 when `today` is before `start`, 100 when it is after `end`, and otherwise the days from `start` to `today`, both counted, as a share of the month's days, in whole percent rounded half up.
- **R4.** `budget_lines` gives one line per target, ordered by name ignoring case, then name: `spent_cents` from `spent_by_group` for a group and `spent_by_category` for a category (0 when absent); `left_cents` the target minus spent; `used_percent` spent × 100 / target in whole percent rounded half up (it can be below zero, or above 100); `month_gone_percent` from R3.
- **R5.** `over_budget` gives a finding for each line whose spent is **more than** its target: severity `high` when spent is at least 1.5 times the target, else `medium`; savings spent minus target; subject the name; detail as above; ordered by subject ignoring case, then subject. `over_budget` sits after `fees` in `TYPES`.

### Part 3: the report and the terminal

- **R6.** `budget_report(session, start, today)` reads the budgets (with each row's name and whether it is a group), loads Phase 12a's flows for `start`'s month, takes `spending_lines` by category and by group (spent per label), and returns `budget_lines`.
- **R7.** `insights_report` adds `over_budget(M's first day, budget_report(session, M's first day, M's last day))` to its findings.
- **R8.** `budget_rows` formats each line (`format_cents`; percents as `N%`; kind `group` or `category`); `budgets_summary` is `Over budget: N.` (lines whose spent is more than their target).
- **R9.** `fin budgets set --name NAME --amount AMOUNT` reads the amount with `parse_money` (its error becomes the amount message) and prints `Budget for "NAME": $X a month.`; `fin budgets remove --name NAME` prints `Removed the budget for "NAME".`; `fin budgets list [--month YYYY-MM]` (the current month when not given; the month's share gone counted to today) prints `Budgets for YYYY-MM.`, then a table with columns `Budget`, `Kind`, `Target`, `Spent`, `Left`, `Used`, `Month gone` and the summary, or `No budgets.` Each command checks the schema first and uses one session.

## Given migration

`src/finances/db/migrations/versions/0010_budgets.py`

```python
"""Create budgets: a monthly target for a category or a group."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_budgets"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], name="fk_budgets_category_id_categories"
        ),
        sa.UniqueConstraint("category_id", name="uq_budgets_category_id"),
    )


def downgrade() -> None:
    op.drop_table("budgets")
```

## Given tests

26 tests in three files.

`tests/unit/test_budgets.py`

```python
from datetime import date

import pytest

from finances.domain.budgets import BudgetLine, BudgetTarget, budget_lines, month_gone_percent
from finances.domain.insights import TYPES, Finding, over_budget

MAY = (date(2026, 5, 1), date(2026, 5, 31))


def test_over_budget_comes_after_fees() -> None:
    assert TYPES.index("over_budget") == TYPES.index("fees") + 1
    assert TYPES[-2:] == ("duplicate", "large_first_charge")


@pytest.mark.parametrize(
    ("today", "percent"),
    [
        (date(2026, 4, 30), 0),
        (date(2026, 5, 1), 3),
        (date(2026, 5, 16), 52),
        (date(2026, 5, 31), 100),
        (date(2026, 6, 1), 100),
    ],
)
def test_month_gone_percent(today: date, percent: int) -> None:
    assert month_gone_percent(*MAY, today) == percent


def test_budget_lines() -> None:
    targets = [
        BudgetTarget("Groceries", False, 20000),
        BudgetTarget("Food", True, 40000),
        BudgetTarget("dining", False, 25000),
        BudgetTarget("Travel", True, 10000),
    ]
    lines = budget_lines(
        targets,
        {"Groceries": 10000, "dining": 30000, "Coffee & Dessert": 450},
        {"Food": 40450},
        *MAY,
        date(2026, 6, 3),
    )
    assert lines == [
        BudgetLine("dining", False, 25000, 30000, -5000, 120, 100),
        BudgetLine("Food", True, 40000, 40450, -450, 101, 100),
        BudgetLine("Groceries", False, 20000, 10000, 10000, 50, 100),
        BudgetLine("Travel", True, 10000, 0, 10000, 0, 100),
    ]


def test_used_percent_rounds_half_up_and_can_go_below_zero() -> None:
    lines = budget_lines(
        [BudgetTarget("A", False, 800), BudgetTarget("B", False, 1000)],
        {"A": 4, "B": -250},
        {},
        *MAY,
        date(2026, 5, 16),
    )
    assert [(line.used_percent, line.month_gone_percent) for line in lines] == [(1, 52), (-25, 52)]


def test_over_budget() -> None:
    lines = [
        BudgetLine("Dining", False, 25000, 30000, -5000, 120, 100),
        BudgetLine("Food", True, 40000, 60000, -20000, 150, 100),
        BudgetLine("Groceries", False, 20000, 20000, 0, 100, 100),
        BudgetLine("Travel", True, 10000, 14999, -4999, 150, 100),
    ]
    month = date(2026, 5, 1)
    assert over_budget(month, lines) == [
        Finding(
            "over_budget",
            "medium",
            month,
            "Dining",
            5000,
            "Dining: $300.00 spent against a budget of $250.00.",
        ),
        Finding(
            "over_budget",
            "high",
            month,
            "Food",
            20000,
            "Food: $600.00 spent against a budget of $400.00.",
        ),
        Finding(
            "over_budget",
            "medium",
            month,
            "Travel",
            4999,
            "Travel: $149.99 spent against a budget of $100.00.",
        ),
    ]
    assert over_budget(month, []) == []
```

`tests/integration/test_migration_0010.py`

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import Base, BudgetRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("category_id", "INTEGER", False),
    ("amount_cents", "BIGINT", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def at_0010(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    command.upgrade(make_config(url), "0010")
    return url


def test_0010_follows_0009() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0010")
    assert script.down_revision == "0009"


def test_the_table(at_0010: str) -> None:
    engine = get_engine(at_0010)
    found = inspect(engine)
    columns = [(c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns("budgets")]
    uniques = [(u["name"], u["column_names"]) for u in found.get_unique_constraints("budgets")]
    foreign = [
        (f["constrained_columns"], f["referred_table"]) for f in found.get_foreign_keys("budgets")
    ]
    primary = found.get_pk_constraint("budgets")
    engine.dispose()
    assert columns == COLUMNS
    assert uniques == [("uq_budgets_category_id", ["category_id"])]
    assert foreign == [(["category_id"], "categories")]
    assert (primary["name"], primary["constrained_columns"]) == ("pk_budgets", ["id"])
    assert [(c.name, str(c.type), c.nullable) for c in BudgetRow.__table__.columns] == COLUMNS
    assert BudgetRow.__table__ is Base.metadata.tables["budgets"]


def test_downgrade_removes_only_the_table(at_0010: str) -> None:
    command.downgrade(make_config(at_0010), "0009")
    engine = get_engine(at_0010)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert "budgets" not in names and "transfer_pairs" in names
```

`tests/e2e/test_cli_budgets.py`

```python
from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, plain_lines, run, table_rows

HEADINGS = ["Budget", "Kind", "Target", "Spent", "Left", "Used", "Month gone"]
AMOUNT = "a budget must be an amount from $0.01 to $1,000,000.00"


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    """May on one card: dining $300.00, groceries $120.00 less a $20.00 refund, a coffee."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (day, cents, description) in enumerate(
            (
                (5, -20000, "ACME DINER"),
                (12, -10000, "ACME DINER"),
                (6, -12000, "FOOBAR GROCERY"),
                (9, 2000, "FOOBAR GROCERY"),
                (7, -450, "ACME COFFEE"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    for pattern, category in (
        ("ACME DINER", "Dining"),
        ("FOOBAR", "Groceries"),
        ("ACME COFFEE", "Coffee & Dessert"),
    ):
        assert run("rules", "add", "--pattern", pattern, "--category", category).exit_code == 0
    return tmp_settings


def set_budgets() -> None:
    for name, amount in (
        ("dining", "250"),
        ("Food", "$400.00"),
        ("Groceries", "200.00"),
        ("travel", "100"),
    ):
        assert run("budgets", "set", "--name", name, "--amount", amount).exit_code == 0


@pytest.mark.parametrize(
    "args",
    [("list",), ("set", "--name", "Dining", "--amount", "1"), ("remove", "--name", "Dining")],
)
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run("budgets", *args)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


def test_set_list_and_remove(money: Settings) -> None:
    assert run("budgets", "list", "--month", "2026-05").stdout == (
        "Budgets for 2026-05.\nNo budgets.\n"
    )
    result = run("budgets", "set", "--name", "dining", "--amount", "250")
    assert (result.exit_code, result.stdout) == (0, 'Budget for "Dining": $250.00 a month.\n')
    set_budgets()
    result = run("budgets", "list", "--month", "2026-05")
    assert table_rows(result.stdout) == [
        HEADINGS,
        ["Dining", "category", "$250.00", "$300.00", "-$50.00", "120%", "100%"],
        ["Food", "group", "$400.00", "$404.50", "-$4.50", "101%", "100%"],
        ["Groceries", "category", "$200.00", "$100.00", "$100.00", "50%", "100%"],
        ["Travel", "group", "$100.00", "$0.00", "$100.00", "0%", "100%"],
    ]
    assert plain_lines(result.stdout) == ["Budgets for 2026-05.", "Over budget: 2."]
    result = run("budgets", "set", "--name", "Dining", "--amount", "350")
    assert result.stdout == 'Budget for "Dining": $350.00 a month.\n'
    result = run("budgets", "remove", "--name", "groceries")
    assert (result.exit_code, result.stdout) == (0, 'Removed the budget for "Groceries".\n')
    rows = table_rows(run("budgets", "list", "--month", "2026-05").stdout)
    assert [row[:3] for row in rows[1:]] == [
        ["Dining", "category", "$350.00"],
        ["Food", "group", "$400.00"],
        ["Travel", "group", "$100.00"],
    ]


def test_over_budget_is_a_finding(money: Settings) -> None:
    set_budgets()
    rows = table_rows(run("insights", "--month", "2026-05").stdout)
    assert rows[1:] == [
        [
            "medium",
            "over_budget",
            "Dining",
            "$50.00",
            "Dining: $300.00 spent against a budget of $250.00.",
        ],
        [
            "medium",
            "over_budget",
            "Food",
            "$4.50",
            "Food: $404.50 spent against a budget of $400.00.",
        ],
    ]


def test_deleting_a_category_removes_its_budget(money: Settings) -> None:
    set_budgets()
    result = run("categories", "delete", "--name", "Groceries", "--move-to", "Dining")
    assert result.exit_code == 0
    rows = table_rows(run("budgets", "list", "--month", "2026-05").stdout)
    assert [row[0] for row in rows[1:]] == ["Dining", "Food", "Travel"]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("set", "--name", "Nope", "--amount", "10"), "category not found"),
        (("set", "--name", "Dining", "--amount", "0"), AMOUNT),
        (("set", "--name", "Dining", "--amount", "-5"), AMOUNT),
        (("set", "--name", "Dining", "--amount", "ten"), AMOUNT),
        (("set", "--name", "Dining", "--amount", "1000000.01"), AMOUNT),
        (("remove", "--name", "Nope"), "category not found"),
        (("remove", "--name", "Dining"), "there is no budget for Dining"),
        (("list", "--month", "2026-13"), "month must be a year and month, like 2026-05"),
    ],
)
def test_a_refused_command(money: Settings, args, message: str) -> None:
    assert failed_cleanly(run("budgets", *args), message)
```

The change to `tests/unit/test_insights.py`, exactly this diff:

```diff
diff --git a/tests/unit/test_insights.py b/tests/unit/test_insights.py
index 14cc91d..f439d50 100644
--- a/tests/unit/test_insights.py
+++ b/tests/unit/test_insights.py
@@ -69,6 +69,7 @@ def test_the_types() -> None:
         "price_increase",
         "interest",
         "fees",
+        "over_budget",
         "duplicate",
         "large_first_charge",
     )
```

## Tests to write

`tests/integration/test_budgets_more.py`:

- `set_budget` replacing a budget; amounts of exactly 1 and 100000000 cents;
- deleting a group with a budget (an empty group); moving a category's uses to a category that has its own budget (that budget unchanged);
- `budget_report` leaves out a paired transfer and an income transaction in a budgeted category;
- `fin budgets list` without `--month` uses the current month.

## Rules for this phase

- `domain/budgets.py` imports only the standard library and `finances.domain`; money stays integer cents.
- **Thin.** The commands call the repositories, `budget_report`, and the views.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_budgets.py tests/integration/test_migration_0010.py tests/e2e/test_cli_budgets.py`, 26 tests;
- also `.venv/bin/python -m pytest tests/unit/test_insights.py tests/unit/test_unusual_charges.py tests/e2e/test_cli_insights.py tests/e2e/test_cli_category_editing.py --no-cov`: all pass;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.budgets --cov=finances.domain.insights --cov=finances.analysis.budgets --cov=finances.analysis.insights --cov=finances.views.budgets --cov=finances.cli.budgets --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` and `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|sorted\(" -- src/finances/cli/budgets.py`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 26a: budgets (YYYY-MM-DD)`.
