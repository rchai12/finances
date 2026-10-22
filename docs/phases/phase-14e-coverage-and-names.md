# Phase 14e: data coverage and finding merchants

## Goal

The last read tools of Phase 14. After this phase the MCP server has two more:

- `data_coverage`: for each open account, how far its data can be trusted (the days it has data, the periods imported statements audit and the gaps between them, whether SimpleFIN feeds it, its last pull and newest balance drift), and the data problems Phase 25's health check finds, so the agent can say when an answer rests on stale or partial months;
- `find_merchants`: the merchant and category names closest to a phrase ("cofee", "paychek", "that coffee place"), so the agent can turn the household's words into names the other tools accept.

Both need a little new logic, which goes where the layering says: two pure functions in `domain`, two loaders in `analysis`, and two thin tools. Matching is the standard library's `difflib`, with no index and no new dependency (the roadmap's decision on vector search stands).

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-14a-mcp-server.md` (the SDK facts, `reading()`, the logging rule), `docs/phases/phase-14d-work-queues.md`
- `src/finances/analysis/health.py` (`account_facts`, `gather_health`), `src/finances/domain/health.py` (`AccountFacts`, `Problem`), `src/finances/domain/periods.py` (`statement_gaps`), `src/finances/domain/merchants.py`, `src/finances/analysis/spending.py` (`load_flows`)
- `src/finances/db/repositories.py`: `list_accounts`, `account_data_span`, `statement_periods`, `list_categories`

## Starting state

N is `3226` when Phase 14d is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/periods.py` | `joined_periods` (R1) |
| `src/finances/domain/merchants.py` | `MATCH_THRESHOLD`, `NameMatch`, `match_score`, `closest_names` (R2, R3) |
| `src/finances/analysis/coverage.py` | new (R4) |
| `src/finances/analysis/names.py` | new (R5) |
| `src/finances/mcp_server/tools.py`, `src/finances/mcp_server/server.py` | two tools and their descriptions (R6 to R8) |
| five earlier MCP test files | the given diff (R9) |
| `tests/unit/test_name_matching.py`, `tests/integration/test_mcp_coverage.py` | new: given |
| `tests/integration/test_mcp_coverage_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Embeddings, a vector index, or any new dependency; aliases between merchants (Phase 28).
- A web page or command for coverage or matching; any write.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/periods.py
def joined_periods(periods: Iterable[tuple[date, date]]) -> list[tuple[date, date]]: ...

# src/finances/domain/merchants.py
MATCH_THRESHOLD = 75

@dataclass(frozen=True)
class NameMatch:
    name: str
    kind: str     # "merchant" or "category"
    score: int    # 0 to 100

def match_score(phrase: str, name: str) -> int: ...
def closest_names(
    phrase: str, candidates: Iterable[tuple[str, str]], limit: int = 5
) -> list[NameMatch]: ...

# src/finances/analysis/coverage.py
@dataclass(frozen=True)
class AccountCoverage:
    type: str                          # the account type's value
    facts: AccountFacts                # Phase 25's facts for the account
    span: tuple[date, date] | None     # account_data_span
    audited: list[tuple[date, date]]   # joined_periods of its statement periods

@dataclass(frozen=True)
class CoverageReport:
    as_of: date
    accounts: list[AccountCoverage]
    problems: list[Problem]

def coverage_report(session: Session, backup_folder: Path, as_of: date) -> CoverageReport: ...

# src/finances/analysis/names.py
def find_names(session: Session, phrase: str, limit: int) -> list[NameMatch]: ...

# src/finances/mcp_server/tools.py
def data_coverage() -> dict[str, Any]: ...
def find_merchants(phrase: str, limit: Annotated[int, Field(ge=1, le=20)] = 5) -> dict[str, Any]: ...
```

Descriptions, in `server.py`, exactly:

