# Phase 19a: the agent proposes categories, and a person reviews them

## Goal

The agent can suggest, and only suggest. After this phase:

- the MCP server has two tools that **write**, and they write nothing but the agent's own material: `propose_category` stores a proposal (a category for a transaction, with a one-line reason a person will read), and `log_advice` keeps one of its notes; `list_proposals` and `list_advice` read them back;
- a person reviews in the terminal: `fin review list` shows the open proposals beside the transaction and its category now; `fin review accept --id N` does what the proposal says by the same function the terminal and web use (`set_category_by_hand`), so the change is the person's choice in the audit trail; `fin review decline --id N` changes nothing and stops the agent proposing the same again;
- a proposal is **out of date** once a person has decided its transaction (set its category by hand, or paired it as a transfer); it cannot then be accepted.

The agent cannot accept or decline, and no tool touches an amount, a date, a balance, an account, an import, a deletion, or a sync. Phase 19b brings the review queue to the web; 19c transfer and rule proposals; merchant aliases and finding status wait for Phase 28.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `AGENTS.md` (MCP tools may write only proposals and the advice log), `docs/architecture.md` ("Agent interface"), `docs/roadmap.md` (Phase 19)
- `docs/phases/phase-14a-mcp-server.md`, `docs/phases/phase-34a-audit-trail.md`
- `src/finances/mcp_server/`, `src/finances/db/repositories/assignments.py` (`set_category_by_hand`, `_assignment_row`), `src/finances/db/repositories/transfers.py` (`find_transfer_pair`), `src/finances/db/repositories/categories.py` (`_leaf_category`), `src/finances/db/repositories/audit.py`

## Starting state

N is `3349` when Phase 34b is the last phase built. The newest migration is `0012`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0013_proposals.py` | new: given (R1) |
| `src/finances/domain/text.py`, `src/finances/db/orm.py` | two limits; `ProposalRow`, `AdviceRow`, `to_proposal`, `to_advice` (R1) |
| `src/finances/domain/proposals.py` | new (R2) |
| `src/finances/domain/audit.py` | two actions, one kind (R3) |
| `src/finances/db/repositories/proposals.py`, `src/finances/db/repositories/__init__.py` | new area (R4 to R6) |
| `src/finances/analysis/review.py`, `src/finances/views/review.py`, `src/finances/cli/review.py`, `src/finances/cli/main.py` | `fin review` (R7, R8) |
| `src/finances/mcp_server/access.py`, `tools.py`, `server.py` | `writing()` and four tools (R9, R10) |
| nine earlier test files | the given diff (R11) |
| `tests/unit/test_proposal_rules.py`, `tests/integration/test_migration_0013.py`, `tests/integration/test_proposals.py`, `tests/integration/test_mcp_proposals.py`, `tests/e2e/test_cli_review.py` | new: given |
| `tests/integration/test_proposals_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- The web review queue and suggestions beside transactions (19b); transfer, not-a-transfer, and rule proposals (19c); merchant aliases and finding status (after Phase 28).
- Any tool that accepts, declines, or edits a proposal, or writes anything but a proposal or a note.

## Dependencies

None new. One migration, given below.

## Design

```python
# src/finances/domain/text.py
PROPOSAL_TEXT_LIMIT = 200
ADVICE_TEXT_LIMIT = 1000

# src/finances/domain/proposals.py  (standard library and finances.domain only)
CATEGORY = "category"
KINDS = (CATEGORY,)
OPEN = "open"
ACCEPTED = "accepted"
DECLINED = "declined"
STATUSES = (OPEN, ACCEPTED, DECLINED)

@dataclass(frozen=True)
class Proposal:
    id: int
    kind: str
    target_id: int          # the transaction's id
    value: str              # the category's stored name
    reason: str
    status: str
    created_at: datetime    # UTC
    decided_at: datetime | None

@dataclass(frozen=True)
class Advice:
    id: int
    created_at: datetime
    subject: str
    text: str

def out_of_date(*, exists: bool, set_by_hand: bool, paired: bool) -> bool: ...
def proposal_text(proposal: Proposal) -> str: ...   # "transaction 5: Groceries"

# src/finances/db/repositories/proposals.py
def _now() -> datetime: ...   # datetime.now(UTC), looked up when called
def decided_by_a_person(session: Session, transaction_id: int) -> bool: ...
def propose_category(session: Session, transaction_id: int, category: str, reason: str) -> Proposal: ...
def list_proposals(session: Session, *, status: str | None = None, limit: int = 50) -> list[Proposal]: ...
def proposal_out_of_date(session: Session, proposal: Proposal) -> bool: ...
def accept_proposal(session: Session, proposal_id: int) -> Proposal: ...
def decline_proposal(session: Session, proposal_id: int) -> Proposal: ...
def log_advice(session: Session, text: str, subject: str = "") -> Advice: ...
def list_advice(session: Session, *, limit: int = 20) -> list[Advice]: ...

# src/finances/analysis/review.py
@dataclass(frozen=True)
class ReviewItem:
    proposal: Proposal
    transaction: Transaction | None
    account: str | None
    current: str | None      # the transaction's category now, from any source
    out_of_date: bool

def review_items(session: Session, *, status: str = OPEN, limit: int = 50) -> list[ReviewItem]: ...

# src/finances/views/review.py
@dataclass(frozen=True)
class ReviewRow:   # ID, Date, Account, Description, Amount, Now, Proposed, Reason, State
    id: str
    date: str
    account: str
    description: str
    amount: str
    now: str
    proposed: str
    reason: str
    state: str     # the status, or "out of date"

def review_rows(items: list[ReviewItem]) -> list[ReviewRow]: ...
def accepted_text(proposal: Proposal) -> str: ...  # "Accepted proposal 1: Coffee & Dessert for transaction 1."
def declined_text(proposal: Proposal) -> str: ...  # "Declined proposal 2."

# src/finances/mcp_server/access.py
@contextmanager
def writing() -> Iterator[Session]: ...  # like reading(), but an engine that can write

# src/finances/mcp_server/tools.py
def propose_category(transaction_id: int, category: str, reason: str) -> dict[str, Any]: ...
def list_proposals(
    status: Literal["open", "accepted", "declined"] = "open",
    limit: Annotated[int, Field(ge=1, le=200)] = 50,
) -> dict[str, Any]: ...
def log_advice(text: str, subject: str = "") -> dict[str, Any]: ...
def list_advice(limit: Annotated[int, Field(ge=1, le=200)] = 20) -> dict[str, Any]: ...
```

