# Phase 29b: shared expenses in the terminal

## Goal

29a's shares and settlements reach the terminal. After this phase `fin shared` shares a transaction (half by default, or a typed share), lists the shares, says who owes whom, records a settlement (today unless a date is given), lists and deletes settlements, and unshares a transaction. Every number and refusal comes from 29a; this phase adds the commands and their texts.

The web half (a Shared page and a share card on a transaction's page) is Phase 29c.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-29a-shared-expenses-stored.md`
- `src/finances/db/repositories/shared.py`, `src/finances/domain/shared.py`, `src/finances/analysis/shared.py`
- `src/finances/cli/budgets.py` (a command group reading money with `parse_money`), `src/finances/cli/health.py` (a date option and `clock.today()`), `src/finances/cli/common.py`, `src/finances/cli/main.py`

## Starting state

N is `3713` when Phase 29a is the last phase built. The newest migration is `0020`; this phase adds none.

## Scope

| Path | What changes |
|---|---|
| `src/finances/views/shared.py` (new) | the texts and rows (R2) |
| `src/finances/cli/shared.py` (new), `src/finances/cli/main.py` | `fin shared` and its seven commands (R1, R3 to R9) |
| `tests/e2e/test_cli_shared.py` | new: given |
| `tests/unit/test_shared_views.py`, `tests/e2e/test_cli_shared_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Any page or form (29c); an MCP tool for shares.
- Showing a share's transaction (date, description) in `fin shared list`; filtering shares or settlements.
- Any change to 29a's repository or rules.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/views/shared.py
def share_text(share: Share) -> str: ...
# "Transaction 1: Alex owes Sam $10.00." for owed_cents > 0 (and 0);
# "Transaction 2: Sam owes Alex $2.00." for owed_cents < 0 (the payer owes the debtor)

@dataclass(frozen=True)
class ShareRow:
    id: str
    paid_by: str
    owes: str
    owed: str   # format_cents(owed_cents), signed

def share_rows(shares: list[Share]) -> list[ShareRow]: ...
def owed_text(owed: Owed) -> str: ...            # "Alex owes Sam $6.00."
def settlement_text(settlement: Settlement) -> str: ...  # "Alex paid Sam $4.00 on 2026-05-20."

@dataclass(frozen=True)
class SettlementRow:
    id: str
    date: str
    payer: str
    payee: str
    amount: str

def settlement_rows(settlements: list[Settlement]) -> list[SettlementRow]: ...
```

`fin shared` is a new Typer app, `shared_app` (help `Shared expenses: who owes whom.`, `no_args_is_help=True`), registered in `cli/main.py` with `app.add_typer(shared_app, name="shared")`:

| Command | Options | Calls | Prints |
|---|---|---|---|
| `add` | `--id INT`, `--with NAME`, `--paid-by NAME` (default `""`), `--share MONEY` (default `""`: half) | `share_transaction(session, id, with, payer=paid_by, size_cents=...)` | `share_text` |
| `remove` | `--id INT` | `unshare_transaction` | `Transaction 1: no longer shared.` |
| `list` | none | `list_shares` | a table, headings `ID`, `Paid by`, `Owes`, `Owed`, rows `share_rows`; or `No shared transactions.` |
| `owed` | none | `owed_report` | one `owed_text` line per pair; or `Nobody owes anybody.` |
| `settle` | `--from NAME`, `--to NAME`, `--amount MONEY`, `--date YYYY-MM-DD` (default today) | `record_settlement` | `settlement_text` |
| `settlements` | none | `list_settlements` | a table, headings `ID`, `Date`, `From`, `To`, `Amount`, rows `settlement_rows`; or `No settlements.` |
| `delete-settlement` | `--id INT` | `delete_settlement` | `Deleted settlement 1: ` then `settlement_text` |

## Requirements

### The texts

- **R1.** `fin shared` as designed. Each command calls `require_current_schema()` first. A refusal is `fail(message)`: `Error: <message>` on stderr, exit code 1, nothing on stdout, nothing stored.
- **R2.** `views/shared.py` as designed: every amount through `format_cents`; `share_text` names the debtor as owing when `owed_cents` is zero or more, and the payer as owing the debtor `-owed_cents` when it is less than zero; `settlement_text` gives the day as `YYYY-MM-DD`.

### The commands

- **R3.** `add` reads `--share` with `parse_money` when it is not blank, passing on its refusal (`invalid money text`), and passes the cents as `size_cents`; with no `--share` it passes `size_cents=None`, so 29a's half applies. `--paid-by` goes to `payer`, so a joint purchase can be shared. Every refusal of `share_transaction` reaches the command.
- **R4.** `remove` as designed; `unshare_transaction`'s refusals reach it.
- **R5.** `list` as designed, the rows in `list_shares`' order.
- **R6.** `owed` as designed, the lines in `owed_report`'s order.
- **R7.** `settle` reads `--amount` with `parse_money` (its refusal passed on), takes `--date` with `formats=["%Y-%m-%d"]`, and uses `clock.today()` (through `import finances.clock as clock`, so a test can replace it) when no date is given. `record_settlement`'s refusals reach it.
- **R8.** `settlements` as designed, in `list_settlements`' order.
- **R9.** `delete-settlement` as designed; `delete_settlement`'s refusal reaches it.

## Given tests

14 tests in one file. Do not change them.

`tests/e2e/test_cli_shared.py`

```python
from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_person, set_account_owner
from finances.domain.shared import SIZE
from tests.support import failed_cleanly, run, table_rows

SETTLE = ("--from", "Alex", "--to", "Sam", "--amount", "4.00", "--date", "2026-05-20")


@pytest.fixture
def card(tmp_settings: Settings) -> Settings:
    """Sam and Alex; a card owned by Sam with a purchase of -$20.01 (1) and a refund of
    $6.00 (2)."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        sam = create_person(session, "Sam")
        create_person(session, "Alex")
        account = create_account(session, "Test Card", "Test Bank", "credit_card")
        set_account_owner(session, account.id, sam.id)
        for number, (day, cents) in enumerate(((1, -2001), (3, 600)), start=1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description="FOOBAR GROCERY",
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    return tmp_settings


def test_sharing(card: Settings) -> None:
    half = run("shared", "add", "--id", "1", "--with", "alex")
    assert (half.exit_code, half.stdout) == (0, "Transaction 1: Alex owes Sam $10.00.\n")
    refund = run("shared", "add", "--id", "2", "--with", "Alex", "--share", "2.00")
    assert (refund.exit_code, refund.stdout) == (0, "Transaction 2: Sam owes Alex $2.00.\n")
    assert table_rows(run("shared", "list").stdout) == [
        ["ID", "Paid by", "Owes", "Owed"],
        ["1", "Sam", "Alex", "$10.00"],
        ["2", "Sam", "Alex", "-$2.00"],
    ]
    assert run("shared", "owed").stdout == "Alex owes Sam $8.00.\n"


def test_settling(card: Settings) -> None:
    run("shared", "add", "--id", "1", "--with", "Alex")
    settled = run("shared", "settle", *SETTLE)
    assert (settled.exit_code, settled.stdout) == (0, "Alex paid Sam $4.00 on 2026-05-20.\n")
    assert table_rows(run("shared", "settlements").stdout) == [
        ["ID", "Date", "From", "To", "Amount"],
        ["1", "2026-05-20", "Alex", "Sam", "$4.00"],
    ]
    assert run("shared", "owed").stdout == "Alex owes Sam $6.00.\n"
    deleted = run("shared", "delete-settlement", "--id", "1")
    assert (deleted.exit_code, deleted.stdout) == (
        0,
        "Deleted settlement 1: Alex paid Sam $4.00 on 2026-05-20.\n",
    )
    assert run("shared", "settlements").stdout == "No settlements.\n"


def test_a_settlement_today(card: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 6, 1))
    settled = run("shared", "settle", "--from", "Alex", "--to", "Sam", "--amount", "1")
    assert settled.stdout == "Alex paid Sam $1.00 on 2026-06-01.\n"


def test_unsharing(card: Settings) -> None:
    run("shared", "add", "--id", "1", "--with", "Alex")
    removed = run("shared", "remove", "--id", "1")
    assert (removed.exit_code, removed.stdout) == (0, "Transaction 1: no longer shared.\n")
    assert run("shared", "list").stdout == "No shared transactions.\n"
    assert run("shared", "owed").stdout == "Nobody owes anybody.\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("add", "--id", "9", "--with", "Alex"), "transaction not found"),
        (("add", "--id", "1", "--with", "Kai"), "person not found"),
        (("add", "--id", "1", "--with", "Sam"), "a person cannot owe themselves"),
        (("add", "--id", "1", "--with", "Alex", "--share", "30.00"), SIZE),
        (("add", "--id", "1", "--with", "Alex", "--share", "ten"), "invalid money text"),
        (("remove", "--id", "1"), "the transaction is not shared"),
        (
            ("settle", "--from", "Alex", "--to", "alex", "--amount", "1"),
            "a person cannot pay themselves",
        ),
        (
            ("settle", "--from", "Alex", "--to", "Sam", "--amount", "0"),
            "a settlement must be more than zero",
        ),
        (("settle", "--from", "Alex", "--to", "Sam", "--amount", "x"), "invalid money text"),
        (("delete-settlement", "--id", "9"), "settlement not found"),
    ],
)
def test_refused(card: Settings, args: tuple[str, ...], message: str) -> None:
    assert failed_cleanly(run("shared", *args), message)
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/unit/test_shared_views.py`:

- `share_text` of a share owing 0 (a 1-cent purchase) names the debtor; of -200 names the payer owing $2.00;
- `owed_text`, `settlement_text`, `share_rows`, and `settlement_rows` of hand-made values, every field compared.

And in the given file's style, in `tests/e2e/test_cli_shared_more.py`:

- `add --paid-by Sam` on a joint purchase is stored with Sam as the payer; without it, the joint message;
- `add` on a pending purchase gives `a pending transaction cannot be shared`;
- a database that is not migrated gives the CLI's not-migrated message for `fin shared list`.

## Rules for this phase

- Money is integer cents: amounts are typed as sizes and read with `parse_money`; the commands do no arithmetic.
- `cli/shared.py` parses options, calls one function, and prints what `views/shared.py` gives; no rule of 29a is repeated in either.
- Refusal messages are 29a's or `parse_money`'s, constant and echoing nothing typed.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file above, 14 tests; at least N + 14 passed in all;
- `git diff --stat HEAD -- tests` prints nothing (no earlier test changes);
- `git grep -n "half_share\|signed_share\|balances(\|SharedExpenseRow\|SettlementRow" -- src/finances/cli src/finances/views` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.cli.shared --cov=finances.views.shared --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 29b: shared expenses in the terminal (YYYY-MM-DD)`.
