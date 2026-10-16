# Phase 25: data health

## Goal

The household is told when its data is out of date or incomplete, before it trusts a report. After this phase `fin health` lists every problem with what to do about it, or `No problems found.`:

| Kind | When | Problem (in full below) |
|---|---|---|
| `backup` | no backup, or the newest is more than 2 days old | `No backup yet.` / `The newest backup is D days old (taken DATE).` |
| `sync` | an active account mapped to SimpleFIN was never pulled, or not for more than 3 days | `Mapped to SimpleFIN but never synced.` / `No SimpleFIN pull for D days (last on DATE).` |
| `drift` | the newest pull with a balance found the stored balance differs from SimpleFIN's | `The balance differs from SimpleFIN's by $X on DATE.` |
| `statements` | an active account not on SimpleFIN has no data at all, or its newest statement ended more than 45 days ago | `No statements yet.` / `The newest statement ends DATE (D days ago).` |
| `gap` | days between two statements of an active account that neither covers (Phase 16g) | `No statement covers START to END.` |

SimpleFIN access that was revoked is not stored when a sync fails, so it shows as a `sync` problem, whose advice is to sync and relink if that fails. Closed accounts are never checked. The dashboard (16h) shows the same list.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/db/repositories.py`: `list_accounts`, `list_feed_accounts`, `latest_feed_pull`, `list_statements`, `statement_periods`, `account_data_span`
- `src/finances/domain/periods.py` (`statement_gaps`), `src/finances/db/backup.py` (`list_backups`, `taken_at`)
- `src/finances/cli/reports.py` (`fin recurring --as-of`), `tests/support.py`

## Starting state

N is `2763` when Phase 16g is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/health.py` | new (R1 to R4) |
| `src/finances/analysis/health.py` | new (R5) |
| `src/finances/views/health.py` | new (R6) |
| `src/finances/cli/health.py` | new (R7) |
| `src/finances/cli/main.py` | registers `health` |
| `tests/unit/test_health.py`, `tests/e2e/test_cli_health.py` | new: given |
| `tests/integration/test_health_facts.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- A web page or dashboard block (16h); `fin doctor` changes; alerts or notifications.
- Storing sync failures, or telling revoked access apart from a Mac that was off.
- Thresholds set by the household (they are constants for now).

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/health.py  (standard library and finances.domain only)
BACKUP_STALE_DAYS = 2
SYNC_STALE_DAYS = 3
STATEMENT_STALE_DAYS = 45
KINDS = ("backup", "sync", "drift", "statements", "gap")


@dataclass(frozen=True)
class AccountFacts:
    name: str
    mapped: bool                       # mapped to a SimpleFIN account under any link
    last_pull: date | None             # UTC date of the newest pull
    drift_cents: int | None            # of the newest pull with a balance
    drift_date: date | None            # that pull's balance date
    newest_statement_end: date | None
    has_data: bool                     # account_data_span is not None
    gaps: tuple[tuple[date, date], ...] = ()


@dataclass(frozen=True)
class Problem:
    kind: str
    account: str  # "" for a backup problem
    detail: str
    action: str


def health_problems(
    accounts: Iterable[AccountFacts], newest_backup: date | None, as_of: date
) -> list[Problem]: ...
```

```python
# src/finances/analysis/health.py
def account_facts(session: Session) -> list[AccountFacts]: ...
def gather_health(session: Session, backup_folder: Path, as_of: date) -> list[Problem]: ...

# src/finances/views/health.py
@dataclass(frozen=True)
class HealthRow:
    kind: str
    account: str
    problem: str
    action: str


def health_rows(problems: list[Problem]) -> list[HealthRow]: ...
def health_summary(problems: list[Problem]) -> str: ...  # "Problems: N." or "No problems found."
```

Texts, in full (D is a whole number of days, DATE an ISO date, `$X` through `format_cents`):

| Kind | Detail | Action |
|---|---|---|
| `backup` | `No backup yet.`; `The newest backup is D days old (taken DATE).` | `Run fin backup run, or press Back up now on the Backups page.` |
| `sync` | `Mapped to SimpleFIN but never synced.`; `No SimpleFIN pull for D days (last on DATE).` | `Run fin sync run; if it fails, link SimpleFIN again (docs/sync-setup.md).` |
| `drift` | `The balance differs from SimpleFIN's by $X on DATE.` | `Look for a missing or extra transaction, or import the statement for that period.` |
| `statements` | `No statements yet.`; `The newest statement ends DATE (D days ago).` | `Upload the newest statement on the Statements page, or run fin import statement.` |
| `gap` | `No statement covers START to END.` | `Upload the statement for those days.` |

