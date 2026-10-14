# Phase 23: one home for text rules, limits, and input checks

## Goal

**No behaviour changes.** Every command, page, and message is exactly as today, including which message wins when a form has two mistakes. Only where the rules live changes.

The code audit after Phase 16d found small rules copied across layers:

- **"collapse whitespace, cut to N characters, trim"** is written four times (`feed_setup._tidy`, `repositories._feed_text`, `sync/service._description`, `ingest/service._description`), and `collapse_ws` lives in the parser helpers although dedup and the import service use it;
- **column widths** are repeated under five names (`NAME_LIMIT`, `TEXT_LIMIT` twice, `ACCOUNT_TEXT_LIMIT`, `_ID_LIMIT`, `_DESCRIPTION_LIMIT`, `_FEED_ID_LIMIT` twice), none tied to the ORM's `String(n)`;
- **typed-input checks** sit in the command line and the web instead of the repository: the SimpleFIN id check (twice), "Joint, or a person, else person not found" (twice), and the friendly account-type message (web only);
- **small helpers** are copied: `_fail` in three command modules, `_squeezed` in two parsers, and the statement periods both pairing services build.

After this phase each has one home: `finances.domain.text` for text and widths (used by the ORM), the repository and the domain validators for input checks, and one shared helper each for the rest.

## Read first

- `AGENTS.md` ("Every text value written fits its column"), `docs/architecture.md`
- `src/finances/domain/feed_setup.py`, `src/finances/domain/people.py`, `src/finances/domain/models.py` (`validate_last4`, `validate_currency`), `src/finances/db/orm.py`, `src/finances/db/repositories.py` (`create_account`, `map_feed_account`, `_feed_text`), `src/finances/sync/service.py`, `src/finances/ingest/service.py`, `src/finances/ingest/dedup.py`, `src/finances/ingest/parsers/helpers.py`, `marcus.py`, `truist.py`
- `src/finances/cli/common.py`, `cli/sync.py` (`map_command`), `cli/accounts.py` (`set_owner`), `cli/people.py`, `src/finances/web/app.py` (`_add_account`, `_owner_id`, `_feed_id`)

## Starting state

- Phase 22 is committed. `git status --short` prints nothing.
- Run `.venv/bin/python scripts/check.py`; it ends with `All checks passed.`. Note the number of tests passed in its `tests` step. This spec calls it **N**. It is `2007` when Phase 22 is the last phase built.
- Existing tests import `collapse_ws` from `finances.ingest.parsers.helpers`, `NAME_LIMIT` from `finances.domain.people`, and `TEXT_LIMIT` from `finances.domain.feed_setup`; these names stay.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/text.py` | new (Part 1) |
| `src/finances/db/orm.py` | widths from `domain.text` (R4) |
| `src/finances/domain/feed_setup.py`, `domain/people.py`, `domain/models.py` | Part 1 and R7 |
| `src/finances/db/repositories.py` | `fit`, `NAME_LIMIT`; `map_feed_account`, `create_account`; new `resolve_owner`, `statement_periods` |
| `src/finances/sync/service.py`, `src/finances/ingest/service.py`, `src/finances/ingest/dedup.py` | `fit`, the limits, `statement_periods` |
| `src/finances/ingest/parsers/helpers.py`, `marcus.py`, `truist.py` | `collapse_ws` re-exported; `squeeze` |
| `src/finances/cli/common.py`, `cli/sync.py`, `cli/accounts.py`, `cli/people.py` | `fail`; the shared checks |
| `src/finances/web/app.py` | the shared checks |
| `AGENTS.md` | one sentence (R15) |
| `tests/unit/test_text.py`, `tests/unit/test_shared_helpers.py`, `tests/integration/test_repository_rules.py` | new: given, do not change |
| `docs/progress.md` | one new entry |

No template, migration, or existing test changes.

## Out of scope

- Any change to output, messages, exit codes, or the order in which a command or form reports its mistakes.
- `ingest/service`'s `_fit` for cardholder and reference, which cuts without collapsing spaces: a different rule, left as it is.
- `sync/simplefin._clean` (cleaning SimpleFIN's messages): a different rule.
- Widths other than 100, 200, and 500 (`String(3)`, `String(4)`, `String(20)`, `String(30)`, `String(50)`, `String(64)`, `String(255)`).
- Adding `domain/text.py` to `scripts/critical_modules.txt` (Phase 10's test pins that list); splitting modules.

## Dependencies

None new.

## Design

```python
# src/finances/domain/text.py  (imports nothing from finances)
NAME_LIMIT = 100                   # names, institutions, cardholders, references
DESCRIPTION_LIMIT = 500            # transaction descriptions
FEED_ID_LIMIT = 100                # an aggregator's transaction id
PROVIDER_ACCOUNT_ID_LIMIT = 200    # an aggregator's account id