```python
DATA_COVERAGE_DESCRIPTION = (
    "How far the data can be trusted, as of today: for each open account its type, the first "
    "and last day with any data, the periods covered by imported statements (audited) and the "
    "gaps between them, the newest statement's end, whether SimpleFIN feeds it, its last pull, "
    "and the newest balance drift in integer cents with its day; and the data problems the app "
    "sees (kind, account, what is wrong, what to do). Use it before answering about a period "
    "that may be partial or stale."
)
FIND_MERCHANTS_DESCRIPTION = (
    "Merchant and category names that look like a phrase (a misspelling, part of a name, or a "
    "word such as coffee), best first, each with a score from 75 to 100, at most limit (1 to "
    "20, default 5). Use the names it returns with the other tools. No amounts."
)
```

## Requirements

### Part 1: the rules (pure)

- **R1.** `joined_periods` sorts the periods by their first day and joins each one that starts on or before the day after the previous run's last day; it returns the runs oldest first (`[]` for none). Two periods one day apart stay apart.
- **R2.** `match_score(phrase, name)`: both are normalized (split on white space, joined with single spaces, upper case); if either is then empty the score is 0. The **similarity** of two strings `a`, `b` is `(400 * M + T) // (2 * T)`, where `M` is the total size of `difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()` and `T = len(a) + len(b)` (that is, `200 * M / T` rounded half up). The score is the greatest of the similarity of the two whole strings and, for every word of the phrase of three letters or more, its similarity to every word of the name.
- **R3.** `closest_names` scores every candidate `(name, kind)`, keeps those scoring at least `MATCH_THRESHOLD`, orders them by score (highest first), then merchants before categories, then name ignoring case, then name, and returns the first `limit`.

### Part 2: loading

- **R4.** `coverage_report` covers the active accounts in `list_accounts`' order: for each, its type, the matching `account_facts` row (same order), `account_data_span`, and `joined_periods(statement_periods(...))`; and `gather_health(session, backup_folder, as_of)` as the problems.
- **R5.** `find_names` takes the distinct merchants of every posted flow (`load_flows` over all days) as `"merchant"` candidates and the names of the categories that have a group as `"category"` candidates, and returns `closest_names(phrase, candidates, limit)`.

### Part 3: the tools

- **R6.** `data_coverage` returns `coverage_report(session, get_settings().effective_backup_dir, clock.today())` as `{"as_of", "accounts": [...], "problems": [...]}`. Each account is `{"name", "type", "first_day", "last_day", "audited": [{"start", "end"}], "gaps": [{"start", "end"}], "newest_statement_end", "mapped", "last_pull", "drift_cents", "drift_date"}` (days ISO or null; `gaps` from the facts); each problem `{"kind", "account" (null when empty), "detail", "action"}`.
- **R7.** `find_merchants` refuses a phrase that is empty after stripping with `ToolError("give a phrase to look for")` and one longer than 100 characters with `ToolError("a phrase is at most 100 characters")`, neither echoing it; otherwise it returns `{"matches": [{"name", "kind", "score"}]}` from `find_names`.
- **R8.** `server.py` defines the two descriptions above and registers the two tools after 14d's, with `READ_ONLY` and `structured_output=True`. Nothing is logged.
- **R9.** Apply the given diff to five earlier test files: the tool lists and the description table gain the two tools; `find_merchants` joins the tools whose descriptions need not mention cents; 14d's `test_sixteen_read_only_tools` becomes `test_the_read_only_tools`. No other earlier test changes.

## Given tests

28 tests in two files. Every score was computed in a scratch copy with R2's formula and checked by hand (for example `cofee` against `COFFEE`: 5 matching letters of 11, so 91; `groceries` against `GROCERY`: 6 of 16, exactly 75, the threshold).

`tests/unit/test_name_matching.py`

