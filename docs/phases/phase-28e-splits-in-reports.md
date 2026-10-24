# Phase 28e: splits in the reports and the terminal

## Goal

After this phase a split transaction counts as its parts wherever money is grouped by category, and as one payment wherever charges are counted at a merchant:

- the spending report, the months, the budgets, the account page, and insights' category spikes count each part under its own category and group;
- recurring charges and income, upcoming bills and the forecast, and insights' merchant findings and stats see the whole transaction once, so splitting a monthly bill never breaks its series;
- search (the Transactions page, a report's drill-down, and the `list_transactions` tool) finds each part on its own, with the part's amount, so a drill-down adds up to the line it came from;
- the terminal splits a transaction (`fin transactions split`), shows its parts, and removes a split.

Splits on the web are Phase 28g, after tags and notes on the web (28f).

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-28d-splits-stored.md`
- `src/finances/domain/splits.py`, `src/finances/domain/money.py` (`parse_money`), `src/finances/domain/spending.py` (`flow_kind`, `spending_lines`)
- `src/finances/analysis/spending.py` (`flows_for`, `load_flows`, `spending_report`), `months.py`, `budgets.py`, `account_page.py`, `insights.py`, `recurring.py`, `forecast.py`, `search.py`
- `src/finances/db/repositories/splits.py`, `src/finances/views/transactions.py` (`found_rows`), `src/finances/mcp_server/tools.py` (`_transaction_item`)
- `src/finances/cli/tags.py` (commands on `transactions_app`), `src/finances/cli/categories.py` (`categorize_all`)

## Starting state

N is `3605` when Phase 28d is the last phase built. The newest migration is `0019`; this phase adds none. Today every flow is a whole transaction and a split one shows the category and group `Split`. `list_transactions_between` returns transactions by id; `list_transactions_by_day` (which search reads) newest posted day first, then highest id.

## Scope

| Path | What changes |
|---|---|
| `src/finances/analysis/spending.py` | `parts` on `flows_for` and `load_flows`; `spending_report` counts parts (R1, R2) |
| `src/finances/analysis/months.py`, `budgets.py`, `account_page.py`, `insights.py` | which flows each reads (R2, R3) |
| `src/finances/analysis/search.py` | one found item per part (R4) |
| `src/finances/views/transactions.py`, `src/finances/mcp_server/tools.py` | a found item's amount from its flow (R5); `PartLine`, `part_lines` (R10) |
| `src/finances/domain/splits.py` | `signed_parts`, `parse_part` (R6) |
| `src/finances/db/repositories/splits.py`, `src/finances/db/repositories/__init__.py` | `split_by_sizes` (R7) |
| `src/finances/cli/splits.py` (new), `src/finances/cli/main.py` | three commands on `transactions_app` (R8 to R10) |
| `tests/unit/test_repositories_split.py` | the given diff (R11) |
| `tests/unit/test_split_parts.py`, `tests/integration/test_split_reports.py`, `tests/e2e/test_cli_splits.py` | new: given |
| `tests/integration/test_split_reports_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Any page or form for splits (28g); a column or mark on any page or table saying a row is a part.
- Changing `recurring.py`, `forecast.py`, `names.py`, or `refunds.py`: they read whole transactions as they do today.
- A count of purchases that treats a split as one in the spending report's `count` (a split purchase counts once per part there; its money is right).

## Dependencies

None new. No migration.

## Design

```python
# src/finances/analysis/spending.py
def flows_for(
    session: Session, transactions: Iterable[Transaction], *, parts: bool = False
) -> list[Flow]: ...
def load_flows(session: Session, start: date, end: date, *, parts: bool = False) -> list[Flow]: ...

# src/finances/domain/splits.py (critical)
def signed_parts(amount_cents: int, sizes: Sequence[int]) -> list[int]: ...
# each size given the transaction's sign: negative when amount_cents < 0, positive otherwise
def parse_part(text: str) -> tuple[int, str]: ...
# "12.00 Groceries" -> (1200, "Groceries"): parse_money of the text before the first run of
# white space, and the rest stripped as the category

# src/finances/db/repositories/splits.py
def split_by_sizes(
    session: Session, transaction_id: int, parts: Sequence[tuple[int, str]]
) -> list[SplitPart]: ...   # each part: (size in cents, more than zero; category name)

# src/finances/views/transactions.py
@dataclass(frozen=True)
class PartLine:
    part: str
    amount: str
    category: str

def part_lines(parts: list[SplitPart], names: dict[int, str]) -> list[PartLine]: ...
```

New commands on `transactions_app`, from a new module `cli/splits.py` that `cli/main.py` imports:

| Command | Options | Prints |
|---|---|---|
| `fin transactions split` | `--id INT`, `--part TEXT` (two or more, each `SIZE CATEGORY`) | `Transaction 1: split into 2 parts.` |
| `fin transactions unsplit` | `--id INT` | `Transaction 1: split removed.` then the categorize line |
| `fin transactions parts` | `--id INT` | a table with headings `Part`, `Amount`, `Category`; or `Transaction 1 is not split.` |

Each command calls `require_current_schema()` first; a refusal is `fail(message)`.

## Requirements

### Flows

- **R1.** With `parts=False` (the default) `flows_for` and `load_flows` are as today. With `parts=True`, a split transaction gives one flow per part in position order, where its single flow would be: the part's amount, its category's name and its group's name, and the kind `flow_kind(part amount, paired=False, category=the part's category)`; every other field is the transaction's. A transaction that is not split gives the same flow either way. A split transaction's flows add up to its amount.
- **R2.** These read `parts=True`: `spending_report`, `month_report`, `budget_report`, `account_page` (its spending and months), and the flows `insights_report` gives to `spikes`.
- **R3.** These read whole transactions: `recurring_charges`, `recurring_income`, the forecast and upcoming items, `names`, `refund_facts`, and in `insights_report` every finding but `spikes` and `over_budget` (which reads `budget_report`), and `merchant_stats`.

### Search and what shows it

- **R4.** `search_transactions` reads `flows_for(..., parts=True)`: a split transaction gives one `FoundTransaction` per part, each with the transaction and that part's flow, matched on its own; `limit` counts found items. A transaction that is not split is found as today.
- **R5.** `found_rows` gives each row the amount of the item's flow (`format_cents(item.flow.amount_cents)`), and `_transaction_item` gives `"amount_cents"` from the flow. Neither changes for a transaction that is not split.

### Splitting from the terminal

- **R6.** `signed_parts` refuses a size that is not more than zero (`each part's size must be more than zero`) and returns the sizes signed as designed. `parse_part` refuses text with no category after the size (`a part is a size and a category, such as 12.00 Groceries`) and passes on `parse_money`'s refusal (`invalid money text`). Both are pure and covered 100% by `tests/unit/test_split_parts.py`; `domain/splits.py` stays critical.
- **R7.** `split_by_sizes` refuses a transaction that does not exist (`transaction not found`), then signs the sizes with `signed_parts`, then calls `set_split`, so every refusal of 28d's `set_split` applies. It is re-exported from `finances.db.repositories`.
- **R8.** `fin transactions split` reads every `--part` with `parse_part`, in the order given, before anything else, then calls `split_by_sizes` and prints as designed.
- **R9.** `fin transactions unsplit` calls `clear_split`, then `categorize_all()`, and prints as designed with `categorized_text`.
- **R10.** `fin transactions parts` refuses a transaction that does not exist (`transaction not found`), prints `Transaction N is not split.` for one with no parts, and otherwise the table from `part_lines` (the position, `format_cents` of the amount, the category's name).
- **R11.** Apply the given diff to `tests/unit/test_repositories_split.py`. No other earlier test changes.

## Given diff to earlier tests

```text
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index fc3920e..4b2917a 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -133,6 +133,7 @@ HOMES = {
     "splits": [
         "clear_split",
         "set_split",
+        "split_by_sizes",
         "splits_for",
     ],
     "tags": [
@@ -164,7 +165,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 114
+    assert len(expected) == 115
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
```

## Given tests

24 tests in three files. Do not change them. `tests/unit/test_split_parts.py` covers every line and branch of the two new functions; 28d's `tests/unit/test_splits.py` covers the rest of the module.

`tests/unit/test_split_parts.py`

```python
import pytest

from finances.domain.splits import parse_part, signed_parts


@pytest.mark.parametrize(
    ("amount", "sizes", "signed"),
    [
        (-2000, [1200, 800], [-1200, -800]),
        (5000, [2500, 2500], [2500, 2500]),
        (0, [100, 100], [100, 100]),
    ],
)
def test_sizes_take_the_transaction_sign(amount: int, sizes: list[int], signed: list[int]) -> None:
    assert signed_parts(amount, sizes) == signed


@pytest.mark.parametrize("sizes", [[1200, 0], [-1200, 800]])
def test_a_size_must_be_more_than_zero(sizes: list[int]) -> None:
    with pytest.raises(ValueError) as raised:
        signed_parts(-2000, sizes)
    assert str(raised.value) == "each part's size must be more than zero"


@pytest.mark.parametrize(
    ("text", "part"),
    [
        ("12.00 Groceries", (1200, "Groceries")),
        ("  $8   Home & Garden  ", (800, "Home & Garden")),
        ("1,234.56\tRent & Mortgage", (123456, "Rent & Mortgage")),
        ("-12.00 Groceries", (-1200, "Groceries")),
    ],
)
def test_a_part_as_typed(text: str, part: tuple[int, str]) -> None:
    assert parse_part(text) == part


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("12.00", "a part is a size and a category, such as 12.00 Groceries"),
        ("   ", "a part is a size and a category, such as 12.00 Groceries"),
        ("twelve Groceries", "invalid money text"),
    ],
)
def test_a_part_that_is_refused(text: str, message: str) -> None:
    with pytest.raises(ValueError) as raised:
        parse_part(text)
    assert str(raised.value) == message
```

`tests/integration/test_split_reports.py`

```python
from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.search import TransactionQuery, search_transactions
from finances.analysis.spending import load_flows, spending_report
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, set_category_by_hand, set_split
from finances.domain.spending import SpendingLine

FIRST, LAST = date(2026, 5, 1), date(2026, 5, 31)


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    """-$20.00 at FOOBAR GROCERY (1) split into Groceries -$12.00 and Home & Garden -$8.00;
    -$5.00 at ACME COFFEE (2) set to Dining by hand."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        for number, (day, cents, description) in enumerate(
            ((3, -2000, "FOOBAR GROCERY"), (4, -500, "ACME COFFEE")), start=1
        ):
            opened.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        opened.flush()
        set_split(opened, 1, [(-1200, "Groceries"), (-800, "Home & Garden")])
        set_category_by_hand(opened, 2, "Dining")
        yield opened


def test_flows_whole_and_in_parts(session: Session) -> None:
    whole = load_flows(session, FIRST, LAST)
    assert [(f.amount_cents, f.category, f.group) for f in whole] == [
        (-2000, "Split", "Split"),
        (-500, "Dining", "Food"),
    ]
    parts = load_flows(session, FIRST, LAST, parts=True)
    assert [(f.amount_cents, f.category, f.group, f.merchant) for f in parts] == [
        (-1200, "Groceries", "Food", "FOOBAR GROCERY"),
        (-800, "Home & Garden", "Home", "FOOBAR GROCERY"),
        (-500, "Dining", "Food", "ACME COFFEE"),
    ]


def test_spending_counts_the_parts(session: Session) -> None:
    assert spending_report(session, FIRST, LAST).lines == [
        SpendingLine("Groceries", 1200, 1, 0),
        SpendingLine("Home & Garden", 800, 1, 0),
        SpendingLine("Dining", 500, 1, 0),
    ]
    assert spending_report(session, FIRST, LAST, "group").lines == [
        SpendingLine("Food", 1700, 2, 0),
        SpendingLine("Home", 800, 1, 0),
    ]


def test_a_drill_down_finds_the_part(session: Session) -> None:
    found = search_transactions(session, TransactionQuery(category="groceries"))
    assert [(f.transaction.id, f.flow.amount_cents, f.flow.category) for f in found] == [
        (1, -1200, "Groceries"),
    ]
    every = search_transactions(session, TransactionQuery())
    assert [(f.transaction.id, f.flow.amount_cents, f.flow.category) for f in every] == [
        (2, -500, "Dining"),
        (1, -1200, "Groceries"),
        (1, -800, "Home & Garden"),
    ]
```

`tests/e2e/test_cli_splits.py`

```python
from datetime import date

import pytest

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule
from tests.support import failed_cleanly, run, table_rows

PARTS = ("--part", "12.00 groceries", "--part", "$8 Home & Garden")


@pytest.fixture
def card(tmp_settings: Settings) -> Settings:
    """-$20.00 at FOOBAR GROCERY (1) with no category; -$5.00 at ACME COFFEE (2) put in
    Coffee & Dessert by a rule."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-2000, "FOOBAR GROCERY"), (-500, "ACME COFFEE")), start=1
        ):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, number),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        create_rule(session, "ACME", "Coffee & Dessert")
        categorize(session)
    engine.dispose()
    return tmp_settings


def test_splitting(card: Settings) -> None:
    result = run("transactions", "split", "--id", "1", *PARTS)
    assert (result.exit_code, result.stdout) == (0, "Transaction 1: split into 2 parts.\n")
    assert table_rows(run("transactions", "parts", "--id", "1").stdout) == [
        ["Part", "Amount", "Category"],
        ["1", "-$12.00", "Groceries"],
        ["2", "-$8.00", "Home & Garden"],
    ]


def test_unsplitting(card: Settings) -> None:
    run("transactions", "split", "--id", "1", *PARTS)
    result = run("transactions", "unsplit", "--id", "1")
    assert (result.exit_code, result.stdout) == (
        0,
        "Transaction 1: split removed.\n"
        "Categorized 2 transactions: 0 changed, 1 without a category.\n",
    )
    assert run("transactions", "parts", "--id", "1").stdout == "Transaction 1 is not split.\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ("split", "--id", "1", "--part", "12.00 Groceries", "--part", "9.00 Dining"),
            "the parts must add up to the transaction",
        ),
        (
            ("split", "--id", "1", "--part", "12.00", "--part", "8.00 Dining"),
            "a part is a size and a category, such as 12.00 Groceries",
        ),
        (
            ("split", "--id", "1", "--part", "twelve Groceries", "--part", "8.00 Dining"),
            "invalid money text",
        ),
        (
            ("split", "--id", "1", "--part", "-12.00 Groceries", "--part", "8.00 Dining"),
            "each part's size must be more than zero",
        ),
        (("split", "--id", "9", *PARTS), "transaction not found"),
        (("unsplit", "--id", "2"), "the transaction is not split"),
        (("parts", "--id", "9"), "transaction not found"),
    ],
)
def test_refused(card: Settings, args: tuple[str, ...], message: str) -> None:
    assert failed_cleanly(run("transactions", *args), message)
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_split_reports_more.py`:

- a -$20.00 purchase split into Groceries -$12.00 and Transfer -$8.00: `month_report` counts $12.00 spent (the whole would count $20.00), and the transfer part has the kind `transfer`;
- a budget for Groceries counts the -$12.00 part of a split purchase;
- the account page's spending by category shows the parts;
- `spikes` in `insights_report` sees a Groceries part: a month whose Groceries spending is only parts of split purchases, over earlier months with less, built from `spikes`' own thresholds;
- `STREAMFLIX` for -$15.00 on the 5th of four months running, the last split into Subscriptions & Digital -$10.00 and Entertainment & Events -$5.00: `recurring_charges` gives one series of $15.00 a month (parts would break it);
- `merchant_stats` counts a split purchase once;
- search with `kind` matches each part by its own kind; `limit=2` on a three-part split returns its first two parts;
- `list_transactions` (the MCP tool) gives a split transaction as two items with the same id and the parts' amounts; the Transactions page shows the parts' amounts;
- `split_by_sizes(9, [(0, "Dining"), (100, "Groceries")])` gives `transaction not found` (the order); a pending transaction with sizes that do not add up gives the pending message.

## Rules for this phase

- Money is integer cents; a part is signed as its transaction is, and its sizes are typed without a sign. `signed_parts` and `parse_part` take and return integers only.
- Which flows a report reads is decided in `analysis`; no view, command, route, or tool chooses.
- Messages are constant and echo no amount, description, or category.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 24 tests; at least N + 24 passed in all;
- `git diff --stat HEAD -- tests` lists only the file of the given diff;
- `git grep -n "parts=True" -- src/finances/analysis/recurring.py src/finances/analysis/forecast.py src/finances/analysis/names.py src/finances/analysis/refunds.py src/finances/views src/finances/cli src/finances/web src/finances/mcp_server` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.splits --cov=finances.db.repositories --cov=finances.analysis.spending --cov=finances.analysis.months --cov=finances.analysis.budgets --cov=finances.analysis.account_page --cov=finances.analysis.insights --cov=finances.analysis.search --cov=finances.views.transactions --cov=finances.mcp_server --cov=finances.cli.splits --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 28e: splits in the reports and the terminal (YYYY-MM-DD)`.