def collapse_ws(text: str) -> str: ...        # " ".join(text.split())
def fit(text: str, limit: int) -> str: ...    # collapse_ws(text)[:limit].rstrip()
```

```python
# src/finances/domain/models.py
def validate_provider_account_id(text: str) -> str: ...
# returns text.strip() when it is 1 to PROVIDER_ACCOUNT_ID_LIMIT characters long,
# otherwise raises ValueError("feed account id must be 1 to 200 characters")
```

```python
# src/finances/db/repositories.py
def resolve_owner(session: Session, owner: str) -> Person | None: ...
def statement_periods(session: Session, account_id: int) -> list[tuple[date, date]]: ...
```

```python
# src/finances/cli/common.py
def fail(message: str) -> NoReturn: ...   # stderr "Error: MESSAGE", then typer.Exit(code=1)
```

```python
# src/finances/ingest/parsers/helpers.py
def squeeze(text: str) -> str: ...        # "".join(text.split())
```

## Requirements

### Part 1: text and widths

- **R1.** `domain/text.py` as in the design.
- **R2.** The older public names stay importable and are the same objects or values: `finances.ingest.parsers.helpers.collapse_ws` is `finances.domain.text.collapse_ws` (imported, not redefined); `domain.people.NAME_LIMIT`, `domain.feed_setup.TEXT_LIMIT`, and `ingest.service.TEXT_LIMIT` equal `NAME_LIMIT`; `ingest.service.DESCRIPTION_LIMIT` equals `DESCRIPTION_LIMIT`.
- **R3.** The four copies of the rule use `fit`: `feed_setup` with `NAME_LIMIT`, the seen-account text in the repository with `NAME_LIMIT`, the feed's descriptions in `sync/service.py` with `DESCRIPTION_LIMIT`, and statement descriptions in `ingest/service.py` with `DESCRIPTION_LIMIT`. Their private helpers `_tidy`, `_feed_text`, and both `_description` are gone. `ACCOUNT_TEXT_LIMIT` becomes `NAME_LIMIT`; `sync/service.py`'s `_ID_LIMIT` and `_DESCRIPTION_LIMIT` become `FEED_ID_LIMIT` and `DESCRIPTION_LIMIT`. `ingest/dedup.py` and `ingest/service.py` import `collapse_ws` from `finances.domain.text`. Fingerprints do not change.
- **R4.** In `db/orm.py` these twelve columns take their width from `domain.text`, and no `String(100)`, `String(200)`, or `String(500)` literal remains: `accounts.name`, `accounts.institution`, `people.name`, `cardholder_aliases.cardholder`, `transactions.cardholder`, `transactions.external_id`, `feed_seen_accounts.name`, `feed_seen_accounts.institution` (`NAME_LIMIT`); `transactions.description` (`DESCRIPTION_LIMIT`); `feed_items.feed_id` (`FEED_ID_LIMIT`); `feed_accounts.provider_account_id` and `feed_seen_accounts.provider_account_id` (`PROVIDER_ACCOUNT_ID_LIMIT`). Migrations keep their literal numbers.

### Part 2: input checks with one home

- **R5.** `validate_provider_account_id(text)` as in the design.
- **R6.** `map_feed_account(session, account_id, provider_account_id, link)` validates the id with `validate_provider_account_id` before anything else and stores the result (without outer spaces). Everything else is unchanged.
- **R7.** `resolve_owner(session, owner)` returns `None` when `owner`, without outer spaces and in any case, is `joint`; otherwise the person `get_person_by_name` finds; otherwise it raises `ValueError("person not found")`.
- **R8.** `create_account` checks the type **first**, before the name: a value that is neither an `AccountType` nor one of its values raises `ValueError("type must be one of: checking, savings, credit_card, other")`. Its other checks keep their order after it.
- **R9.** `statement_periods(session, account_id)` returns `(period_start, period_end)` of each of the account's stored statements, in `list_statements` order. `ingest/service.py` and `sync/service.py` use it to build their zones (and add the importing statement's period, as now).

### Part 3: the interfaces use them, in today's order

- **R10.** `fin sync map` still checks the SimpleFIN id **before** it looks up the account, now with `validate_provider_account_id`; the web's map and create-and-map forms pass the id to `map_feed_account` unchecked, which keeps their order (the account first). The private `_FEED_ID_LIMIT` (command line and web) and the web's `_feed_id` are gone.
- **R11.** `fin accounts set-owner` and the web's owner fields (the Accounts owner form and Create and map) use `resolve_owner`, each after looking up the account as now; the web's `_owner_id` is gone. `fin accounts set-owner` still prints `Joint` or the person's stored name.
- **R12.** The web's `_add_account` no longer checks the type itself; `create_account` does (R8).
- **R13.** `cli/common.fail(message)` as in the design; `cli/sync.py`, `cli/accounts.py`, and `cli/people.py` use it and lose their `_fail`.
- **R14.** `ingest/parsers/helpers.squeeze(text)` as in the design; `marcus.py` and `truist.py` use it and lose `_squeezed`.

### Part 4: the document

- **R15.** In `AGENTS.md`, the bullet that starts `Every text value written fits its column.` gains, at its end: ` Use `finances.domain.text`: `fit` for text from a statement or the feed, and its limits for the widths.`

## Given tests

Create these three files exactly as shown and do not change them. If one fails, the code is wrong. Every existing test must pass unchanged: they pin today's output and messages, and are this phase's safety net. There are no tests for you to write.

`tests/unit/test_text.py`

```python
from pathlib import Path