```python
from datetime import date

import pytest

from finances.domain.merchants import MATCH_THRESHOLD, NameMatch, closest_names, match_score
from finances.domain.periods import joined_periods

CANDIDATES = [
    ("ACME COFFEE", "merchant"),
    ("ACME UTILITY", "merchant"),
    ("FOOBAR GROCERY", "merchant"),
    ("BAZ BOOKS", "merchant"),
    ("Coffee & Dessert", "category"),
    ("Groceries", "category"),
]


@pytest.mark.parametrize(
    ("phrase", "name", "score"),
    [
        ("cofee", "ACME COFFEE", 91),
        ("groceries", "FOOBAR GROCERY", 75),
        ("groceries", "Groceries", 100),
        ("that coffee place", "ACME UTILITY", 67),
        ("xyz", "BAZ BOOKS", 33),
        ("  Foobar   grocery ", "FOOBAR GROCERY", 100),
        ("ed", "Education", 36),
        ("   ", "BAZ BOOKS", 0),
    ],
)
def test_the_score(phrase: str, name: str, score: int) -> None:
    assert match_score(phrase, name) == score


def test_best_first_merchants_before_categories_on_a_tie() -> None:
    assert MATCH_THRESHOLD == 75
    assert closest_names("cofee", CANDIDATES) == [
        NameMatch("ACME COFFEE", "merchant", 91),
        NameMatch("Coffee & Dessert", "category", 91),
    ]
    assert closest_names("groceries", CANDIDATES) == [
        NameMatch("Groceries", "category", 100),
        NameMatch("FOOBAR GROCERY", "merchant", 75),
    ]


def test_a_tie_of_the_same_kind_goes_by_name() -> None:
    assert closest_names("acme", CANDIDATES) == [
        NameMatch("ACME COFFEE", "merchant", 100),
        NameMatch("ACME UTILITY", "merchant", 100),
    ]


def test_the_limit_and_nothing_close() -> None:
    assert closest_names("acme", CANDIDATES, limit=1) == [NameMatch("ACME COFFEE", "merchant", 100)]
    assert closest_names("xyz", CANDIDATES) == []
    assert closest_names("that coffee place", [("ACME UTILITY", "merchant")]) == []


@pytest.mark.parametrize(
    ("periods", "joined"),
    [
        ([], []),
        (
            [(date(2026, 4, 1), date(2026, 4, 30)), (date(2026, 1, 1), date(2026, 1, 31))],
            [(date(2026, 1, 1), date(2026, 1, 31)), (date(2026, 4, 1), date(2026, 4, 30))],
        ),
        (
            [(date(2026, 1, 1), date(2026, 1, 31)), (date(2026, 2, 1), date(2026, 2, 28))],
            [(date(2026, 1, 1), date(2026, 2, 28))],
        ),
        (
            [(date(2026, 1, 1), date(2026, 1, 31)), (date(2026, 1, 15), date(2026, 1, 20))],
            [(date(2026, 1, 1), date(2026, 1, 31))],
        ),
        (
            [(date(2026, 1, 1), date(2026, 1, 30)), (date(2026, 2, 1), date(2026, 2, 28))],
            [(date(2026, 1, 1), date(2026, 1, 30)), (date(2026, 2, 1), date(2026, 2, 28))],
        ),
    ],
    ids=["none", "out of order", "next day joins", "inside joins", "one day apart stays"],
)
def test_joined_periods(periods: list, joined: list) -> None:
    assert joined_periods(periods) == joined
```

`tests/integration/test_mcp_coverage.py`

