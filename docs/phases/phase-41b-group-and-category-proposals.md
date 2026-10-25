# Phase 41b: the agent proposes a group or a category

## Goal

The second part of Phase 41. Today the agent can only put a transaction in a category that exists; when none fits, all it can do is write a note. With the owner's choices (2026-10-25), two new proposal kinds:

- **`propose_group`**: a new group (name; kind spending, transfer, or income; sensitive or not), for when no existing group fits;
- **`propose_new_category`**: a new category (name; tax-relevant or not) in an **existing** group.

Each names an example transaction it is for, and a one-line reason. Like every proposal it changes nothing until a person accepts it, in `fin review` or on the Review page, where it shows beside its example. Accepting a group calls 41a's `create_group`; accepting a category calls `create_category`, then marks it tax-relevant when proposed so. A name a person declined is not proposed again.

Phase 41c adds the chains: a category in a group that is still only proposed, a transaction or rule put in a category that is still only proposed, "waits for #N", parents first, declining a parent declines what waits on it. This phase's migration already adds the column 41c needs (`parent_id`), so 41c has no migration; here it stays empty.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-19e-alias-proposals.md` (the last proposal kind added; this phase follows its shape)
- `src/finances/domain/proposals.py`, `src/finances/db/repositories/proposals.py` (`propose_merchant_alias`, `proposal_out_of_date`, `accept_proposal`, `_now`), `src/finances/db/repositories/categories.py` (`create_group`, `create_category`, `set_tax_relevant`, `_category_row`), `src/finances/views/review.py`, `src/finances/mcp_server/tools.py` (`_proposal_item`, `propose_merchant_alias`), `src/finances/mcp_server/server.py`

## Starting state

N is `4092` when Phase 41a is the last phase built. **Sections: migrations, core, mcp, cli, web** (the Review page shares `views/review.py` with `fin review`). The newest migration is `0021`. `repositories/proposals.py` is 381 lines and the split test allows 400, so the new proposal functions go in a new area module.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0022_new_category_proposals.py` | new: given (R1) |
| `src/finances/db/orm.py` | the six columns on `ProposalRow`; `to_proposal` (R1) |
| `src/finances/domain/proposals.py` | `GROUP`, `NEW_CATEGORY`, `GROUP_KINDS`, the new `Proposal` fields, `proposal_text` (R2) |
| `src/finances/db/repositories/new_categories.py` (new), `__init__.py` | `propose_group`, `propose_new_category` (R3, R4) |
| `src/finances/db/repositories/proposals.py` | out of date and accepting for the two kinds (R5, R6) |
| `src/finances/views/review.py` | `proposed_text`, `accepted_text` (R7) |
| `src/finances/mcp_server/tools.py`, `server.py` | the two tools; `"new"` on every proposal item (R8) |
| `tests/support.py` and ten earlier test files | the given diff (R9) |
| `tests/integration/test_migration_0022.py`, `tests/integration/test_mcp_new_categories.py` | new: given |
| `tests/integration/test_new_category_proposals.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

Every module of `db/repositories/` stays under 400 lines.

## Out of scope

- Everything of 41c: a category in a proposed group, a transaction or rule in a proposed category, `parent_id` set to anything but None, "waits for", ordering, cascading declines.
- Changing an existing category's or group's flags; any new web route or template.

## Dependencies

None new.

## Design

```python
# src/finances/domain/proposals.py
GROUP = "group"
NEW_CATEGORY = "new_category"
KINDS = (CATEGORY, TRANSFER, NOT_TRANSFER, RULE, ALIAS, GROUP, NEW_CATEGORY)
GROUP_KINDS = ("spending", "transfer", "income")

@dataclass(frozen=True)
class Proposal:
    ...                          # the existing fields, unchanged and in order, then:
    group: str | None = None     # a new category's group
    transfer: bool | None = None # a new group's flags
    income: bool | None = None
    sensitive: bool | None = None
    tax: bool | None = None      # a new category's tax flag
    parent_id: int | None = None # 41c

# src/finances/db/repositories/new_categories.py
def propose_group(
    session: Session, example_id: int, name: str, reason: str, *,
    kind: str = "spending", sensitive: bool = False,
) -> Proposal: ...
def propose_new_category(
    session: Session, example_id: int, name: str, group: str, reason: str, *, tax: bool = False,
) -> Proposal: ...
```