import pytest
from finances.domain.text import (
    DESCRIPTION_LIMIT,
    FEED_ID_LIMIT,
    NAME_LIMIT,
    PROVIDER_ACCOUNT_ID_LIMIT,
    collapse_ws,
    fit,
)

import finances.db.orm as orm
import finances.domain.feed_setup as feed_setup
import finances.domain.people as people
import finances.ingest.parsers.helpers as helpers
import finances.ingest.service as ingest_service
from finances.db.orm import Base


def test_the_limits() -> None:
    assert (NAME_LIMIT, DESCRIPTION_LIMIT, FEED_ID_LIMIT, PROVIDER_ACCOUNT_ID_LIMIT) == (
        100,
        500,
        100,
        200,
    )


def test_the_older_names_are_the_same_limits() -> None:
    assert people.NAME_LIMIT == feed_setup.TEXT_LIMIT == ingest_service.TEXT_LIMIT == NAME_LIMIT
    assert ingest_service.DESCRIPTION_LIMIT == DESCRIPTION_LIMIT


def test_collapse_ws_has_one_home() -> None:
    assert helpers.collapse_ws is collapse_ws
    assert collapse_ws("  ACME \t COFFEE\n#12  ") == "ACME COFFEE #12"
    assert collapse_ws("") == ""


@pytest.mark.parametrize(
    ("text", "limit", "fitted"),
    [
        ("  Probe   Visa  ", 100, "Probe Visa"),
        ("ABCDE", 5, "ABCDE"),
        ("ABCDEF", 5, "ABCDE"),
        ("ABCD EFGH", 5, "ABCD"),
        ("   ", 5, ""),
        ("A B", 5, "A B"),
    ],
)
def test_fit_collapses_cuts_and_trims(text: str, limit: int, fitted: str) -> None:
    assert fit(text, limit) == fitted