```python
from datetime import UTC, date, datetime

import anyio
import pytest
from mcp.client import Client

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import FeedPullRow, TransactionRow
from finances.db.repositories import (
    create_account,
    create_rule,
    create_statement,
    map_feed_account,
)
from finances.domain.models import DEFAULT_LINK
from finances.mcp_server.server import build_server

TOOLS = [
    "data_coverage",
    "find_merchants",
    "get_balances",
    "get_budgets",
    "get_forecast",
    "get_insights",
    "get_net_worth",
    "get_recurring",
    "get_spending",
    "get_upcoming",
    "list_accounts",
    "list_categories",
    "list_rules",
    "list_transactions",
    "list_transfer_suggestions",
    "list_transfers",
    "list_uncategorized",
    "month_over_month",
]


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def data(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """A card with statements for January, February, and April (March missing) and no
    SimpleFIN; checking fed by SimpleFIN, pulled yesterday with $1.50 of drift; no backup."""
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 20))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        months = [
            (date(2026, 1, 1), date(2026, 1, 31)),
            (date(2026, 2, 1), date(2026, 2, 28)),
            (date(2026, 4, 1), date(2026, 4, 30)),
        ]
        for number, (start, end) in enumerate(months):
            create_statement(
                session,
                account_id=card.id,
                source_filename=f"card-{number}.pdf",
                file_sha256=str(number) * 64,
                parser_name="test",
                period_start=start,
                period_end=end,
                opening_balance_cents=0,
                closing_balance_cents=0,
                lines_parsed=0,
                rows_inserted=0,
                rows_duplicate=0,
            )
        map_feed_account(session, checking.id, "ACT-1", link=DEFAULT_LINK)
        session.add(
            FeedPullRow(
                account_id=checking.id,
                inserted=0,
                updated=0,
                removed=0,
                unchanged=0,
                feed_total_cents=0,
                balance_cents=30000,
                balance_date=date(2026, 5, 19),
                drift_cents=-150,
                pulled_at=datetime(2026, 5, 19, 23, 45, tzinfo=UTC),
            )
        )
        rows = [
            (card, date(2026, 5, 10), -650, "ACME COFFEE #12"),
            (card, date(2026, 5, 11), -2599, "FOOBAR GROCERY #77"),
            (checking, date(2026, 5, 15), 300000, "PAYCHECK EXAMPLE CORP"),
            (card, date(2026, 5, 12), -1599, "QUUX STREAMING"),
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
        session.flush()
        create_rule(session, "FOOBAR", "Groceries")
        categorize(session)
    engine.dispose()
    return tmp_settings


def test_eighteen_read_only_tools(tmp_settings: Settings) -> None:
    async def go():
        async with Client(build_server()) as client:
            return (await client.list_tools()).tools

    found = anyio.run(go)
    assert sorted(tool.name for tool in found) == TOOLS
    assert all(tool.annotations.read_only_hint for tool in found)


def test_data_coverage(data: Settings) -> None:
    assert call("data_coverage").structured_content == {
        "as_of": "2026-05-20",
        "accounts": [
            {
                "name": "Test Card",
                "type": "credit_card",
                "first_day": "2026-01-01",
                "last_day": "2026-05-12",
                "audited": [
                    {"start": "2026-01-01", "end": "2026-02-28"},
                    {"start": "2026-04-01", "end": "2026-04-30"},
                ],
                "gaps": [{"start": "2026-03-01", "end": "2026-03-31"}],
                "newest_statement_end": "2026-04-30",
                "mapped": False,
                "last_pull": None,
                "drift_cents": None,
                "drift_date": None,
            },
            {
                "name": "Test Checking",
                "type": "checking",
                "first_day": "2026-05-15",
                "last_day": "2026-05-19",
                "audited": [],
                "gaps": [],
                "newest_statement_end": None,
                "mapped": True,
                "last_pull": "2026-05-19",
                "drift_cents": -150,
                "drift_date": "2026-05-19",
            },
        ],
        "problems": [
            {
                "kind": "backup",
                "account": None,
                "detail": "No backup yet.",
                "action": "Run fin backup run, or press Back up now on the Backups page.",
            },
            {
                "kind": "drift",
                "account": "Test Checking",
                "detail": "The balance differs from SimpleFIN's by -$1.50 on 2026-05-19.",
                "action": (
                    "Look for a missing or extra transaction, or import the statement"
                    " for that period."
                ),
            },
            {
                "kind": "gap",
                "account": "Test Card",
                "detail": "No statement covers 2026-03-01 to 2026-03-31.",
                "action": "Upload the statement for those days.",
            },
        ],
    }


@pytest.mark.parametrize(
    ("arguments", "matches"),
    [
        (
            {"phrase": "cofee"},
            [
                {"name": "ACME COFFEE", "kind": "merchant", "score": 91},
                {"name": "Coffee & Dessert", "kind": "category", "score": 91},
            ],
        ),
        (
            {"phrase": "paychek", "limit": 1},
            [{"name": "PAYCHECK EXAMPLE CORP", "kind": "merchant", "score": 93}],
        ),
        (
            {"phrase": "groceries"},
            [
                {"name": "Groceries", "kind": "category", "score": 100},
                {"name": "FOOBAR GROCERY", "kind": "merchant", "score": 75},
            ],
        ),
        ({"phrase": "xyz"}, []),
    ],
)
def test_find_merchants(data: Settings, arguments: dict, matches: list) -> None:
    assert call("find_merchants", arguments).structured_content == {"matches": matches}


@pytest.mark.parametrize(
    ("phrase", "message"),
    [("   ", "give a phrase to look for"), ("x" * 101, "a phrase is at most 100 characters")],
)
def test_a_refused_phrase(data: Settings, phrase: str, message: str) -> None:
    result = call("find_merchants", {"phrase": phrase})
    assert [item.text for item in result.content] == [
        f"Error executing tool find_merchants: {message}"
    ]


@pytest.mark.parametrize(
    "arguments", [{"phrase": "acme", "limit": 0}, {"phrase": "acme", "limit": 21}]
)
def test_a_limit_out_of_range(data: Settings, arguments: dict) -> None:
    result = call("find_merchants", arguments)
    assert result.is_error is True
    assert result.content[0].text.startswith(
        "Error executing tool find_merchants: 1 validation error"
    )


@pytest.mark.parametrize(
    ("tool", "arguments"), [("data_coverage", {}), ("find_merchants", {"phrase": "acme"})]
)
def test_a_database_that_is_not_migrated(
    tmp_settings: Settings, tool: str, arguments: dict
) -> None:
    assert [item.text for item in call(tool, arguments).content] == [
        f"Error executing tool {tool}: The database is not up to date. Run: fin db upgrade"
    ]
```