The ORM columns are `group_name`, `is_transfer`, `is_income`, `is_sensitive`, `is_tax`, and `parent_id`, as the given migration adds them; `to_proposal` maps them to `group`, `transfer`, `income`, `sensitive`, `tax`, and `parent_id`. `new_categories.py` stamps `created_at` through a `_now()` of its own, as `proposals.py` does (the given test patches both).

A stored proposal of either kind has `target_id` = the example, `value` = the new name as stored (stripped), `other_id`, `pattern`, `match`, `priority`, `source`, and `parent_id` None. A group stores `is_transfer`, `is_income`, `is_sensitive` (from its kind and `sensitive`) and leaves `group_name` and `is_tax` None; a category stores `group_name` (the group's name as the database spells it) and `is_tax`, and leaves the three group flags None.

| `propose_group`: checks, in this order | Refusal (`ValueError`) |
|---|---|
| the reason, whitespace collapsed, is 1 to 200 characters | `a reason must be 1 to 200 characters` |
| the name, stripped, is 1 to 50 characters | `a group name must be 1 to 50 characters` |
| `kind` is one of `GROUP_KINDS` | `a group's kind must be spending, transfer, or income` |
| the example transaction exists | `transaction not found` |
| no category or group has the name (ignoring case) | `a category with this name already exists` |
| no declined group proposal has the name (ignoring case) | `a person declined this proposal already` |
| no open group or new-category proposal has the name (ignoring case) | `this name already has an open proposal` |

`propose_new_category` makes the same checks with these differences: the name's message is `a category name must be 1 to 50 characters`; there is no kind; after the example comes the group, which must be an existing group (ignoring case; a category or nothing: `group not found`); and the declined check looks at declined new-category proposals with the name in that group.

| Kind | Out of date when | Accepting |
|---|---|---|
| `GROUP` | a category or group now has the name | `create_group(session, value, transfer=, income=, sensitive=)` |
| `NEW_CATEGORY` | a category or group now has the name, or the group is no longer a group | `create_category(session, value, group)`, then `set_tax_relevant(session, value, True)` when `tax` |

Accepting an out of date one is refused with `proposal N is out of date: the categories changed since`. `accept_proposals` runs no categorize for these kinds. History records `proposal_accepted` or `proposal_declined` as for every kind, and accepting also records the `category_added` (and, with tax, `category_tax_set`) that `create_group`, `create_category`, and `set_tax_relevant` already record.

| Text | Group | Category |
|---|---|---|
| `proposal_text` (History) | `group: Pets`, or `group: Side Gigs (income, sensitive)` | `category: Pet Supplies in Home`, with ` (tax)` after when tax-relevant |
| `proposed_text` (`fin review list`, Review page) | `a new group: Pets`, or `a new group: Side Gigs (income, sensitive)` | `a new category: Pet Supplies in Home`, with `, tax-relevant` after when so |
| `accepted_text` | `Accepted proposal 5: the group Pets.` | `Accepted proposal 6: the category Pet Supplies in Home.` |

The words in brackets are `transfer`, `income`, `sensitive` that apply, in that order, joined by `, `; none: no brackets.

**MCP.** Two tools, registered after `propose_merchant_alias` with the same annotations as the other writers:

```python
def propose_group(
    name: str, example_id: int, reason: str,
    kind: Literal["spending", "transfer", "income"] = "spending", sensitive: bool = False,
) -> dict[str, Any]: ...
def propose_new_category(
    name: str, group: str, example_id: int, reason: str, tax: bool = False,
) -> dict[str, Any]: ...
```

Each returns `{"proposal": <item>}` like the other `propose_*` tools. Every proposal item, of every kind, gains `"new"`: None, except for the two new kinds, where it is `{"name", "group", "kind", "sensitive", "tax"}`: for a group `group` and `tax` are None and `kind` is the kind word; for a category `kind` and `sensitive` are None. The descriptions, exactly:

```python
PROPOSE_GROUP_DESCRIPTION = (
    "Propose a new group of categories (a name; kind: spending, transfer, or income; sensitive "
    "or not), with an example transaction it is for and a one-line reason a person will read. "
    "Use it only when no existing group fits. It changes nothing until a person accepts it "
    "with fin review. Refused when a category or group has the name, a person declined it, or "
    "another proposal for that name is open. No amounts."
)
PROPOSE_NEW_CATEGORY_DESCRIPTION = (
    "Propose a new category (a name) in an existing group, tax-relevant or not, with an "
    "example transaction it is for and a one-line reason a person will read. It changes "
    "nothing until a person accepts it with fin review; then propose_category can put "
    "transactions in it. Refused when the group does not exist, a category or group has the "
    "name, a person declined it, or another proposal for that name is open. No amounts."
)
```

## Requirements

- **R1.** Apply the given migration exactly; the six ORM columns and `to_proposal` as designed.
- **R2.** The domain names and `Proposal` fields as designed; `proposal_text` for the two kinds.
- **R3.** `propose_group` as designed, its checks in the table's order, stored as designed.
- **R4.** `propose_new_category` as designed.
- **R5.** Out of date for the two kinds as designed, through `proposal_out_of_date`.
- **R6.** Accepting the two kinds as designed, through `accept_proposal`; `accept_proposals` unchanged otherwise.
- **R7.** The three texts as designed.
- **R8.** The two MCP tools, their descriptions, and `"new"` on every item as designed.
- **R9.** Apply the given diff to `tests/support.py` and the ten earlier test files. No other earlier test changes.

## Given migration

`src/finances/db/migrations/versions/0022_new_category_proposals.py` (do not change). It was run up, down, and up again on a database holding a proposal, which it keeps.

```python
"""Add to proposals what a proposed group or category needs, and the proposal one waits for."""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

ADDED = ("group_name", "is_transfer", "is_income", "is_sensitive", "is_tax", "parent_id")


def upgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.add_column(sa.Column("group_name", sa.String(50), nullable=True))
        batch.add_column(sa.Column("is_transfer", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("is_income", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("is_sensitive", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("is_tax", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        for name in reversed(ADDED):
            batch.drop_column(name)
```

## Given diff to earlier tests

The tool lists, the description table, the repository areas, the proposal kinds, and `"new": None` in every whole proposal item an earlier test pins. With `"new"` added to the item, each of these passes except the two that need the new tools registered.

```text
diff --git a/tests/integration/test_mcp_accounts.py b/tests/integration/test_mcp_accounts.py
index 0d381c2..98dc415 100644
--- a/tests/integration/test_mcp_accounts.py
+++ b/tests/integration/test_mcp_accounts.py
@@ -33,6 +33,8 @@ NO_AMOUNTS = (
     "propose_transfer",
     "propose_not_transfer",
     "propose_rule",
+    "propose_group",
+    "propose_new_category",
 )
 READ_ONLY = {
     "read_only_hint": True,
diff --git a/tests/integration/test_mcp_alias_proposals.py b/tests/integration/test_mcp_alias_proposals.py
index 129d4d0..c406130 100644
--- a/tests/integration/test_mcp_alias_proposals.py
+++ b/tests/integration/test_mcp_alias_proposals.py
@@ -66,6 +66,7 @@ def test_the_agent_proposes_an_alias(card: Settings) -> None:
             "category": None,
             "rule": None,
             "alias": {"source": "ACME CAFE", "target": "ACME COFFEE"},
+            "new": None,
             "reason": "the same shop",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_more.py b/tests/integration/test_mcp_more.py
index 3e0a9c1..c53936a 100644
--- a/tests/integration/test_mcp_more.py
+++ b/tests/integration/test_mcp_more.py
@@ -35,7 +35,9 @@ from finances.mcp_server.server import (
     LOG_ADVICE_DESCRIPTION,
     MONTH_OVER_MONTH_DESCRIPTION,
     PROPOSE_CATEGORY_DESCRIPTION,
+    PROPOSE_GROUP_DESCRIPTION,
     PROPOSE_MERCHANT_ALIAS_DESCRIPTION,
+    PROPOSE_NEW_CATEGORY_DESCRIPTION,
     PROPOSE_NOT_TRANSFER_DESCRIPTION,
     PROPOSE_RULE_DESCRIPTION,
     PROPOSE_TRANSFER_DESCRIPTION,
@@ -163,6 +165,8 @@ def test_each_tool_description_matches_the_table(tmp_settings: Settings) -> None
         "propose_transfer": PROPOSE_TRANSFER_DESCRIPTION,
         "propose_not_transfer": PROPOSE_NOT_TRANSFER_DESCRIPTION,
         "propose_rule": PROPOSE_RULE_DESCRIPTION,
+        "propose_group": PROPOSE_GROUP_DESCRIPTION,
+        "propose_new_category": PROPOSE_NEW_CATEGORY_DESCRIPTION,
         "list_proposals": LIST_PROPOSALS_DESCRIPTION,
         "log_advice": LOG_ADVICE_DESCRIPTION,
         "list_advice": LIST_ADVICE_DESCRIPTION,
diff --git a/tests/integration/test_mcp_proposals.py b/tests/integration/test_mcp_proposals.py
index 7053c85..fd95d4f 100644
--- a/tests/integration/test_mcp_proposals.py
+++ b/tests/integration/test_mcp_proposals.py
@@ -32,7 +32,9 @@ FROM_REPOSITORIES = {
     "log_advice",
     "proposal_out_of_date",
     "propose_category",
+    "propose_group",
     "propose_merchant_alias",
+    "propose_new_category",
     "propose_not_transfer",
     "propose_rule",
     "propose_transfer",
@@ -106,6 +108,7 @@ def test_a_proposal_and_its_listing(one: Settings) -> None:
         "category": "Coffee & Dessert",
         "rule": None,
         "alias": None,
+        "new": None,
         "reason": "a cafe",
         "status": "open",
         "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_rule_proposals.py b/tests/integration/test_mcp_rule_proposals.py
index a7183ce..b7c5b37 100644
--- a/tests/integration/test_mcp_rule_proposals.py
+++ b/tests/integration/test_mcp_rule_proposals.py
@@ -68,6 +68,7 @@ def test_the_agent_proposes_a_rule(card: Settings) -> None:
             "category": "Dining",
             "rule": {"match": "equals", "pattern": "ACME COFFEE", "priority": 5},
             "alias": None,
+            "new": None,
             "reason": "a cafe",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_transfer_proposals.py b/tests/integration/test_mcp_transfer_proposals.py
index 50febe5..c3c5cc8 100644
--- a/tests/integration/test_mcp_transfer_proposals.py
+++ b/tests/integration/test_mcp_transfer_proposals.py
@@ -60,6 +60,7 @@ def test_the_agent_proposes_a_transfer(moved: Settings) -> None:
             "category": None,
             "rule": None,
             "alias": None,
+            "new": None,
             "reason": "same day, same amount",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_transfer_proposals_more.py b/tests/integration/test_transfer_proposals_more.py
index 293e204..1ff1d26 100644
--- a/tests/integration/test_transfer_proposals_more.py
+++ b/tests/integration/test_transfer_proposals_more.py
@@ -37,6 +37,7 @@ PAIR = {
     "category": None,
     "rule": None,
     "alias": None,
+    "new": None,
     "reason": "interest, not a transfer",
     "status": "open",
     "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/support.py b/tests/support.py
index ab1574b..3faac29 100644
--- a/tests/support.py
+++ b/tests/support.py
@@ -173,7 +173,9 @@ MCP_TOOLS = [
     "log_advice",
     "month_over_month",
     "propose_category",
+    "propose_group",
     "propose_merchant_alias",
+    "propose_new_category",
     "propose_not_transfer",
     "propose_rule",
     "propose_transfer",
@@ -184,5 +186,7 @@ MCP_WRITERS = (
     "propose_not_transfer",
     "propose_rule",
     "propose_merchant_alias",
+    "propose_group",
+    "propose_new_category",
     "log_advice",
 )
diff --git a/tests/unit/test_proposal_rules.py b/tests/unit/test_proposal_rules.py
index 40f32f6..a0cc9a1 100644
--- a/tests/unit/test_proposal_rules.py
+++ b/tests/unit/test_proposal_rules.py
@@ -19,7 +19,7 @@ from finances.domain.text import ADVICE_TEXT_LIMIT, PROPOSAL_TEXT_LIMIT
 def test_the_lists_and_limits() -> None:
     assert (CATEGORY, KINDS) == (
         "category",
-        ("category", "transfer", "not_transfer", "rule", "alias"),
+        ("category", "transfer", "not_transfer", "rule", "alias", "group", "new_category"),
     )
     assert (OPEN, ACCEPTED, DECLINED, STATUSES) == (
         "open",
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index c4f84e2..c4b19b7 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -86,6 +86,10 @@ HOMES = {
         "record_sync_failure",
         "set_feed_account_ignored",
     ],
+    "new_categories": [
+        "propose_group",
+        "propose_new_category",
+    ],
     "proposals": [
         "accept_proposal",
         "count_open_proposals",
@@ -178,7 +182,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 126
+    assert len(expected) == 128
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
diff --git a/tests/unit/test_rule_proposal_rules.py b/tests/unit/test_rule_proposal_rules.py
index ca6f57f..110135f 100644
--- a/tests/unit/test_rule_proposal_rules.py
+++ b/tests/unit/test_rule_proposal_rules.py
@@ -17,7 +17,15 @@ MADE = datetime(2026, 5, 25, tzinfo=UTC)
 
 def test_the_kinds() -> None:
     assert RULE == "rule"
-    assert KINDS == ("category", "transfer", "not_transfer", "rule", "alias")
+    assert KINDS == (
+        "category",
+        "transfer",
+        "not_transfer",
+        "rule",
+        "alias",
+        "group",
+        "new_category",
+    )
 
 
 @pytest.mark.parametrize(
```

## Given tests

15 tests in two files. Do not change them.

`tests/integration/test_migration_0022.py`

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import ProposalRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
ADDED = [
    ("group_name", "VARCHAR(50)", True),
    ("is_transfer", "BOOLEAN", True),
    ("is_income", "BOOLEAN", True),
    ("is_sensitive", "BOOLEAN", True),
    ("is_tax", "BOOLEAN", True),
    ("parent_id", "INTEGER", True),
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


def reasons(url: str) -> list[str]:
    engine = get_engine(url)
    with engine.connect() as connection:
        found = list(connection.execute(text("SELECT reason FROM proposals ORDER BY id")).scalars())
    engine.dispose()
    return found


def test_0022_follows_0021() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0022")
    assert script.down_revision == "0021"


def test_the_columns_come_and_go_and_the_rows_stay(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = make_config(url)
    command.upgrade(config, "0021")
    engine = get_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO proposals (kind, target_id, value, reason, status, created_at)"
                " VALUES ('category', 1, 'Dining', 'a cafe', 'open', '2026-05-25 12:00:00.000000')"
            )
        )
    engine.dispose()
    command.upgrade(config, "0022")
    found = columns(url)
    assert found[-6:] == ADDED
    orm = [(c.name, str(c.type), c.nullable) for c in ProposalRow.__table__.columns]
    assert orm[: len(found)] == found
    assert reasons(url) == ["a cafe"]
    command.downgrade(config, "0021")
    assert columns(url)[-1] == ("source", "VARCHAR(100)", True)
    assert reasons(url) == ["a cafe"]
    command.upgrade(config, "0022")
    assert columns(url)[-6:] == ADDED
```

`tests/integration/test_mcp_new_categories.py`

```python
from datetime import UTC, date, datetime

import anyio
import pytest
from mcp.client import Client

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, get_category_by_name
from finances.mcp_server.server import build_server
from tests.support import failed_cleanly, run, table_rows

GROUP = {"name": " Pets ", "example_id": 1, "reason": "pet costs"}
CATEGORY = {"name": "Pet Supplies", "group": "home", "example_id": 1, "reason": "a pet shop"}
TAKEN = "a category with this name already exists"


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def error(name: str, arguments: dict) -> list[str]:
    return [item.text for item in call(name, arguments).content]


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """One card purchase with no category: transaction 1, FOOBAR PET SUPPLY, -$25.99."""
    for module in ("proposals", "new_categories"):
        monkeypatch.setattr(
            f"finances.db.repositories.{module}._now",
            lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
        )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, 1),
                amount_cents=-2599,
                description="FOOBAR PET SUPPLY",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
    engine.dispose()
    return tmp_settings