In `server.py`, exactly (the instructions change their last sentence; the rest is new):

```python
INSTRUCTIONS = (
    "Read-only tools over one household's finances. Money is in integer cents. Amounts are"
    " from the account holder's side: money leaving is negative, money coming in is positive,"
    " and a card balance owed is negative. Dates are ISO (YYYY-MM-DD). The tools change no"
    " data: they only store your proposals, which a person accepts or declines, and your notes."
)
```

```python
WRITES_PROPOSALS = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
)
PROPOSE_CATEGORY_DESCRIPTION = (
    "Propose a category for a transaction without one (or set only by a rule), with a one-line "
    "reason a person will read. It changes nothing: a person accepts or declines it with fin "
    "review. Refused when a person already decided the transaction, declined this same "
    "proposal, or another proposal for it is open."
)
LIST_PROPOSALS_DESCRIPTION = (
    "Your proposals, newest first, of one status (open by default, accepted, or declined), at "
    "most limit (1 to 200, default 50): the transaction, the category, your reason, when it was "
    "made and decided, and whether it is out of date (a person decided the transaction since). "
    "No amounts."
)
LOG_ADVICE_DESCRIPTION = (
    "Keep a note of advice you gave or something to remember about this household (up to 1000 "
    "characters, with an optional subject of up to 100). It changes no data. No amounts are "
    "computed here; write them as you would in integer cents or plain text."
)
LIST_ADVICE_DESCRIPTION = (
    "Your notes, newest first, at most limit (1 to 200, default 20), with when each was kept."
)
_WRITES = ("propose_category", "log_advice")
```

## Requirements

### Part 1: storage and rules

- **R1.** Add the given migration exactly; `PROPOSAL_TEXT_LIMIT`, `ADVICE_TEXT_LIMIT`; the two row classes (text widths by those constants, `subject` by `NAME_LIMIT`) and `to_proposal`, `to_advice` (times read back in UTC).
- **R2.** `domain/proposals.py` as designed: `out_of_date` is true when the transaction no longer exists, or its category was set by hand, or it is in a transfer pair.
- **R3.** `ACTIONS` ends with `proposal_accepted`, `proposal_declined`; `KINDS` ends with `proposal`.

### Part 2: the repository area

- **R4.** `propose_category` checks, in this order, and refuses with `ValueError`: the reason, with runs of white space made one space, is 1 to 200 characters (`a reason must be 1 to 200 characters`); the transaction exists (`transaction not found`); the category is a category, by `_leaf_category` (its own messages); a person has not decided the transaction (`decided_by_a_person`: set by hand or paired; `a person has already decided this transaction`); a person has not declined a proposal of this category for it (`a person declined this proposal already`); no proposal for it is open (`this transaction already has an open proposal`). A category set by a rule may be proposed over. It stores an open proposal with the category's stored name, stamps `created_at` with `_now()`, flushes, and returns it; nothing else changes.
- **R5.** `list_proposals` refuses a status not in `STATUSES` (`status must be one of: open, accepted, declined`) and a limit below 1 (`limit must be at least 1`), and returns proposals of the status (all when None), newest first then highest id. `proposal_out_of_date` applies R2 to the stored transaction. `accept_proposal` and `decline_proposal` refuse an unknown id (`proposal not found`) and a proposal not open (`proposal N is already accepted` or `declined`); `accept_proposal` also refuses one out of date (`proposal N is out of date: the transaction was decided since`), then calls `set_category_by_hand(session, target_id, value)`, marks it accepted with `decided_at` from `_now()`, and records `proposal_accepted` (who `person`, kind `proposal`, its id, after `proposal_text`); `decline_proposal` marks it declined and records `proposal_declined` the same way. Neither commits.
- **R6.** `log_advice` strips the text (1 to 1000 characters: `advice must be 1 to 1000 characters`) and collapses the subject's white space (at most 100: `a subject is at most 100 characters`), stamps it with `_now()`, and returns it; `list_advice` refuses a limit below 1 and returns the notes newest first.