The diff to earlier tests (apply it exactly):

```text
diff --git a/tests/integration/test_mcp_accounts.py b/tests/integration/test_mcp_accounts.py
index c699df7..748d079 100644
--- a/tests/integration/test_mcp_accounts.py
+++ b/tests/integration/test_mcp_accounts.py
@@ -20,7 +20,7 @@ from finances.domain.models import DataSource
 from finances.mcp_server.access import reading
 from finances.mcp_server.server import INSTRUCTIONS, build_server
 
-NO_AMOUNTS = ("list_accounts", "list_categories", "list_rules")
+NO_AMOUNTS = ("list_accounts", "list_categories", "list_rules", "find_merchants")
 READ_ONLY = {
     "read_only_hint": True,
     "destructive_hint": False,
@@ -73,6 +73,8 @@ def test_the_server_and_its_tools(tmp_settings: Settings) -> None:
     name, instructions, tools = anyio.run(go)
     assert (name, instructions) == ("finances", INSTRUCTIONS)
     assert sorted(tool.name for tool in tools) == [
+        "data_coverage",
+        "find_merchants",
         "get_balances",
         "get_budgets",
         "get_forecast",
diff --git a/tests/integration/test_mcp_more.py b/tests/integration/test_mcp_more.py
index 377fffe..abd4778 100644
--- a/tests/integration/test_mcp_more.py
+++ b/tests/integration/test_mcp_more.py
@@ -13,6 +13,8 @@ from finances.db.repositories import add_balance_snapshot, create_account
 from finances.domain.models import DataSource
 from finances.mcp_server.access import reading
 from finances.mcp_server.server import (
+    DATA_COVERAGE_DESCRIPTION,
+    FIND_MERCHANTS_DESCRIPTION,
     GET_BALANCES_DESCRIPTION,
     GET_BUDGETS_DESCRIPTION,
     GET_FORECAST_DESCRIPTION,
@@ -146,6 +148,8 @@ def test_each_tool_description_matches_the_table(tmp_settings: Settings) -> None
         "list_rules": LIST_RULES_DESCRIPTION,
         "list_transfers": LIST_TRANSFERS_DESCRIPTION,
         "list_transfer_suggestions": LIST_TRANSFER_SUGGESTIONS_DESCRIPTION,
+        "data_coverage": DATA_COVERAGE_DESCRIPTION,
+        "find_merchants": FIND_MERCHANTS_DESCRIPTION,
     }
 
 
diff --git a/tests/integration/test_mcp_outlook.py b/tests/integration/test_mcp_outlook.py
index 433ee71..2e645be 100644
--- a/tests/integration/test_mcp_outlook.py
+++ b/tests/integration/test_mcp_outlook.py
@@ -21,6 +21,8 @@ from finances.domain.models import DataSource
 from finances.mcp_server.server import build_server
 
 TOOLS = [
+    "data_coverage",
+    "find_merchants",
     "get_balances",
     "get_budgets",
     "get_forecast",
diff --git a/tests/integration/test_mcp_queues.py b/tests/integration/test_mcp_queues.py
index 266f4cf..1a06755 100644
--- a/tests/integration/test_mcp_queues.py
+++ b/tests/integration/test_mcp_queues.py
@@ -15,6 +15,8 @@ from finances.domain.models import CONFIRMED
 from finances.mcp_server.server import build_server
 
 TOOLS = [
+    "data_coverage",
+    "find_merchants",
     "get_balances",
     "get_budgets",
     "get_forecast",
@@ -132,7 +134,7 @@ def queues(tmp_settings: Settings) -> Settings:
     return tmp_settings
 
 
-def test_sixteen_read_only_tools(tmp_settings: Settings) -> None:
+def test_the_read_only_tools(tmp_settings: Settings) -> None:
     async def go():
         async with Client(build_server()) as client:
             return (await client.list_tools()).tools
diff --git a/tests/integration/test_mcp_spending.py b/tests/integration/test_mcp_spending.py
index 69e5d20..9c56dd5 100644
--- a/tests/integration/test_mcp_spending.py
+++ b/tests/integration/test_mcp_spending.py
@@ -14,6 +14,8 @@ from finances.db.repositories import create_account, create_person, create_rule,
 from finances.mcp_server.server import build_server
 
 TOOLS = [
+    "data_coverage",
+    "find_merchants",
     "get_balances",
     "get_budgets",
     "get_forecast",
```