## Requirements

### Part 1: the rules (pure)

- **R1.** A `backup` problem when `newest_backup` is `None`, or when `as_of` minus it is more than `BACKUP_STALE_DAYS` days.
- **R2.** For a `mapped` account: a `sync` problem when `last_pull` is `None`, or `as_of` minus it is more than `SYNC_STALE_DAYS`; a `drift` problem when `drift_cents` is neither `None` nor 0. A mapped account has no `statements` problem.
- **R3.** For an account that is not mapped: a `statements` problem when `newest_statement_end` is `None` and `has_data` is false, or when `as_of` minus `newest_statement_end` is more than `STATEMENT_STALE_DAYS`. Any account: one `gap` problem per gap.
- **R4.** `health_problems` returns the problems ordered by kind (`KINDS` order), then account ignoring case, then account, then detail.

### Part 2: gathering and the terminal

- **R5.** `account_facts` gives one `AccountFacts` per **active** account (`list_accounts`, in its order): `mapped` from `list_feed_accounts` (every link); `last_pull` the UTC date of `latest_feed_pull`'s `pulled_at`; `drift_cents` and `drift_date` from `latest_feed_pull(..., with_balance=True)`; `newest_statement_end` the latest `period_end` of its statements; `has_data` from `account_data_span`; `gaps` from `statement_gaps(statement_periods(...))`. `gather_health` adds the newest backup's day (`taken_at` of `list_backups(backup_folder)`'s first, as a UTC date) and returns `health_problems`.
- **R6.** `health_rows` gives each problem's four texts; `health_summary` is `Problems: N.` or, with none, `No problems found.`
- **R7.** `fin health` takes `--as-of` (`YYYY-MM-DD`, read as `fin recurring` reads it; today when not given), checks the schema, and calls `gather_health` with `effective_backup_dir`, in one session. With problems it prints a table with columns `Kind`, `Account`, `Problem`, `What to do`, then the summary; with none, only the summary. It exits with code 0 either way.

## Given tests

22 tests in two files; the end-to-end file imports from `tests/support.py`.

`tests/unit/test_health.py`

```python
from datetime import date

import pytest

from finances.domain.health import (
    BACKUP_STALE_DAYS,
    KINDS,
    STATEMENT_STALE_DAYS,
    SYNC_STALE_DAYS,
    AccountFacts,
    Problem,
    health_problems,
)

AS_OF = date(2026, 5, 20)
BACKUP = "Run fin backup run, or press Back up now on the Backups page."
SYNC = "Run fin sync run; if it fails, link SimpleFIN again (docs/sync-setup.md)."
DRIFT = "Look for a missing or extra transaction, or import the statement for that period."
STATEMENTS = "Upload the newest statement on the Statements page, or run fin import statement."
GAP = "Upload the statement for those days."


def facts(name: str = "Test Card", **changes) -> AccountFacts:
    values = {
        "name": name,
        "mapped": False,
        "last_pull": None,
        "drift_cents": None,
        "drift_date": None,
        "newest_statement_end": date(2026, 5, 1),
        "has_data": True,
        "gaps": (),
    }
    values.update(changes)
    return AccountFacts(**values)


def test_the_limits_and_kinds() -> None:
    assert (BACKUP_STALE_DAYS, SYNC_STALE_DAYS, STATEMENT_STALE_DAYS) == (2, 3, 45)
    assert KINDS == ("backup", "sync", "drift", "statements", "gap")


def test_nothing_wrong() -> None:
    assert health_problems([facts()], date(2026, 5, 19), AS_OF) == []
    assert health_problems([], date(2026, 5, 18), AS_OF) == []


@pytest.mark.parametrize(
    ("newest", "problems"),
    [
        (None, [Problem("backup", "", "No backup yet.", BACKUP)]),
        (date(2026, 5, 18), []),
        (
            date(2026, 5, 17),
            [Problem("backup", "", "The newest backup is 3 days old (taken 2026-05-17).", BACKUP)],
        ),
    ],
)
def test_backups(newest: date | None, problems: list[Problem]) -> None:
    assert health_problems([], newest, AS_OF) == problems


@pytest.mark.parametrize(
    ("changes", "problems"),
    [
        (
            {"mapped": True},
            [Problem("sync", "Test Card", "Mapped to SimpleFIN but never synced.", SYNC)],
        ),
        ({"mapped": True, "last_pull": date(2026, 5, 17)}, []),
        (
            {"mapped": True, "last_pull": date(2026, 5, 16)},
            [
                Problem(
                    "sync", "Test Card", "No SimpleFIN pull for 4 days (last on 2026-05-16).", SYNC
                )
            ],
        ),
        (
            {"mapped": True, "last_pull": AS_OF, "drift_cents": -1234, "drift_date": AS_OF},
            [
                Problem(
                    "drift",
                    "Test Card",
                    "The balance differs from SimpleFIN's by -$12.34 on 2026-05-20.",
                    DRIFT,
                )
            ],
        ),
        ({"mapped": True, "last_pull": AS_OF, "drift_cents": 0, "drift_date": AS_OF}, []),
        ({"mapped": True, "last_pull": AS_OF, "newest_statement_end": None}, []),
    ],
    ids=["never-synced", "three-days", "four-days", "drift", "no-drift", "no-statements-needed"],
)
def test_accounts_on_simplefin(changes: dict, problems: list[Problem]) -> None:
    assert health_problems([facts(**changes)], AS_OF, AS_OF) == problems


@pytest.mark.parametrize(
    ("changes", "problems"),
    [
        ({"newest_statement_end": date(2026, 4, 5)}, []),
        (
            {"newest_statement_end": date(2026, 4, 4)},
            [
                Problem(
                    "statements",
                    "Test Card",
                    "The newest statement ends 2026-04-04 (46 days ago).",
                    STATEMENTS,
                )
            ],
        ),
        (
            {"newest_statement_end": None, "has_data": False},
            [Problem("statements", "Test Card", "No statements yet.", STATEMENTS)],
        ),
        ({"newest_statement_end": None, "has_data": True}, []),
        (
            {"gaps": ((date(2026, 2, 1), date(2026, 2, 28)),)},
            [Problem("gap", "Test Card", "No statement covers 2026-02-01 to 2026-02-28.", GAP)],
        ),
    ],
    ids=["45-days", "46-days", "no-data", "data-without-statements", "a-gap"],
)
def test_accounts_on_statements(changes: dict, problems: list[Problem]) -> None:
    assert health_problems([facts(**changes)], AS_OF, AS_OF) == problems


def test_problems_come_by_kind_then_account_then_detail() -> None:
    found = health_problems(
        [
            facts(
                "beta",
                gaps=((date(2026, 3, 1), date(2026, 3, 5)), (date(2026, 1, 1), date(2026, 1, 9))),
            ),
            facts("Alpha", newest_statement_end=None, has_data=False),
            facts(
                "Card",
                mapped=True,
                last_pull=date(2026, 5, 1),
                drift_cents=500,
                drift_date=date(2026, 5, 1),
            ),
        ],
        None,
        AS_OF,
    )
    assert [(problem.kind, problem.account, problem.detail) for problem in found] == [
        ("backup", "", "No backup yet."),
        ("sync", "Card", "No SimpleFIN pull for 19 days (last on 2026-05-01)."),
        ("drift", "Card", "The balance differs from SimpleFIN's by $5.00 on 2026-05-01."),
        ("statements", "Alpha", "No statements yet."),
        ("gap", "beta", "No statement covers 2026-01-01 to 2026-01-09."),
        ("gap", "beta", "No statement covers 2026-03-01 to 2026-03-05."),
    ]
```

`tests/e2e/test_cli_health.py`

```python
from datetime import UTC, date, datetime

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import FeedPullRow
from finances.db.repositories import (
    create_account,
    create_statement,
    map_feed_account,
    set_account_active,
)
from tests.support import CLI_NOT_MIGRATED, plain_lines, run, table_rows

AS_OF = ("--as-of", "2026-05-20")
HEADINGS = ["Kind", "Account", "Problem", "What to do"]
BACKUP = [
    "backup",
    "",
    "No backup yet.",
    "Run fin backup run, or press Back up now on the Backups page.",
]
ACCOUNTS = [
    [
        "sync",
        "Test Card",
        "No SimpleFIN pull for 10 days (last on 2026-05-10).",
        "Run fin sync run; if it fails, link SimpleFIN again (docs/sync-setup.md).",
    ],
    [
        "drift",
        "Test Card",
        "The balance differs from SimpleFIN's by -$12.34 on 2026-05-10.",
        "Look for a missing or extra transaction, or import the statement for that period.",
    ],
    [
        "statements",
        "Test Checking",
        "The newest statement ends 2026-03-31 (50 days ago).",
        "Upload the newest statement on the Statements page, or run fin import statement.",
    ],
    [
        "statements",
        "Test Savings",
        "No statements yet.",
        "Upload the newest statement on the Statements page, or run fin import statement.",
    ],
    [
        "gap",
        "Test Checking",
        "No statement covers 2026-02-01 to 2026-02-28.",
        "Upload the statement for those days.",
    ],
]


def statement(session, account, number: int, start: date, end: date) -> None:
    create_statement(
        session,
        account_id=account.id,
        source_filename=f"statement-{number}.pdf",
        file_sha256=f"s{number:02d}".ljust(64, "0"),
        parser_name="test",
        period_start=start,
        period_end=end,
        opening_balance_cents=0,
        closing_balance_cents=0,
        lines_parsed=0,
        rows_inserted=0,
        rows_duplicate=0,
    )


@pytest.fixture
def household(tmp_settings: Settings) -> Settings:
    """Test Card on SimpleFIN, last pulled 10 May with drift; Test Checking with statements for
    January and March; Test Savings with nothing; Old Card closed with nothing; no backup."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        create_account(session, "Test Savings", "Test Bank", "savings")
        old = create_account(session, "Old Card", "Test Bank", "credit_card")
        set_account_active(session, old.id, False)
        map_feed_account(session, card.id, "ACT-1")
        session.add(
            FeedPullRow(
                account_id=card.id,
                inserted=0,
                updated=0,
                removed=0,
                unchanged=0,
                feed_total_cents=0,
                balance_cents=-50000,
                balance_date=date(2026, 5, 10),
                drift_cents=-1234,
                pulled_at=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
            )
        )
        statement(session, checking, 1, date(2026, 1, 1), date(2026, 1, 31))
        statement(session, checking, 2, date(2026, 3, 1), date(2026, 3, 31))
    engine.dispose()
    return tmp_settings


def test_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = run("health", *AS_OF)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


def test_every_kind_of_problem(household: Settings) -> None:
    result = run("health", *AS_OF)
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [HEADINGS, BACKUP, *ACCOUNTS]
    assert plain_lines(result.stdout) == ["Problems: 6."]


def test_a_recent_backup_is_no_problem(household: Settings) -> None:
    folder = household.effective_backup_dir
    folder.mkdir(parents=True)
    (folder / "finances-20260519-020000.db").write_bytes(b"")
    assert table_rows(run("health", *AS_OF).stdout) == [HEADINGS, *ACCOUNTS]


def test_no_problems(tmp_settings: Settings) -> None:
    assert run("db", "upgrade").exit_code == 0
    folder = tmp_settings.effective_backup_dir
    folder.mkdir(parents=True)
    (folder / "finances-20260520-020000.db").write_bytes(b"")
    result = run("health", *AS_OF)
    assert (result.exit_code, result.stdout) == (0, "No problems found.\n")


def test_a_day_that_is_not_one(household: Settings) -> None:
    result = run("health", "--as-of", "2026-02-30")
    assert result.exit_code == 2
    assert "'--as-of'" in result.stderr
```

## Tests to write

`tests/integration/test_health_facts.py`:

- `account_facts`: an account mapped under a second link; `last_pull` from a pull late in the evening UTC (the UTC date, not the local one); drift taken from the newest pull **with** a balance when a later pull has none; a closed account left out;
- `gather_health` with backup files that are not backups in the folder (ignored);
- `fin health` without `--as-of` uses today.

## Rules for this phase

- `domain/health.py` imports only the standard library and `finances.domain`.
- **Thin.** The command calls `gather_health` and the views; no query or rule in `cli/`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_health.py tests/e2e/test_cli_health.py`, 22 tests;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.health --cov=finances.analysis.health --cov=finances.views.health --cov=finances.cli.health --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` and `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|timedelta|health_problems\(" -- src/finances/cli/health.py`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 25: data health (YYYY-MM-DD)`.