def item(kind: str, new: dict, reason: str) -> dict:
    return {
        "proposal": {
            "id": 1,
            "kind": kind,
            "transaction_id": 1,
            "in_id": None,
            "category": None,
            "rule": None,
            "alias": None,
            "new": new,
            "reason": reason,
            "status": "open",
            "created_at": "2026-05-25T12:00:00+00:00",
            "decided_at": None,
            "out_of_date": False,
        }
    }


def test_the_agent_proposes_a_group(card: Settings) -> None:
    made = call("propose_group", {**GROUP, "kind": "income", "sensitive": True})
    assert made.structured_content == item(
        "group",
        {"name": "Pets", "group": None, "kind": "income", "sensitive": True, "tax": None},
        "pet costs",
    )


def test_the_agent_proposes_a_category_in_a_group(card: Settings) -> None:
    made = call("propose_new_category", {**CATEGORY, "tax": True})
    assert made.structured_content == item(
        "new_category",
        {"name": "Pet Supplies", "group": "Home", "kind": None, "sensitive": None, "tax": True},
        "a pet shop",
    )


@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("propose_group", {**GROUP, "name": "food"}, TAKEN),
        ("propose_group", {**GROUP, "name": "Groceries"}, TAKEN),
        ("propose_group", {**GROUP, "example_id": 9}, "transaction not found"),
        ("propose_new_category", {**CATEGORY, "group": "Dining"}, "group not found"),
        ("propose_new_category", {**CATEGORY, "name": "Dining"}, TAKEN),
        (
            "propose_new_category",
            {**CATEGORY, "reason": " "},
            "a reason must be 1 to 200 characters",
        ),
    ],
)
def test_a_refused_proposal(card: Settings, tool: str, arguments: dict, message: str) -> None:
    assert error(tool, arguments) == [f"Error executing tool {tool}: {message}"]