### Part 3: the person's side

- **R7.** `review_items` gives each proposal of the status (open by default), newest first, with its transaction (None when gone), the account's name, the transaction's category now from any source, and `proposal_out_of_date`. `review_rows` formats them (ISO date, `format_cents`, `""` for what is missing, the state `out of date` or the status).
- **R8.** `fin review` (a Typer group, help `Review the agent's proposals.`): `list [--limit 1..500, default 50]` prints a table with the columns `ID`, `Date`, `Account`, `Description`, `Amount`, `Now`, `Proposed`, `Reason`, `State`, or `No open proposals.`; `accept --id N [--id M ...]` and `decline --id ...` decide every id in **one** session and print one line each (`accepted_text`, `declined_text`); if any id is refused, the command fails with its message (exit 1) and nothing is decided. Each checks the schema first.

### Part 4: the agent's side

- **R9.** `writing()` refuses with `ToolError(NOT_MIGRATED)` when the schema is not current, else yields a session of an engine that can write, and disposes of it. Only `propose_category` and `log_advice` use it; every other tool still reads through `reading()`.
- **R10.** The four tools: `propose_category` returns `{"proposal": {...}}` and `list_proposals` `{"proposals": [...]}`, each item `{"id", "kind", "transaction_id", "category", "reason", "status", "created_at", "decided_at", "out_of_date"}` (times as ISO strings, `decided_at` null when open; `out_of_date` false for a new proposal); `log_advice` returns `{"advice": {"id", "created_at", "subject", "text"}}` and `list_advice` `{"advice": [...]}`. A `ValueError` becomes a `ToolError` with its message. The two writing tools are registered with `WRITES_PROPOSALS` (read-only false, destructive false, idempotent false, open world false), the others with `READ_ONLY`; all four after 14e's tools, with the descriptions above. `mcp_server` imports from `finances.db.repositories` exactly the names the given test lists.
- **R11.** Apply the given diff to nine earlier test files (the tool lists and description table, the read-only checks that now except the two writing tools, the cents exemptions, the audit lists and message, the repository areas). No other earlier test changes.

## Given migration

```python
"""Create proposals (the agent's suggestions, waiting for a person) and advice_log (its notes)."""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_proposals"),
    )
    op.create_table(
        "advice_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("text", sa.String(1000), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_advice_log"),
    )


def downgrade() -> None:
    op.drop_table("advice_log")
    op.drop_table("proposals")
```

## Given tests

39 tests in five files. `finances.db.repositories.proposals._now` is replaced where a time is pinned.

`tests/unit/test_proposal_rules.py`

```python
from datetime import UTC, datetime

import pytest

from finances.domain.proposals import (
    ACCEPTED,
    CATEGORY,
    DECLINED,
    KINDS,
    OPEN,
    STATUSES,
    Proposal,
    out_of_date,
    proposal_text,
)
from finances.domain.text import ADVICE_TEXT_LIMIT, PROPOSAL_TEXT_LIMIT


def test_the_lists_and_limits() -> None:
    assert (CATEGORY, KINDS) == ("category", ("category",))
    assert (OPEN, ACCEPTED, DECLINED, STATUSES) == (
        "open",
        "accepted",
        "declined",
        ("open", "accepted", "declined"),
    )
    assert (PROPOSAL_TEXT_LIMIT, ADVICE_TEXT_LIMIT) == (200, 1000)


@pytest.mark.parametrize(
    ("exists", "set_by_hand", "paired", "stale"),
    [
        (True, False, False, False),
        (False, False, False, True),
        (True, True, False, True),
        (True, False, True, True),
    ],
)
def test_out_of_date(exists: bool, set_by_hand: bool, paired: bool, stale: bool) -> None:
    assert out_of_date(exists=exists, set_by_hand=set_by_hand, paired=paired) is stale


def test_the_text_of_a_proposal() -> None:
    made = datetime(2026, 5, 25, tzinfo=UTC)
    found = Proposal(3, CATEGORY, 5, "Groceries", "FOOBAR is a grocer", OPEN, made, None)
    assert proposal_text(found) == "transaction 5: Groceries"
```