## Tests to write

`tests/integration/test_mcp_coverage_more.py`: an account with no data (`first_day` and `last_day` null); a closed account left out; a statement-only account whose newest statement is stale (its problem listed); `find_merchants` on an empty database (only categories can match); a merchant that appears only in a pending transaction is not offered.

## Rules for this phase

- `domain/periods.py` and `domain/merchants.py` import only the standard library and `finances.domain`.
- The tools are thin: `data_coverage` and `find_merchants` each call one `analysis` function and rename fields.
- No phrase, name, or amount is logged or echoed in an error.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_name_matching.py tests/integration/test_mcp_coverage.py`, 28 tests; at least N + 28 passed in all;
- `git diff --stat HEAD -- tests` lists only the five files of the given diff;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.mcp_server --cov=finances.domain.periods --cov=finances.domain.merchants --cov=finances.analysis.coverage --cov=finances.analysis.names --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain`, `git grep -n --untracked -E "^ *(from|import) +finances\.(views|web|cli)" -- src/finances/mcp_server`, and `git grep -n --untracked -E "\.(debug|info|warning|error|exception|critical)\(|print\(" -- src/finances/mcp_server src/finances/cli/mcp.py`, no output.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 14e: data coverage and finding merchants (YYYY-MM-DD)`.