def test_one_open_proposal_for_a_name(card: Settings) -> None:
    call("propose_group", GROUP)
    again = "this name already has an open proposal"
    assert error("propose_group", GROUP) == [f"Error executing tool propose_group: {again}"]
    assert error("propose_new_category", {**CATEGORY, "name": "pets"}) == [
        f"Error executing tool propose_new_category: {again}"
    ]


def test_a_person_accepts_a_group_in_the_terminal(card: Settings) -> None:
    call("propose_group", {**GROUP, "sensitive": True})
    rows = table_rows(run("review", "list").stdout)
    assert rows[1] == [
        "1",
        "2026-05-01",
        "Test Card",
        "FOOBAR PET SUPPLY",
        "-$25.99",
        "",
        "a new group: Pets (sensitive)",
        "pet costs",
        "open",
    ]
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (0, "Accepted proposal 1: the group Pets.\n")
    assert ["Pets", "", "sensitive"] in table_rows(run("categories", "list").stdout)


def test_a_person_accepts_a_category_in_the_terminal(card: Settings) -> None:
    call("propose_new_category", {**CATEGORY, "tax": True})
    rows = table_rows(run("review", "list").stdout)
    assert rows[1][6] == "a new category: Pet Supplies in Home, tax-relevant"
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: the category Pet Supplies in Home.\n",
    )
    engine = get_engine()
    with session_scope(engine) as session:
        found = get_category_by_name(session, "Pet Supplies")
        group = get_category_by_name(session, "Home")
    engine.dispose()
    assert found is not None and group is not None
    assert (found.group_id, found.is_tax) == (group.id, True)


