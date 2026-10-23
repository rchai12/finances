# Phase 19d: the agent proposes rules

## Goal

The agent can suggest a categorizing rule, and only suggest. After this phase:

- a new MCP tool, `propose_rule`, writes a proposal for a rule (a pattern, how it matches, a priority, and a category) with an **example** transaction the rule matches and a one-line reason a person will read;
- a person decides it as they decide every other proposal, in `fin review` and on the Review page: accepting it adds the rule through `create_rule`, so the audit trail shows the person's choice, and then **the rules run once** over every transaction, as they do after `fin rules add`;
- a rule proposal is **out of date** once a rule with the same match and pattern exists, or its category no longer exists under that name.

One migration adds the rule's pattern, match, and priority to `proposals`. Phase 19 ends here; merchant alias and finding-status proposals join after Phase 28.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-19a-proposals-and-advice.md`, `docs/phases/phase-19c-transfer-proposals.md`
- `src/finances/domain/proposals.py`, `src/finances/domain/rules.py` (`normalize_pattern`, `rule_matches`, `MATCHES`), `src/finances/domain/merchants.py` (`clean_merchant`), `src/finances/domain/audit.py` (`rule_text`)
- `src/finances/db/repositories/proposals.py`, `src/finances/db/repositories/categories.py` (`create_rule`, `_category_row`, `_leaf_category`)
- `src/finances/categorize/service.py`, `src/finances/views/review.py`, `src/finances/views/categories.py` (`categorized_text`), `src/finances/cli/review.py`, `src/finances/web/routes/review.py`
- `src/finances/mcp_server/tools.py` (`_proposal_item`, `propose_transfer`), `src/finances/mcp_server/server.py`

## Starting state