@pytest.mark.parametrize(
    ("table", "column", "limit"),
    [
        ("accounts", "name", NAME_LIMIT),
        ("accounts", "institution", NAME_LIMIT),
        ("people", "name", NAME_LIMIT),
        ("cardholder_aliases", "cardholder", NAME_LIMIT),
        ("transactions", "description", DESCRIPTION_LIMIT),
        ("transactions", "cardholder", NAME_LIMIT),
        ("transactions", "external_id", NAME_LIMIT),
        ("feed_items", "feed_id", FEED_ID_LIMIT),
        ("feed_accounts", "provider_account_id", PROVIDER_ACCOUNT_ID_LIMIT),
        ("feed_seen_accounts", "provider_account_id", PROVIDER_ACCOUNT_ID_LIMIT),
        ("feed_seen_accounts", "name", NAME_LIMIT),
        ("feed_seen_accounts", "institution", NAME_LIMIT),
    ],
)
def test_each_column_is_as_wide_as_its_limit(table: str, column: str, limit: int) -> None:
    assert Base.metadata.tables[table].columns[column].type.length == limit


def test_the_orm_names_its_widths_by_constant() -> None:
    source = Path(orm.__file__).read_text(encoding="utf-8")
    for literal in ("String(100)", "String(200)", "String(500)"):
        assert literal not in source
```

`tests/unit/test_shared_helpers.py`

```python
import pytest
import typer

from finances.cli.common import fail
from finances.domain.models import validate_provider_account_id
from finances.ingest.parsers.helpers import squeeze

BAD_ID = "feed account id must be 1 to 200 characters"


@pytest.mark.parametrize(
    ("text", "kept"),
    [("ACT-1", "ACT-1"), ("  ACT-1 \t", "ACT-1"), ("X" * 200, "X" * 200), (" a b ", "a b")],
)
def test_a_usable_provider_account_id(text: str, kept: str) -> None:
    assert validate_provider_account_id(text) == kept


@pytest.mark.parametrize("text", ["", "   ", "X" * 201, " " + "X" * 201])
def test_an_unusable_provider_account_id(text: str) -> None:
    with pytest.raises(ValueError, match=f"^{BAD_ID}$"):
        validate_provider_account_id(text)


def test_fail_prints_the_error_and_ends_the_command(capsys) -> None:
    with pytest.raises(typer.Exit) as stopped:
        fail("account not found")
    assert stopped.value.exit_code == 1
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "Error: account not found\n")


@pytest.mark.parametrize(
    ("text", "squeezed"),
    [("New  Balance", "NewBalance"), (" A \t B\nC ", "ABC"), ("", ""), (" x", "x")],
)
def test_squeeze_removes_every_space(text: str, squeezed: str) -> None:
    assert squeeze(text) == squeezed
```

`tests/integration/test_repository_rules.py`

```python
from datetime import date

import pytest
from sqlalchemy import Engine

from finances.db.engine import session_scope
from finances.db.repositories import (
    create_account,
    create_person,
    create_statement,
    list_feed_accounts,
    map_feed_account,
    resolve_owner,
    statement_periods,
)

BAD_ID = "feed account id must be 1 to 200 characters"
BAD_TYPE = "type must be one of: checking, savings, credit_card, other"