def test_a_group_whose_name_was_taken_since_is_out_of_date(card: Settings) -> None:
    call("propose_group", GROUP)
    run("categories", "add-group", "--name", "Pets")
    assert table_rows(run("review", "list").stdout)[1][8] == "out of date"
    assert failed_cleanly(
        run("review", "accept", "--id", "1"),
        "proposal 1 is out of date: the categories changed since",
    )


def test_a_declined_name_is_not_proposed_again(card: Settings) -> None:
    call("propose_group", GROUP)
    assert run("review", "decline", "--id", "1").stdout == "Declined proposal 1.\n"
    assert error("propose_group", GROUP) == [
        "Error executing tool propose_group: a person declined this proposal already"
    ]
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_new_category_proposals.py` (section core):

- `propose_group` with `kind="savings"` is refused with the kind's message, and with a 51-character name with the name's message before the kind is checked;
- a stored group of kind `transfer` has `transfer` True, `income` False, `group` and `tax` None; a stored category has the group spelled as the database spells it (`home` stored as `Home`);
- a declined group named `Pets` does not stop a category named `Pets` being proposed (the declined check is per kind), but an open one does;
- a new-category proposal whose group is deleted since is out of date, and accepting it is refused;
- accepting a tax-relevant category records `category_added` then `category_tax_set`, and one that is not records only `category_added`;
- `proposed_text` and `accepted_text` for a transfer group (`a new group: Moves (transfer)`), for an income group that is sensitive (`a new group: Side Gigs (income, sensitive)`, the words in that order), and for a category that is not tax-relevant; `proposal_text` for the same three;
- the Review page lists a group proposal with `a new group: Pets` in its row, and accepting it there (`POST /review`) creates the group.

## Rules for this phase

- The tools only store proposals: neither creates a group or a category.
- Earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the check: `.venv/bin/python scripts/check.py --first migrations,core,mcp,cli,web`;
- the given test files above, 15 tests; at least N + 15 passed in all;
- `git diff --stat HEAD -- tests` lists only `tests/support.py` and the ten files of the given diff;
- the coverage command: `.venv/bin/python -m coverage report --include="*/finances/domain/proposals.py,*/finances/db/repositories/proposals.py,*/finances/db/repositories/new_categories.py,*/finances/db/orm.py,*/finances/views/review.py,*/finances/mcp_server/tools.py,*/finances/mcp_server/server.py" --fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 41b: the agent proposes a group or a category (YYYY-MM-DD)`.