N is `3450` when Phase 19c is the last phase built. The newest migration is `0014`. No rules are seeded; `Food` is a seeded group and `Dining`, `Groceries`, and `Coffee & Dessert` are categories in it. A categorize run writes no audit rows.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0015_proposal_rules.py` | new: given (R1) |
| `src/finances/db/orm.py` | `ProposalRow.pattern`, `match`, `priority`; `to_proposal` (R1) |
| `src/finances/domain/proposals.py` | `RULE`, `Proposal`'s three fields, `rule_out_of_date`, `proposal_text` (R2) |
| `src/finances/db/repositories/proposals.py`, `src/finances/db/repositories/__init__.py` | `propose_rule`; out of date and accepting for a rule (R3 to R5) |
| `src/finances/categorize/service.py` | `Accepted`, `accept_proposals` (R6) |
| `src/finances/views/review.py` | `proposed_text`, `accepted_text` for a rule (R7) |
| `src/finances/cli/review.py`, `src/finances/web/routes/review.py` | accepting through `accept_proposals` (R8) |
| `src/finances/mcp_server/tools.py`, `server.py` | the tool; `"rule"` on every proposal item (R9) |
| `tests/support.py` and eight earlier test files | the given diff (R10) |
| `tests/integration/test_migration_0015.py`, `tests/integration/test_mcp_rule_proposals.py` | new: given |
| `tests/unit/test_rule_proposal_rules.py`, `tests/integration/test_rule_proposals.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Merchant alias and finding-status proposals (after Phase 28); a proposal to edit or delete a rule.
- Pairing transfers after the run (the web's rule form does not either); any change to `fin rules`, the Categories page, the Review page's template, or `open_suggestions`.
- A count of the transactions a proposed rule would change; any tool that accepts, declines, or adds a rule itself.

## Dependencies

None new. One migration, given below.

## Design

```python
# src/finances/domain/proposals.py
RULE = "rule"
KINDS = (CATEGORY, TRANSFER, NOT_TRANSFER, RULE)

@dataclass(frozen=True)
class Proposal:
    ...                          # the fields of 19c, unchanged and in order
    pattern: str | None = None   # a rule proposal's pattern, as normalize_pattern stores it
    match: str | None = None     # a rule proposal's match; None for the other kinds
    priority: int | None = None  # a rule proposal's priority; None for the other kinds

def rule_out_of_date(*, category_found: bool, rule_exists: bool) -> bool: ...
def proposal_text(proposal: Proposal) -> str: ...
# 19c's three texts, and for a rule "rule: " + rule_text(match, pattern, value, priority):
# 'rule: equals "ACME COFFEE" -> Dining (priority 5)'

# src/finances/db/repositories/proposals.py
def propose_rule(
    session: Session,
    example_id: int,
    pattern: str,
    category: str,
    reason: str,
    *,
    match: str = "contains",
    priority: int = 0,
) -> Proposal: ...

# src/finances/categorize/service.py
@dataclass(frozen=True)
class Accepted:
    proposals: list[Proposal]             # each accepted proposal, in the order asked
    categorized: CategorizeResult | None  # the run after them; None when none was a rule

def accept_proposals(session: Session, proposal_ids: list[int]) -> Accepted: ...

# src/finances/views/review.py
def proposed_text(proposal: Proposal) -> str: ...
# for a rule: 'a rule: equals "ACME COFFEE" -> Dining (priority 5)'
def accepted_text(proposal: Proposal) -> str: ...
# for a rule: 'Accepted proposal 1: a rule, equals "ACME COFFEE" -> Dining (priority 5).'

# src/finances/mcp_server/tools.py
def propose_rule(
    example_id: int,
    pattern: str,
    category: str,
    reason: str,
    match: Literal["contains", "starts_with", "equals"] = "contains",
    priority: Annotated[int, Field(ge=-1000, le=1000)] = 0,
) -> dict[str, Any]: ...

# src/finances/mcp_server/server.py
PROPOSE_RULE_DESCRIPTION = (
    "Propose a rule that puts every transaction whose merchant matches pattern in a category "
    "(match: contains, starts_with, or equals; priority -1000 to 1000, higher tried first), "
    "with an example transaction it matches and a one-line reason a person will read. It "
    "changes nothing until a person accepts it; then the rules run over every transaction. "
    "Refused when it does not match the example, a rule with this pattern and match exists, a "
    "person declined it, or another proposal for it is open. No amounts."
)
```

## Requirements

### Storage and rules

- **R1.** Add the given migration exactly. `ProposalRow` gains, after `other_id` and in this order, `pattern` (`String(RULE_PATTERN_LIMIT)`), `match` (`String(12)`), and `priority` (`Integer`), all nullable; `to_proposal` reads them.
- **R2.** `domain/proposals.py` as designed. `rule_out_of_date` is true when the category is not found or the rule exists. `proposal_text` of a rule is `rule: ` followed by `finances.domain.audit.rule_text` of its match, pattern, category (`value`), and priority.

### Proposing and deciding

- **R3.** `propose_rule` checks, in this order, and refuses with `ValueError`:
  1. the reason, with runs of white space made one space, is 1 to 200 characters (`a reason must be 1 to 200 characters`);
  2. the pattern, after `normalize_pattern`, is 1 to `RULE_PATTERN_LIMIT` characters (`a rule pattern must be 1 to 100 characters`);
  3. `match` is in `MATCHES` (`match must be one of: contains, starts_with, equals`);
  4. the example transaction exists (`transaction not found`);
  5. the category is a category by `_leaf_category` (its own messages);
  6. the rule matches the example: `rule_matches` on `clean_merchant` of the example's description, the same test a categorize run makes (`the rule does not match the example transaction`);
  7. no rule has this match and pattern (`a rule with this pattern and match already exists`);
  8. no **declined** rule proposal has this match, pattern, and category; the priority does not count (`a person declined this proposal already`);
  9. no **open** rule proposal has this match and pattern, whatever its category (`this rule already has an open proposal`).

  It stores an open proposal with `target_id` the example, `value` the category's own name, `other_id` None, the normalized pattern, the match, and the priority; stamps `created_at` with `_now()`; flushes; and returns it. Nothing else changes. It is re-exported from `finances.db.repositories`.
- **R4.** `proposal_out_of_date` of a rule proposal applies `rule_out_of_date`: `category_found` when a category (not a group) has the stored name, ignoring case as `_category_row` does; `rule_exists` when a rule has the stored match and pattern.
- **R5.** `accept_proposal` refuses a rule proposal out of date with `proposal N is out of date: the rules or categories changed since` (the other kinds keep their messages), then calls `create_rule(session, pattern, value, match, priority)`, and marks and records the proposal as for the other kinds. It does not run the rules; nothing in `finances.db` imports `finances.categorize`.
- **R6.** `accept_proposals` calls `accept_proposal` for each id in order; a `ValueError` passes to the caller, which rolls the session back, so a list is accepted all or none. When at least one accepted proposal is a rule, it runs `categorize(session)` **once, after the last**, and returns its result in `categorized`; otherwise `categorized` is None and the rules do not run.

### Showing and the tools

- **R7.** `proposed_text` and `accepted_text` of a rule as designed: `a rule: ` and `a rule, ` followed by `rule_text`; the other kinds' texts are unchanged.
- **R8.** `fin review accept` accepts through `accept_proposals` in one session and prints each accepted line, then, when `categorized` is not None, `categorized_text(categorized)` as the last line. The Review page's `accept` decision goes through `accept_proposals`, with 19b's notice and errors. `decline` is unchanged in both.
- **R9.** Every proposal item of the tools gains `"rule"`: `{"match": ..., "pattern": ..., "priority": ...}` for a rule proposal, null for the other kinds; `"category"` is the stored category for a category or a rule proposal and null for a pair. `propose_rule` returns `{"proposal": {...}}` through `writing()`, and a `ValueError` becomes a `ToolError` with its message. It is registered with `WRITES_PROPOSALS` and `PROPOSE_RULE_DESCRIPTION` after `propose_not_transfer`, and is in `_WRITES`. `mcp_server` imports from `finances.db.repositories` exactly the names the given diff lists.
- **R10.** Apply the given diff to `tests/support.py` and eight earlier test files: the tool lists, writers, cents exemptions, description table, and repository names gain `propose_rule`; `KINDS` has four entries; three pinned proposal items gain `"rule": None`; the 0014 migration test compares the columns it made. No other earlier test changes.

## Given migration

`src/finances/db/migrations/versions/0015_proposal_rules.py` (do not change)

```python
"""Add proposals.pattern, match, and priority: the rule a rule proposal would add."""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.add_column(sa.Column("pattern", sa.String(100), nullable=True))
        batch.add_column(sa.Column("match", sa.String(12), nullable=True))
        batch.add_column(sa.Column("priority", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.drop_column("priority")
        batch.drop_column("match")
        batch.drop_column("pattern")
```

## Given diff to earlier tests

```text
diff --git a/tests/integration/test_mcp_accounts.py b/tests/integration/test_mcp_accounts.py
index cd63053..e98c16d 100644
--- a/tests/integration/test_mcp_accounts.py
+++ b/tests/integration/test_mcp_accounts.py
@@ -31,6 +31,7 @@ NO_AMOUNTS = (
     "list_advice",
     "propose_transfer",
     "propose_not_transfer",
+    "propose_rule",
 )
 READ_ONLY = {
     "read_only_hint": True,
diff --git a/tests/integration/test_mcp_more.py b/tests/integration/test_mcp_more.py
index 21d08ea..5581d53 100644
--- a/tests/integration/test_mcp_more.py
+++ b/tests/integration/test_mcp_more.py
@@ -36,6 +36,7 @@ from finances.mcp_server.server import (
     MONTH_OVER_MONTH_DESCRIPTION,
     PROPOSE_CATEGORY_DESCRIPTION,
     PROPOSE_NOT_TRANSFER_DESCRIPTION,
+    PROPOSE_RULE_DESCRIPTION,
     PROPOSE_TRANSFER_DESCRIPTION,
     build_server,
 )
@@ -159,6 +160,7 @@ def test_each_tool_description_matches_the_table(tmp_settings: Settings) -> None
         "propose_category": PROPOSE_CATEGORY_DESCRIPTION,
         "propose_transfer": PROPOSE_TRANSFER_DESCRIPTION,
         "propose_not_transfer": PROPOSE_NOT_TRANSFER_DESCRIPTION,
+        "propose_rule": PROPOSE_RULE_DESCRIPTION,
         "list_proposals": LIST_PROPOSALS_DESCRIPTION,
         "log_advice": LOG_ADVICE_DESCRIPTION,
         "list_advice": LIST_ADVICE_DESCRIPTION,
diff --git a/tests/integration/test_mcp_proposals.py b/tests/integration/test_mcp_proposals.py
index e07ff2e..f5ffcc0 100644
--- a/tests/integration/test_mcp_proposals.py
+++ b/tests/integration/test_mcp_proposals.py
@@ -33,6 +33,7 @@ FROM_REPOSITORIES = {
     "proposal_out_of_date",
     "propose_category",
     "propose_not_transfer",
+    "propose_rule",
     "propose_transfer",
 }
 
@@ -102,6 +103,7 @@ def test_a_proposal_and_its_listing(one: Settings) -> None:
         "transaction_id": 1,
         "in_id": None,
         "category": "Coffee & Dessert",
+        "rule": None,
         "reason": "a cafe",
         "status": "open",
         "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_transfer_proposals.py b/tests/integration/test_mcp_transfer_proposals.py
index 5571d59..4a66ce4 100644
--- a/tests/integration/test_mcp_transfer_proposals.py
+++ b/tests/integration/test_mcp_transfer_proposals.py
@@ -58,6 +58,7 @@ def test_the_agent_proposes_a_transfer(moved: Settings) -> None:
             "transaction_id": 1,
             "in_id": 2,
             "category": None,
+            "rule": None,
             "reason": "same day, same amount",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_migration_0014.py b/tests/integration/test_migration_0014.py
index d73295f..2e17af4 100644
--- a/tests/integration/test_migration_0014.py
+++ b/tests/integration/test_migration_0014.py
@@ -38,9 +38,9 @@ def test_other_id_comes_and_goes(tmp_path: Path) -> None:
     config = make_config(url)
     command.upgrade(config, "0014")
     assert columns(url)[-1] == ("other_id", "INTEGER", True)
-    assert [(c.name, str(c.type), c.nullable) for c in ProposalRow.__table__.columns] == columns(
-        url
-    )
+    found = columns(url)
+    orm = [(c.name, str(c.type), c.nullable) for c in ProposalRow.__table__.columns]
+    assert orm[: len(found)] == found
     command.downgrade(config, "0013")
     assert "other_id" not in [name for name, _, _ in columns(url)]
     command.upgrade(config, "0014")
diff --git a/tests/integration/test_transfer_proposals_more.py b/tests/integration/test_transfer_proposals_more.py
index 59333fd..e0254a3 100644
--- a/tests/integration/test_transfer_proposals_more.py
+++ b/tests/integration/test_transfer_proposals_more.py
@@ -35,6 +35,7 @@ PAIR = {
     "transaction_id": 1,
     "in_id": 2,
     "category": None,
+    "rule": None,
     "reason": "interest, not a transfer",
     "status": "open",
     "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/support.py b/tests/support.py
index e893bc9..e6bdf34 100644
--- a/tests/support.py
+++ b/tests/support.py
@@ -174,6 +174,13 @@ MCP_TOOLS = [
     "month_over_month",
     "propose_category",
     "propose_not_transfer",
+    "propose_rule",
     "propose_transfer",
 ]
-MCP_WRITERS = ("propose_category", "propose_transfer", "propose_not_transfer", "log_advice")
+MCP_WRITERS = (
+    "propose_category",
+    "propose_transfer",
+    "propose_not_transfer",
+    "propose_rule",
+    "log_advice",
+)
diff --git a/tests/unit/test_proposal_rules.py b/tests/unit/test_proposal_rules.py
index 9664019..43da418 100644
--- a/tests/unit/test_proposal_rules.py
+++ b/tests/unit/test_proposal_rules.py
@@ -17,7 +17,7 @@ from finances.domain.text import ADVICE_TEXT_LIMIT, PROPOSAL_TEXT_LIMIT
 
 
 def test_the_lists_and_limits() -> None:
-    assert (CATEGORY, KINDS) == ("category", ("category", "transfer", "not_transfer"))
+    assert (CATEGORY, KINDS) == ("category", ("category", "transfer", "not_transfer", "rule"))
     assert (OPEN, ACCEPTED, DECLINED, STATUSES) == (
         "open",
         "accepted",
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index a5ef476..fed3cfe 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -90,6 +90,7 @@ HOMES = {
         "proposal_out_of_date",
         "propose_category",
         "propose_not_transfer",
+        "propose_rule",
         "propose_transfer",
     ],
     "people": [
@@ -142,7 +143,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 98
+    assert len(expected) == 99
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
```

## Given tests

5 tests in two files. Do not change them.

`tests/integration/test_migration_0015.py`

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import ProposalRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
ADDED = [
    ("pattern", "VARCHAR(100)", True),
    ("match", "VARCHAR(12)", True),
    ("priority", "INTEGER", True),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


def columns(url: str) -> list[tuple]:
    engine = get_engine(url)
    found = [
        (c["name"], str(c["type"]), c["nullable"]) for c in inspect(engine).get_columns("proposals")
    ]
    engine.dispose()
    return found


def test_0015_follows_0014() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0015")
    assert script.down_revision == "0014"


def test_the_rule_columns_come_and_go(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = make_config(url)
    command.upgrade(config, "0015")
    found = columns(url)
    assert found[-3:] == ADDED
    orm = [(c.name, str(c.type), c.nullable) for c in ProposalRow.__table__.columns]
    assert orm[: len(found)] == found
    command.downgrade(config, "0014")
    assert columns(url)[-1] == ("other_id", "INTEGER", True)
    command.upgrade(config, "0015")
    assert columns(url)[-3:] == ADDED
```

`tests/integration/test_mcp_rule_proposals.py`

```python
from datetime import UTC, date, datetime

import anyio
import pytest
from mcp.client import Client

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from finances.mcp_server.server import build_server
from tests.support import run, table_rows

PROPOSED = {
    "example_id": 1,
    "pattern": "acme   coffee",
    "category": "dining",
    "reason": "a cafe",
    "match": "equals",
    "priority": 5,
}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Two card purchases: 1 cleans to ACME COFFEE, 2 to FOOBAR GROCERY. No rules."""
    monkeypatch.setattr(
        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-700, "SQ *ACME COFFEE 12345"), (-3000, "FOOBAR GROCERY")), start=1
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
    engine.dispose()
    return tmp_settings


def test_the_agent_proposes_a_rule(card: Settings) -> None:
    made = call("propose_rule", PROPOSED)
    assert made.structured_content == {
        "proposal": {
            "id": 1,
            "kind": "rule",
            "transaction_id": 1,
            "in_id": None,
            "category": "Dining",
            "rule": {"match": "equals", "pattern": "ACME COFFEE", "priority": 5},
            "reason": "a cafe",
            "status": "open",
            "created_at": "2026-05-25T12:00:00+00:00",
            "decided_at": None,
            "out_of_date": False,
        }
    }


def test_a_refused_rule(card: Settings) -> None:
    refused = call("propose_rule", {**PROPOSED, "pattern": "TEA"})
    assert [item.text for item in refused.content] == [
        "Error executing tool propose_rule: the rule does not match the example transaction"
    ]


def test_a_person_accepts_it_in_the_terminal(card: Settings) -> None:
    call("propose_rule", PROPOSED)
    rows = table_rows(run("review", "list").stdout)
    assert rows[1] == [
        "1",
        "2026-05-01",
        "Test Card",
        "SQ *ACME COFFEE 12345",
        "-$7.00",
        "",
        'a rule: equals "ACME COFFEE" -> Dining (priority 5)',
        "a cafe",
        "open",
    ]
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        'Accepted proposal 1: a rule, equals "ACME COFFEE" -> Dining (priority 5).\n'
        "Categorized 2 transactions: 1 changed, 1 without a category.\n",
    )
```

## Tests to write

Each case below names the input that decides it; the test must use that input or one that decides the same way.

`tests/unit/test_rule_proposal_rules.py`:

- `RULE` and `KINDS`; `rule_out_of_date` for each of its three outcomes; `proposal_text` of a rule (`'rule: equals "ACME COFFEE" -> Dining (priority 5)'`); the three new fields default to None.

`tests/integration/test_rule_proposals.py`, on four card purchases: 1 `SQ *ACME COFFEE 12345`, 2 `ACME COFFEE #12` (both clean to `ACME COFFEE`), 3 `ACME COFFEE ROASTERS`, 4 `FOOBAR GROCERY`:

- a stored proposal compared whole (pattern ` acme   coffee ` stored as `ACME COFFEE`, category `dining` stored as `Dining`), with no rule added and no category set;
- each refusal of R3 once, nothing stored. The reason case also has a blank pattern, so the order of checks 1 and 2 decides it;
- `equals "ACME COFFEE"` with example 1 is accepted: the example is matched by its cleaned merchant, not its description;
- after `create_rule("acme coffee", "Dining", "equals")`, the same rule is refused but `contains "ACME COFFEE"` is stored;
- after declining `contains "ACME COFFEE" -> Dining`, the same at priority 9 is refused and the same with `Coffee & Dessert` is stored;
- with `contains "ACME COFFEE" -> Dining` open, `contains "acme coffee" -> Coffee & Dessert` (example 3) is refused;
- accepting `equals "ACME COFFEE" -> Dining (priority 5)` returns `Accepted([the accepted proposal], CategorizeResult(4, 2, 2))`, sets 1 and 2 only, and records `proposal_accepted` then `rule_added`, both by `person`;
- a rule proposal (1) and a category proposal for transaction 4 (2), accepted as `[1, 2]`, give `CategorizeResult(4, 3, 0)`: a run straight after the rule would give `(4, 3, 1)`;
- only a category proposal accepted gives `categorized` None;
- out of date after `rename_category("Dining", "Eating Out")` and after the same rule is added, each refused with R5's message; not out of date after a rule with the same pattern and `starts_with`;
- on the Review page, accepting a rule proposal sets the matching transactions; accepting it together with an out-of-date proposal answers 400 and adds no rule;
- `list_proposals` shows `"rule"` for a rule proposal beside `null` for a category one; `fin review list` shows a rule proposal out of date as `out of date`.

## Rules for this phase

- Accepting goes through `create_rule` and `categorize` only, so the audit trail and every rule of 11a hold. The repositories never run the rules.
- The tool writes nothing but a proposal; the agent cannot accept, decline, or add a rule.
- Keep `repositories/proposals.py` under 400 lines (`tests/unit/test_repositories_split.py`).

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 5 tests; at least N + 5 passed in all;
- `git diff --stat HEAD -- tests` lists only the nine files of the given diff;
- `git grep -n "from finances.categorize" -- src/finances/db src/finances/domain` and `git grep -n "accept_proposal[^s]" -- src/finances/cli src/finances/web` print nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.proposals --cov=finances.db.repositories --cov=finances.categorize.service --cov=finances.views.review --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 19d: the agent proposes rules (YYYY-MM-DD)`.