`tests/integration/test_migration_0013.py`

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import AdviceRow, ProposalRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
PROPOSALS = [
    ("id", "INTEGER", False),
    ("kind", "VARCHAR(20)", False),
    ("target_id", "INTEGER", False),
    ("value", "VARCHAR(200)", False),
    ("reason", "VARCHAR(200)", False),
    ("status", "VARCHAR(10)", False),
    ("created_at", "DATETIME", False),
    ("decided_at", "DATETIME", True),
]
ADVICE = [
    ("id", "INTEGER", False),
    ("created_at", "DATETIME", False),
    ("subject", "VARCHAR(100)", False),
    ("text", "VARCHAR(1000)", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0013_follows_0012() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0013")
    assert script.down_revision == "0012"


@pytest.mark.parametrize(
    ("table", "columns", "row", "key"),
    [
        ("proposals", PROPOSALS, ProposalRow, "pk_proposals"),
        ("advice_log", ADVICE, AdviceRow, "pk_advice_log"),
    ],
)
def test_the_tables_and_their_row_classes(
    url: str, table: str, columns: list, row: type, key: str
) -> None:
    command.upgrade(make_config(url), "0013")
    engine = get_engine(url)
    found = inspect(engine)
    shown = [(c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns(table)]
    primary = found.get_pk_constraint(table)
    extras = (
        found.get_unique_constraints(table),
        found.get_foreign_keys(table),
        found.get_indexes(table),
    )
    engine.dispose()
    assert shown == columns
    assert (primary["name"], primary["constrained_columns"]) == (key, ["id"])
    assert extras == ([], [], [])
    assert [(c.name, str(c.type), c.nullable) for c in row.__table__.columns] == columns


def test_down_and_up_again(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0013")
    command.downgrade(config, "0012")
    engine = get_engine(url)
    names = inspect(engine).get_table_names()
    engine.dispose()
    assert "proposals" not in names and "advice_log" not in names
    command.upgrade(config, "0013")
```

`tests/integration/test_proposals.py`

```python
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.categorize.service import categorize
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    accept_proposal,
    create_account,
    create_rule,
    create_transfer_pair,
    decline_proposal,
    list_advice,
    list_category_assignments,
    list_changes,
    list_proposals,
    log_advice,
    propose_category,
    set_category_by_hand,
)
from finances.domain.models import CONFIRMED, MANUAL
from finances.domain.proposals import Advice, Proposal

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """Coffee with no category (1), groceries set by a rule (2), books set by hand (3), and a
    card payment paired as a transfer (4 and 5)."""
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        create_account(opened, "Test Checking", "Test Bank", "checking")
        rows = [
            (1, date(2026, 5, 1), -500, "ACME COFFEE"),
            (1, date(2026, 5, 2), -2599, "FOOBAR GROCERY"),
            (1, date(2026, 5, 3), -1500, "BAZ BOOKS"),
            (2, date(2026, 5, 4), -5000, "PAYMENT TO CARD"),
            (1, date(2026, 5, 5), 5000, "PAYMENT THANK YOU"),
        ]
        for number, (account, day, cents, description) in enumerate(rows, start=1):
            opened.add(
                TransactionRow(
                    account_id=account,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        opened.flush()
        create_rule(opened, "FOOBAR", "Groceries")
        categorize(opened)
        set_category_by_hand(opened, 3, "Education")
        create_transfer_pair(opened, 4, 5, CONFIRMED)
        yield opened


def test_a_proposal_changes_nothing(session: Session) -> None:
    found = propose_category(session, 1, "coffee & dessert", "  ACME is a   coffee shop ")
    assert found == Proposal(
        1, "category", 1, "Coffee & Dessert", "ACME is a coffee shop", "open", NOON, None
    )
    assert 1 not in list_category_assignments(session)
    assert list_proposals(session) == [found]


def test_a_rules_category_can_be_proposed_over(session: Session) -> None:
    assert (
        propose_category(session, 2, "Dining", "FOOBAR GROCERY has a deli counter").value
        == "Dining"
    )


@pytest.mark.parametrize(
    ("transaction_id", "category", "reason", "message"),
    [
        (1, "Dining", "", "a reason must be 1 to 200 characters"),
        (1, "Dining", "x" * 201, "a reason must be 1 to 200 characters"),
        (99, "Dining", "why", "transaction not found"),
        (1, "Nope", "why", "category not found"),
        (1, "Food", "why", "rules and transactions take a category, not a group"),
        (3, "Dining", "why", "a person has already decided this transaction"),
        (4, "Dining", "why", "a person has already decided this transaction"),
    ],
)
def test_refused_proposals(
    session: Session, transaction_id: int, category: str, reason: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        propose_category(session, transaction_id, category, reason)
    assert list_proposals(session) == []


def test_one_open_proposal_per_transaction(session: Session) -> None:
    propose_category(session, 1, "Dining", "first")
    with pytest.raises(ValueError, match="this transaction already has an open proposal"):
        propose_category(session, 1, "Coffee & Dessert", "second")


def test_accepting_is_the_persons_choice(session: Session) -> None:
    propose_category(session, 1, "Coffee & Dessert", "ACME is a coffee shop")
    found = accept_proposal(session, 1)
    assert (found.status, found.decided_at) == ("accepted", NOON)
    assignment = list_category_assignments(session)[1]
    assert (assignment.source, assignment.rule_id) == (MANUAL, None)
    assert [
        (c.who, c.action, c.kind, c.record_id, c.before, c.after) for c in list_changes(session)[:2]
    ] == [
        ("person", "proposal_accepted", "proposal", 1, None, "transaction 1: Coffee & Dessert"),
        ("person", "category_set", "transaction", 1, None, "Coffee & Dessert"),
    ]


def test_an_out_of_date_proposal_cannot_be_accepted(session: Session) -> None:
    propose_category(session, 1, "Coffee & Dessert", "ACME is a coffee shop")
    set_category_by_hand(session, 1, "Dining")
    with pytest.raises(
        ValueError, match="proposal 1 is out of date: the transaction was decided since"
    ):
        accept_proposal(session, 1)
    assert list_proposals(session)[0].status == "open"


def test_declining_and_not_again(session: Session) -> None:
    propose_category(session, 1, "Coffee & Dessert", "ACME is a coffee shop")
    found = decline_proposal(session, 1)
    assert (found.status, found.decided_at) == ("declined", NOON)
    assert 1 not in list_category_assignments(session)
    assert list_changes(session)[0].action == "proposal_declined"
    with pytest.raises(ValueError, match="a person declined this proposal already"):
        propose_category(session, 1, "coffee & dessert", "really")
    assert propose_category(session, 1, "Dining", "then a cafe").id == 2


@pytest.mark.parametrize(
    ("decide", "message"), [(accept_proposal, "accepted"), (decline_proposal, "accepted")]
)
def test_a_decided_proposal_is_not_decided_again(session: Session, decide, message: str) -> None:
    propose_category(session, 1, "Dining", "why")
    accept_proposal(session, 1)
    with pytest.raises(ValueError, match=f"proposal 1 is already {message}"):
        decide(session, 1)
    with pytest.raises(ValueError, match="proposal not found"):
        decide(session, 9)


def test_listing_by_status(session: Session) -> None:
    propose_category(session, 1, "Dining", "one")
    propose_category(session, 2, "Dining", "two")
    decline_proposal(session, 1)
    assert [item.id for item in list_proposals(session)] == [2, 1]
    assert [item.id for item in list_proposals(session, status="open")] == [2]
    assert [item.id for item in list_proposals(session, status="declined", limit=1)] == [1]
    with pytest.raises(ValueError, match="status must be one of: open, accepted, declined"):
        list_proposals(session, status="nope")


def test_the_advice_log(session: Session) -> None:
    first = log_advice(session, "  Suggested a coffee budget.  ", " budgets ")
    second = log_advice(session, "Groceries rose in May.")
    assert first == Advice(1, NOON, "budgets", "Suggested a coffee budget.")
    assert list_advice(session) == [second, first]
    assert list_advice(session, limit=1) == [second]
    for text, subject, message in (
        ("", "", "advice must be 1 to 1000 characters"),
        ("x" * 1001, "", "advice must be 1 to 1000 characters"),
        ("ok", "s" * 101, "a subject is at most 100 characters"),
    ):
        with pytest.raises(ValueError, match=message):
            log_advice(session, text, subject)
```

`tests/integration/test_mcp_proposals.py`

```python
import ast
from datetime import UTC, date, datetime
from pathlib import Path

import anyio
import pytest
from mcp.client import Client

import finances.mcp_server
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, list_category_assignments, set_category_by_hand
from finances.mcp_server.server import build_server

WRITERS = {"propose_category", "log_advice"}
FROM_REPOSITORIES = {
    "account_names",
    "count_uncategorized",
    "get_transaction",
    "list_account_owners",
    "list_accounts",
    "list_advice",
    "list_categories",
    "list_people",
    "list_proposals",
    "list_rules",
    "list_transfer_pairs",
    "list_uncategorized",
    "log_advice",
    "proposal_out_of_date",
    "propose_category",
}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def one(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """A card with one coffee and no category."""
    monkeypatch.setattr(
        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, 1),
                amount_cents=-500,
                description="ACME COFFEE",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
    engine.dispose()
    return tmp_settings


def test_only_two_tools_write_and_none_decides(tmp_settings: Settings) -> None:
    async def go():
        async with Client(build_server()) as client:
            return (await client.list_tools()).tools

    tools = {tool.name: tool for tool in anyio.run(go)}
    assert {name for name, tool in tools.items() if not tool.annotations.read_only_hint} == WRITERS
    for name in WRITERS:
        assert tools[name].annotations.destructive_hint is False
    assert not [name for name in tools if "accept" in name or "decline" in name]


def test_the_server_reaches_only_these_repository_functions() -> None:
    folder = Path(finances.mcp_server.__file__).parent
    names = set()
    for path in folder.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module == "finances.db.repositories":
                names |= {alias.name for alias in node.names}
    assert names == FROM_REPOSITORIES


def test_a_proposal_and_its_listing(one: Settings) -> None:
    made = call(
        "propose_category",
        {"transaction_id": 1, "category": "Coffee & Dessert", "reason": "a cafe"},
    )
    expected = {
        "id": 1,
        "kind": "category",
        "transaction_id": 1,
        "category": "Coffee & Dessert",
        "reason": "a cafe",
        "status": "open",
        "created_at": "2026-05-25T12:00:00+00:00",
        "decided_at": None,
        "out_of_date": False,
    }
    assert made.structured_content == {"proposal": expected}
    engine = get_engine()
    with session_scope(engine) as session:
        assert list_category_assignments(session) == {}
        set_category_by_hand(session, 1, "Dining")
    engine.dispose()
    assert call("list_proposals").structured_content == {
        "proposals": [{**expected, "out_of_date": True}]
    }
    assert call("list_proposals", {"status": "declined"}).structured_content == {"proposals": []}


def test_a_refused_proposal(one: Settings) -> None:
    result = call("propose_category", {"transaction_id": 9, "category": "Dining", "reason": "why"})
    assert [item.text for item in result.content] == [
        "Error executing tool propose_category: transaction not found"
    ]


def test_the_agents_notes(one: Settings) -> None:
    kept = call("log_advice", {"text": "Suggested a coffee budget.", "subject": "budgets"})
    note = {
        "id": 1,
        "created_at": "2026-05-25T12:00:00+00:00",
        "subject": "budgets",
        "text": "Suggested a coffee budget.",
    }
    assert kept.structured_content == {"advice": note}
    assert call("list_advice").structured_content == {"advice": [note]}
    refused = call("log_advice", {"text": "  "})
    assert [item.text for item in refused.content] == [
        "Error executing tool log_advice: advice must be 1 to 1000 characters"
    ]


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("propose_category", {"transaction_id": 1, "category": "Dining", "reason": "why"}),
        ("log_advice", {"text": "note"}),
    ],
)
def test_a_database_that_is_not_migrated(
    tmp_settings: Settings, tool: str, arguments: dict
) -> None:
    assert [item.text for item in call(tool, arguments).content] == [
        f"Error executing tool {tool}: The database is not up to date. Run: fin db upgrade"
    ]
```

`tests/e2e/test_cli_review.py`

```python
from datetime import UTC, date, datetime

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, propose_category, set_category_by_hand
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, run, table_rows

HEADINGS = ["ID", "Date", "Account", "Description", "Amount", "Now", "Proposed", "Reason", "State"]


@pytest.fixture
def proposed(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Two coffees on a card with the agent's proposals (1 and 2)."""
    monkeypatch.setattr(
        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    )
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, description in ((1, "ACME COFFEE"), (2, "BAZ CAFE")):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, number),
                    amount_cents=-500,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        propose_category(session, 1, "Coffee & Dessert", "ACME is a coffee shop")
        propose_category(session, 2, "Dining", "BAZ CAFE serves lunch")
    engine.dispose()
    return tmp_settings


def test_the_open_proposals(proposed: Settings) -> None:
    result = run("review", "list")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        HEADINGS,
        [
            "2",
            "2026-05-02",
            "Test Card",
            "BAZ CAFE",
            "-$5.00",
            "",
            "Dining",
            "BAZ CAFE serves lunch",
            "open",
        ],
        [
            "1",
            "2026-05-01",
            "Test Card",
            "ACME COFFEE",
            "-$5.00",
            "",
            "Coffee & Dessert",
            "ACME is a coffee shop",
            "open",
        ],
    ]


def test_accepting_and_declining(proposed: Settings) -> None:
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: Coffee & Dessert for transaction 1.\n",
    )
    declined = run("review", "decline", "--id", "2")
    assert (declined.exit_code, declined.stdout) == (0, "Declined proposal 2.\n")
    assert run("review", "list").stdout == "No open proposals.\n"
    assert [row[1:] for row in table_rows(run("audit", "--limit", "3").stdout)[1:]] == [
        ["person", "proposal_declined", "proposal 2", "", "transaction 2: Dining"],
        ["person", "proposal_accepted", "proposal 1", "", "transaction 1: Coffee & Dessert"],
        ["person", "category_set", "transaction 1", "", "Coffee & Dessert"],
    ]


def test_an_out_of_date_proposal_shows_and_is_refused(proposed: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        set_category_by_hand(session, 1, "Dining")
    engine.dispose()
    rows = table_rows(run("review", "list").stdout)
    assert rows[2][5:] == ["Dining", "Coffee & Dessert", "ACME is a coffee shop", "out of date"]
    assert failed_cleanly(
        run("review", "accept", "--id", "1"),
        "proposal 1 is out of date: the transaction was decided since",
    )


def test_all_or_none(proposed: Settings) -> None:
    assert failed_cleanly(run("review", "accept", "--id", "2", "--id", "9"), "proposal not found")
    assert len(table_rows(run("review", "list").stdout)) == 3


def test_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = run("review", "list")
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)
```

The diff to earlier tests (apply it exactly):

```text
diff --git a/tests/e2e/test_cli_audit.py b/tests/e2e/test_cli_audit.py
index 5219c98..ec4f964 100644
--- a/tests/e2e/test_cli_audit.py
+++ b/tests/e2e/test_cli_audit.py
@@ -59,7 +59,8 @@ UNKNOWN = (
     "eopened, owner_set, person_added, cardholder_set, category_added, category_renam"
     "ed, category_deleted, rule_added, rule_edited, rule_deleted, category_set, categ"
     "ory_cleared, budget_set, budget_removed, transfer_confirmed, transfer_rejected, "
-    "transfer_unpaired, statement_imported, backup_deleted, backup_restored"
+    "transfer_unpaired, statement_imported, backup_deleted, backup_restored, proposal"
+    "_accepted, proposal_declined"
 )
 
 
diff --git a/tests/integration/test_mcp_accounts.py b/tests/integration/test_mcp_accounts.py
index 748d079..98a9d55 100644
--- a/tests/integration/test_mcp_accounts.py
+++ b/tests/integration/test_mcp_accounts.py
@@ -20,7 +20,15 @@ from finances.domain.models import DataSource
 from finances.mcp_server.access import reading
 from finances.mcp_server.server import INSTRUCTIONS, build_server
 
-NO_AMOUNTS = ("list_accounts", "list_categories", "list_rules", "find_merchants")
+NO_AMOUNTS = (
+    "list_accounts",
+    "list_categories",
+    "list_rules",
+    "find_merchants",
+    "propose_category",
+    "list_proposals",
+    "list_advice",
+)
 READ_ONLY = {
     "read_only_hint": True,
     "destructive_hint": False,
@@ -84,16 +92,21 @@ def test_the_server_and_its_tools(tmp_settings: Settings) -> None:
         "get_spending",
         "get_upcoming",
         "list_accounts",
+        "list_advice",
         "list_categories",
+        "list_proposals",
         "list_rules",
         "list_transactions",
         "list_transfer_suggestions",
         "list_transfers",
         "list_uncategorized",
+        "log_advice",
         "month_over_month",
+        "propose_category",
     ]
     for tool in tools:
-        assert tool.annotations.model_dump(include=set(READ_ONLY)) == READ_ONLY, tool.name
+        if tool.name not in ("propose_category", "log_advice"):
+            assert tool.annotations.model_dump(include=set(READ_ONLY)) == READ_ONLY, tool.name
         assert "cents" in tool.description or tool.name in NO_AMOUNTS, tool.name
 
 
diff --git a/tests/integration/test_mcp_coverage.py b/tests/integration/test_mcp_coverage.py
index a086ec8..30f9a9e 100644
--- a/tests/integration/test_mcp_coverage.py
+++ b/tests/integration/test_mcp_coverage.py
@@ -30,13 +30,17 @@ TOOLS = [
     "get_spending",
     "get_upcoming",
     "list_accounts",
+    "list_advice",
     "list_categories",
+    "list_proposals",
     "list_rules",
     "list_transactions",
     "list_transfer_suggestions",
     "list_transfers",
     "list_uncategorized",
+    "log_advice",
     "month_over_month",
+    "propose_category",
 ]
 
 
@@ -124,7 +128,11 @@ def test_eighteen_read_only_tools(tmp_settings: Settings) -> None:
 
     found = anyio.run(go)
     assert sorted(tool.name for tool in found) == TOOLS
-    assert all(tool.annotations.read_only_hint for tool in found)
+    assert all(
+        tool.annotations.read_only_hint
+        for tool in found
+        if tool.name not in ("propose_category", "log_advice")
+    )
 
 
 def test_data_coverage(data: Settings) -> None:
diff --git a/tests/integration/test_mcp_more.py b/tests/integration/test_mcp_more.py
index abd4778..a89a368 100644
--- a/tests/integration/test_mcp_more.py
+++ b/tests/integration/test_mcp_more.py
@@ -24,13 +24,17 @@ from finances.mcp_server.server import (
     GET_SPENDING_DESCRIPTION,
     GET_UPCOMING_DESCRIPTION,
     LIST_ACCOUNTS_DESCRIPTION,
+    LIST_ADVICE_DESCRIPTION,
     LIST_CATEGORIES_DESCRIPTION,
+    LIST_PROPOSALS_DESCRIPTION,
     LIST_RULES_DESCRIPTION,
     LIST_TRANSACTIONS_DESCRIPTION,
     LIST_TRANSFER_SUGGESTIONS_DESCRIPTION,
     LIST_TRANSFERS_DESCRIPTION,
     LIST_UNCATEGORIZED_DESCRIPTION,
+    LOG_ADVICE_DESCRIPTION,
     MONTH_OVER_MONTH_DESCRIPTION,
+    PROPOSE_CATEGORY_DESCRIPTION,
     build_server,
 )
 from tests.support import run
@@ -150,6 +154,10 @@ def test_each_tool_description_matches_the_table(tmp_settings: Settings) -> None
         "list_transfer_suggestions": LIST_TRANSFER_SUGGESTIONS_DESCRIPTION,
         "data_coverage": DATA_COVERAGE_DESCRIPTION,
         "find_merchants": FIND_MERCHANTS_DESCRIPTION,
+        "propose_category": PROPOSE_CATEGORY_DESCRIPTION,
+        "list_proposals": LIST_PROPOSALS_DESCRIPTION,
+        "log_advice": LOG_ADVICE_DESCRIPTION,
+        "list_advice": LIST_ADVICE_DESCRIPTION,
     }
 
 
diff --git a/tests/integration/test_mcp_outlook.py b/tests/integration/test_mcp_outlook.py
index 2e645be..03205a0 100644
--- a/tests/integration/test_mcp_outlook.py
+++ b/tests/integration/test_mcp_outlook.py
@@ -32,13 +32,17 @@ TOOLS = [
     "get_spending",
     "get_upcoming",
     "list_accounts",
+    "list_advice",
     "list_categories",
+    "list_proposals",
     "list_rules",
     "list_transactions",
     "list_transfer_suggestions",
     "list_transfers",
     "list_uncategorized",
+    "log_advice",
     "month_over_month",
+    "propose_category",
 ]
 CHECKING = {
     "account": "Test Checking",
@@ -215,7 +219,11 @@ def test_the_read_only_tools(tmp_settings: Settings) -> None:
 
     found = anyio.run(go)
     assert sorted(tool.name for tool in found) == TOOLS
-    assert all(tool.annotations.read_only_hint for tool in found)
+    assert all(
+        tool.annotations.read_only_hint
+        for tool in found
+        if tool.name not in ("propose_category", "log_advice")
+    )
 
 
 def test_recurring_charges_are_negative(ahead: Settings) -> None:
diff --git a/tests/integration/test_mcp_queues.py b/tests/integration/test_mcp_queues.py
index 1a06755..6747823 100644
--- a/tests/integration/test_mcp_queues.py
+++ b/tests/integration/test_mcp_queues.py
@@ -26,13 +26,17 @@ TOOLS = [
     "get_spending",
     "get_upcoming",
     "list_accounts",
+    "list_advice",
     "list_categories",
+    "list_proposals",
     "list_rules",
     "list_transactions",
     "list_transfer_suggestions",
     "list_transfers",
     "list_uncategorized",
+    "log_advice",
     "month_over_month",
+    "propose_category",
 ]
 TO_SAVINGS = {
     "id": 4,
@@ -141,7 +145,11 @@ def test_the_read_only_tools(tmp_settings: Settings) -> None:
 
     found = anyio.run(go)
     assert sorted(tool.name for tool in found) == TOOLS
-    assert all(tool.annotations.read_only_hint for tool in found)
+    assert all(
+        tool.annotations.read_only_hint
+        for tool in found
+        if tool.name not in ("propose_category", "log_advice")
+    )
 
 
 def test_uncategorized_latest_first_with_the_total(queues: Settings) -> None:
diff --git a/tests/integration/test_mcp_spending.py b/tests/integration/test_mcp_spending.py
index 9c56dd5..0c29785 100644
--- a/tests/integration/test_mcp_spending.py
+++ b/tests/integration/test_mcp_spending.py
@@ -25,13 +25,17 @@ TOOLS = [
     "get_spending",
     "get_upcoming",
     "list_accounts",
+    "list_advice",
     "list_categories",
+    "list_proposals",
     "list_rules",
     "list_transactions",
     "list_transfer_suggestions",
     "list_transfers",
     "list_uncategorized",
+    "log_advice",
     "month_over_month",
+    "propose_category",
 ]
 REFUND = {
     "id": 2,
@@ -116,7 +120,9 @@ def test_the_read_only_tools(tmp_settings: Settings) -> None:
     found = anyio.run(go)
     assert sorted(tool.name for tool in found) == TOOLS
     for tool in found:
-        assert tool.annotations.read_only_hint is True, tool.name
+        assert tool.annotations.read_only_hint is (
+            tool.name not in ("propose_category", "log_advice")
+        ), tool.name
 
 
 def test_every_transaction_latest_first(money: Settings) -> None:
diff --git a/tests/unit/test_audit_rules.py b/tests/unit/test_audit_rules.py
index 17e3b52..a05c140 100644
--- a/tests/unit/test_audit_rules.py
+++ b/tests/unit/test_audit_rules.py
@@ -28,6 +28,8 @@ def test_the_lists() -> None:
         "statement_imported",
         "backup_deleted",
         "backup_restored",
+        "proposal_accepted",
+        "proposal_declined",
     )
     assert KINDS == (
         "account",
@@ -38,6 +40,7 @@ def test_the_lists() -> None:
         "transfer",
         "statement",
         "backup",
+        "proposal",
     )
     assert AUDIT_TEXT_LIMIT == 200
 
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index 82139bb..8ebe3b0 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -80,6 +80,16 @@ HOMES = {
         "record_sync_failure",
         "set_feed_account_ignored",
     ],
+    "proposals": [
+        "accept_proposal",
+        "decided_by_a_person",
+        "decline_proposal",
+        "list_advice",
+        "list_proposals",
+        "log_advice",
+        "proposal_out_of_date",
+        "propose_category",
+    ],
     "people": [
         "PersonExistsError",
         "create_person",
@@ -130,7 +140,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 88
+    assert len(expected) == 96
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
```

## Tests to write

`tests/integration/test_proposals_more.py`: a proposal made without replacing `_now` is stamped in UTC; `list_proposals` and `list_advice` refuse a limit of 0; a proposal whose transaction was deleted is out of date (and `fin review list` shows it with empty transaction cells); accepting a proposal whose category was deleted since is refused with `category not found`; `fin review decline` with two ids.

## Rules for this phase

- **The agent recommends; it does not act.** No tool accepts, declines, or edits a proposal; the only writes reachable from `mcp_server` are `propose_category` and `log_advice` (the given test pins every repository name the server imports).
- Accepting goes through `set_category_by_hand`, so the change is recorded as the person's.
- No proposal or note is logged anywhere but the database; reasons and notes are the agent's text and stay local.
- One migration, given; never edit an earlier one.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_proposal_rules.py tests/integration/test_migration_0013.py tests/integration/test_proposals.py tests/integration/test_mcp_proposals.py tests/e2e/test_cli_review.py`, 39 tests; at least N + 39 passed in all;
- `git diff --stat HEAD -- tests` lists only the nine files of the given diff;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.proposals --cov=finances.db.repositories --cov=finances.analysis.review --cov=finances.views.review --cov=finances.cli.review --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` and `git grep -n --untracked -E "\.(debug|info|warning|error|exception|critical)\(|print\(" -- src/finances/mcp_server src/finances/cli/mcp.py`, no output.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 19a: proposals and the advice log (YYYY-MM-DD)`.