@pytest.fixture
def card(db_engine: Engine) -> Engine:
    with session_scope(db_engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        create_account(session, "Test Other", "Test Bank", "credit_card")
    return db_engine


def mappings(engine: Engine) -> list[tuple[int, str, str]]:
    with session_scope(engine) as session:
        return [(m.account_id, m.provider_account_id, m.link) for m in list_feed_accounts(session)]


def test_a_mapping_keeps_the_id_without_outer_spaces(card: Engine) -> None:
    with session_scope(card) as session:
        map_feed_account(session, 1, "  ACT-1 ", "alex")
    assert mappings(card) == [(1, "ACT-1", "alex")]


@pytest.mark.parametrize("feed_id", ["", "  ", "X" * 201])
def test_a_mapping_with_an_unusable_id_is_refused(card: Engine, feed_id: str) -> None:
    with session_scope(card) as session, pytest.raises(ValueError, match=f"^{BAD_ID}$"):
        map_feed_account(session, 1, feed_id, "alex")
    assert mappings(card) == []


def test_the_same_id_with_spaces_is_the_same_mapping(card: Engine) -> None:
    with session_scope(card) as session:
        map_feed_account(session, 1, "ACT-1", "alex")
    with session_scope(card) as session, pytest.raises(ValueError, match="already mapped"):
        map_feed_account(session, 2, " ACT-1 ", "alex")


@pytest.mark.parametrize("owner", ["joint", "JOINT", "  Joint  "])
def test_joint_is_no_person(db_engine: Engine, owner: str) -> None:
    with session_scope(db_engine) as session:
        assert resolve_owner(session, owner) is None


def test_a_person_is_found_ignoring_case_and_spaces(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        kim = create_person(session, "Kim")
        assert resolve_owner(session, "  kIM ") == kim


@pytest.mark.parametrize("owner", ["Nobody", "", "  "])
def test_an_unknown_owner_is_refused(db_engine: Engine, owner: str) -> None:
    with session_scope(db_engine) as session:
        create_person(session, "Kim")
        with pytest.raises(ValueError, match="^person not found$"):
            resolve_owner(session, owner)


@pytest.mark.parametrize("kind", ["loan", "", "CHECKING", "credit card"])
def test_an_unknown_type_gets_a_plain_message(db_engine: Engine, kind: str) -> None:
    with session_scope(db_engine) as session, pytest.raises(ValueError, match=f"^{BAD_TYPE}$"):
        create_account(session, "Probe", "Probe Bank", kind)


def test_the_type_is_checked_first(db_engine: Engine) -> None:
    with session_scope(db_engine) as session, pytest.raises(ValueError, match=f"^{BAD_TYPE}$"):
        create_account(session, "", "", "loan", currency="usd", last4="12")


def test_statement_periods(card: Engine) -> None:
    with session_scope(card) as session:
        assert statement_periods(session, 1) == []
        for account_id, start, end, sha in (
            (1, date(2026, 1, 1), date(2026, 1, 31), "a"),
            (1, date(2026, 2, 1), date(2026, 2, 28), "b"),
            (2, date(2026, 3, 1), date(2026, 3, 31), "c"),
        ):
            create_statement(
                session,
                account_id=account_id,
                source_filename=f"{sha}.pdf",
                file_sha256=sha * 64,
                parser_name="probe",
                period_start=start,
                period_end=end,
                opening_balance_cents=0,
                closing_balance_cents=0,
                lines_parsed=0,
                rows_inserted=0,
                rows_duplicate=0,
            )
        assert sorted(statement_periods(session, 1)) == [
            (date(2026, 1, 1), date(2026, 1, 31)),
            (date(2026, 2, 1), date(2026, 2, 28)),
        ]
```

## Rules for this phase

- **Same behaviour, same messages, same order of messages.** If a test or the verifier's comparison shows a difference, the code is wrong.
- **Never edit a shipped migration.**
- **`domain` imports nothing outside `finances.domain`.**
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; in the `tests` step, 0 failed, 0 skipped, 0 xfailed, at least N + 53 passed |
| `.venv/bin/python -m pytest tests/unit/test_text.py tests/unit/test_shared_helpers.py tests/integration/test_repository_rules.py --no-cov` | exactly `53 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| each of the two searches below | no output |
| `git diff HEAD --stat -- tests src/finances/web/templates src/finances/db/migrations scripts` | nothing |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain --cov=finances.db --cov=finances.ingest --cov=finances.sync --cov=finances.cli --cov=finances.web --cov=finances.views --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n -E 'def (_tidy|_feed_text|_description|_squeezed|_fail|_feed_id|_owner_id)\(|(^|[^A-Z])_FEED_ID_LIMIT|ACCOUNT_TEXT_LIMIT|(^|[^A-Z])_ID_LIMIT|(^|[^A-Z])_DESCRIPTION_LIMIT|join\(text\.split\(\)\)\[:' -- src/finances ':!src/finances/domain/text.py'`

`git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views)" -- src/finances/domain`

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 23: one home for text rules, limits, and input checks (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. In your final message, give the last ten lines of `scripts/check.py`'s output and the output line of each other acceptance command.
