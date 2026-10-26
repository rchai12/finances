# Phase 44a: proposing over a person's choice, and changing a rule

## Goal

The first part of Phase 44 (the agent proposes changes to what already exists). With the owner's choices (2026-10-26):

- **A person's choice can be proposed over.** `propose_category` no longer refuses a transaction whose category a person set (by hand, or by accepting an earlier proposal). A split transaction and one in a transfer are still refused, as today. Proposing the category a transaction already has is refused.
- **A rule can be changed.** A new `propose_rule_change` proposes editing an existing rule (any of pattern, match, priority, category) or deleting it. Accepting it goes through `edit_rule` or `delete_rule`, then the rules run again. The category must exist (no waiting for a proposed one).
- **A proposal remembers what it changes.** Each new category proposal stores the transaction's category when proposed, and each rule change stores the rule as it was (`before`). A proposal is out of date only when a **person** changed that since: so the agent's proposal over a person's choice is not out of date from the start, and a person's own later edit is never overwritten.

Phase 44b adds renaming and deleting categories and groups.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/db/repositories/proposals.py` (`propose_category`, `decided_by_a_person`, `proposal_out_of_date`, `accept_proposal`), `src/finances/db/repositories/new_categories.py` (how 41b put a new kind's out of date and accepting in their own module), `src/finances/db/repositories/categories.py` (`edit_rule`, `delete_rule`, `_rule_line`, `_leaf_category`), `src/finances/categorize/service.py` (`accept_proposals`), `src/finances/analysis/review.py` (`review_items`), `src/finances/views/review.py`, `src/finances/mcp_server/tools.py` (`_proposal_item`, `propose_rule`), `src/finances/mcp_server/server.py`

## Starting state

N is `4163` when Phase 43 is the last phase built. **Sections: migrations, core, mcp, cli, web.** The newest migration is `0023`. `repositories/proposals.py` is at the 400 lines the split test allows: it must not grow, so the rule-change kinds' checks, out of date, and accepting live in the new `repositories/rule_changes.py` (as 41b's did in `new_categories.py`), and the edits to `propose_category` and `proposal_out_of_date` must fit (move a private helper out if needed).

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0024_proposal_before.py` | new: given (R1) |
| `src/finances/db/orm.py`, `src/finances/domain/proposals.py` | `before` on `ProposalRow` and `Proposal`; `RULE_EDIT`, `RULE_DELETE`; `proposal_text` (R1, R2) |
| `src/finances/db/repositories/proposals.py` | `propose_category` and its out of date (R3, R4); dispatch to the new module (R6) |
| `src/finances/db/repositories/rule_changes.py` (new), `__init__.py` | `propose_rule_change`, its out of date and accepting (R5, R6) |
| `src/finances/categorize/service.py` | `accept_proposals` runs the rules after a rule change (R6) |
| `src/finances/analysis/review.py`, `src/finances/views/review.py` | the rows and texts of a rule change (R7) |
| `src/finances/mcp_server/tools.py`, `server.py` | the tool; `"rule_change"` on every item; two descriptions (R8) |
| `tests/support.py` and twelve earlier test files | the given diff (R9) |
| `tests/integration/test_migration_0024.py`, `tests/integration/test_mcp_rule_changes.py` | new: given |
| `tests/integration/test_rule_changes_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Renaming or deleting categories and groups (44b); a rule change into a proposed category; a chain through a rule change.
- A transfer or a split given one category by a proposal.

## Dependencies

None new.

## Design

```python
# src/finances/domain/proposals.py
RULE_EDIT = "rule_edit"
RULE_DELETE = "rule_delete"
KINDS = (CATEGORY, TRANSFER, NOT_TRANSFER, RULE, ALIAS, GROUP, NEW_CATEGORY, RULE_EDIT, RULE_DELETE)
# Proposal gains, last:  before: str | None = None

# src/finances/db/repositories/rule_changes.py
def propose_rule_change(
    session: Session, rule_id: int, reason: str, *, delete: bool = False,
    pattern: str | None = None, match: str | None = None, priority: int | None = None,
    category: str | None = None,
) -> Proposal: ...
```

**`propose_category`.** The refusal for a transaction a person decided now applies only to a split transaction or one in a transfer pair, with today's message (`a person has already decided this transaction`). After the category is found (as today), a transaction whose current category is that one is refused: `the transaction already has this category`. The proposal stores `before` = the name of the transaction's current category, or None when it has none. Everything else is unchanged.

**Out of date, `CATEGORY`.** Out of date when the transaction is gone, split, or in a transfer pair, or when its category is now set by a person and its name differs from `before` (None counts as no category). This is today's rule exactly for proposals made before this phase, whose `before` is None.

**`propose_rule_change`.** Checks, in this order (all `ValueError`):

| Check | Refusal |
|---|---|
| the reason, whitespace collapsed, is 1 to 200 characters | `a reason must be 1 to 200 characters` |
| the rule exists | `rule not found` |
| with `delete`, no field is given | `a deletion changes no fields` |
| without `delete`, at least one field is given | `name at least one field to change` |
| the fields, as `edit_rule` checks them (pattern normalized and its length, match, the category by `_leaf_category`), in `edit_rule`'s order | `edit_rule`'s messages |
| the rule as changed differs from the rule now | `the rule already is like this` |
| no other rule has the new pattern and match | `a rule with this pattern and match already exists` |
| no declined proposal of the same kind for this rule with the same values | `a person declined this proposal already` |
| no open edit or delete proposal for this rule | `this rule already has an open proposal` |

Stored: kind `RULE_EDIT` or `RULE_DELETE`; `target_id` = the rule's id; `value` = the category name the rule would have (for a delete, its current one); `pattern`, `match`, `priority` = the values it would have (for a delete, its current ones); `before` = `_rule_line` of the rule now; every other column None. `created_at` comes from a `_now()` of `rule_changes.py`'s own (the given test patches it).

**Out of date and accepting a rule change.** Out of date when the rule is gone or its `_rule_line` differs from `before`; accepting one is then refused with the rule message of today, `proposal N is out of date: the rules or categories changed since`. Accepting a `RULE_EDIT` calls `edit_rule(session, target_id, pattern=, match=, priority=, category=value)`; a `RULE_DELETE` calls `delete_rule(session, target_id)`. `accept_proposals` runs categorize after either, as after a `RULE` or `ALIAS`.

| Text | `RULE_EDIT` (rule 1 to `contains "ACME" -> Coffee & Dessert (priority 5)`) | `RULE_DELETE` |
|---|---|---|
| `proposal_text` (History) | `rule 1: contains "ACME" -> Coffee & Dessert (priority 5)` | `delete rule 1` |
| review: Now / Proposed | `before` / `rule 1: contains "ACME" -> Coffee & Dessert (priority 5)` | `before` / `delete rule 1` |
| `accepted_text` | `Accepted proposal N: rule 1 is now contains "ACME" -> Coffee & Dessert (priority 5).` | `Accepted proposal N: rule 1 deleted.` |

A rule change has no transaction: `review_items` gives it `transaction` None and `account` None, and `current` = `before`, so its date, account, description, and amount cells are empty.

**MCP.** `propose_rule_change` is registered after `propose_new_category` with the writers' annotations:

```python
def propose_rule_change(
    rule_id: int, reason: str, delete: bool = False, pattern: str | None = None,
    match: Literal["contains", "starts_with", "equals"] | None = None,
    priority: Annotated[int | None, Field(ge=-1000, le=1000)] = None, category: str | None = None,
) -> dict[str, Any]: ...
```

Every proposal item gains `"rule_change"`: None, except for the two new kinds: `{"rule_id": <target_id>, "before": <before>, "delete": <bool>}`. For them, `"transaction_id"` is None, `"category"` is `value`, and `"rule"` is `{"match", "pattern", "priority"}`. The descriptions, exactly:

```python
PROPOSE_CATEGORY_DESCRIPTION = (
    "Propose a category for a transaction, with a one-line reason a person will read. The "
    "transaction may have a category already, set by a rule or by a person; the category may "
    "be one still proposed with propose_new_category, and this proposal then waits for that "
    "one. It changes nothing: a person accepts or declines it with fin review. Refused for a "
    "split transaction or one in a transfer, when it already has that category, when a person "
    "declined this same proposal, or when another proposal for it is open."
)
PROPOSE_RULE_CHANGE_DESCRIPTION = (
    "Propose changing an existing rule (rule_id from list_rules): any of its pattern, match, "
    "priority, and category, or delete=true to delete it, with a one-line reason a person will "
    "read. The category must exist. It changes nothing until a person accepts it; then the "
    "rules run over every transaction. Refused when the rule would not change, another rule "
    "has the new pattern and match, a person declined it, or another proposal for that rule "
    "is open. No amounts."
)
```

## Requirements

- **R1.** Apply the given migration exactly; `before` on `ProposalRow` and `Proposal`, mapped by `to_proposal`.
- **R2.** `RULE_EDIT`, `RULE_DELETE`, `KINDS`, and `proposal_text` as designed.
- **R3.** `propose_category` as designed.
- **R4.** Out of date for `CATEGORY` as designed.
- **R5.** `propose_rule_change` as designed, exported from `finances.db.repositories`.
- **R6.** Out of date and accepting for the two new kinds as designed; `accept_proposals` runs categorize after them.
- **R7.** The review rows and the texts as designed.
- **R8.** The MCP tool, `"rule_change"` on every item, and the two descriptions as designed.
- **R9.** Apply the given diff to `tests/support.py` and the twelve earlier test files. No other earlier test changes.

## Given migration

`src/finances/db/migrations/versions/0024_proposal_before.py` (do not change). It was run up, down, and up again on a database holding a proposal, which it keeps.

```python
"""Add proposals.before: what a proposal changes, as it was when the agent proposed it."""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.add_column(sa.Column("before", sa.String(200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.drop_column("before")
```

## Given diff to earlier tests

The tool lists, the description table, the repository areas, the kinds, `"rule_change": None` beside `"waits_for"` in every whole proposal item, and the one refusal case of `test_proposals.py` that no longer holds (a transaction a person set by hand). With `"rule_change"` added to the item, all of these pass except the two that need the new tool registered. A spike that stored `before` in `propose_category` broke no earlier test.

```text
diff --git a/tests/integration/test_mcp_accounts.py b/tests/integration/test_mcp_accounts.py
index 98dc415..0a6356c 100644
--- a/tests/integration/test_mcp_accounts.py
+++ b/tests/integration/test_mcp_accounts.py
@@ -35,6 +35,7 @@ NO_AMOUNTS = (
     "propose_rule",
     "propose_group",
     "propose_new_category",
+    "propose_rule_change",
 )
 READ_ONLY = {
     "read_only_hint": True,
diff --git a/tests/integration/test_mcp_alias_proposals.py b/tests/integration/test_mcp_alias_proposals.py
index 0aa7107..596fad4 100644
--- a/tests/integration/test_mcp_alias_proposals.py
+++ b/tests/integration/test_mcp_alias_proposals.py
@@ -68,6 +68,7 @@ def test_the_agent_proposes_an_alias(card: Settings) -> None:
             "alias": {"source": "ACME CAFE", "target": "ACME COFFEE"},
             "new": None,
             "waits_for": None,
+            "rule_change": None,
             "reason": "the same shop",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_more.py b/tests/integration/test_mcp_more.py
index c53936a..050592a 100644
--- a/tests/integration/test_mcp_more.py
+++ b/tests/integration/test_mcp_more.py
@@ -39,6 +39,7 @@ from finances.mcp_server.server import (
     PROPOSE_MERCHANT_ALIAS_DESCRIPTION,
     PROPOSE_NEW_CATEGORY_DESCRIPTION,
     PROPOSE_NOT_TRANSFER_DESCRIPTION,
+    PROPOSE_RULE_CHANGE_DESCRIPTION,
     PROPOSE_RULE_DESCRIPTION,
     PROPOSE_TRANSFER_DESCRIPTION,
     build_server,
@@ -167,6 +168,7 @@ def test_each_tool_description_matches_the_table(tmp_settings: Settings) -> None
         "propose_rule": PROPOSE_RULE_DESCRIPTION,
         "propose_group": PROPOSE_GROUP_DESCRIPTION,
         "propose_new_category": PROPOSE_NEW_CATEGORY_DESCRIPTION,
+        "propose_rule_change": PROPOSE_RULE_CHANGE_DESCRIPTION,
         "list_proposals": LIST_PROPOSALS_DESCRIPTION,
         "log_advice": LOG_ADVICE_DESCRIPTION,
         "list_advice": LIST_ADVICE_DESCRIPTION,
diff --git a/tests/integration/test_mcp_new_categories.py b/tests/integration/test_mcp_new_categories.py
index 24538dc..f83ce92 100644
--- a/tests/integration/test_mcp_new_categories.py
+++ b/tests/integration/test_mcp_new_categories.py
@@ -67,6 +67,7 @@ def item(kind: str, new: dict, reason: str) -> dict:
             "alias": None,
             "new": new,
             "waits_for": None,
+            "rule_change": None,
             "reason": reason,
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_proposals.py b/tests/integration/test_mcp_proposals.py
index 29d715e..6a80f42 100644
--- a/tests/integration/test_mcp_proposals.py
+++ b/tests/integration/test_mcp_proposals.py
@@ -37,6 +37,7 @@ FROM_REPOSITORIES = {
     "propose_new_category",
     "propose_not_transfer",
     "propose_rule",
+    "propose_rule_change",
     "propose_transfer",
 }
 
@@ -110,6 +111,7 @@ def test_a_proposal_and_its_listing(one: Settings) -> None:
         "alias": None,
         "new": None,
         "waits_for": None,
+        "rule_change": None,
         "reason": "a cafe",
         "status": "open",
         "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_rule_proposals.py b/tests/integration/test_mcp_rule_proposals.py
index afed7ed..6e259ab 100644
--- a/tests/integration/test_mcp_rule_proposals.py
+++ b/tests/integration/test_mcp_rule_proposals.py
@@ -70,6 +70,7 @@ def test_the_agent_proposes_a_rule(card: Settings) -> None:
             "alias": None,
             "new": None,
             "waits_for": None,
+            "rule_change": None,
             "reason": "a cafe",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_transfer_proposals.py b/tests/integration/test_mcp_transfer_proposals.py
index f459eca..0d6d77b 100644
--- a/tests/integration/test_mcp_transfer_proposals.py
+++ b/tests/integration/test_mcp_transfer_proposals.py
@@ -62,6 +62,7 @@ def test_the_agent_proposes_a_transfer(moved: Settings) -> None:
             "alias": None,
             "new": None,
             "waits_for": None,
+            "rule_change": None,
             "reason": "same day, same amount",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_proposals.py b/tests/integration/test_proposals.py
index 6579f42..e8c3cb6 100644
--- a/tests/integration/test_proposals.py
+++ b/tests/integration/test_proposals.py
@@ -86,7 +86,6 @@ def test_a_rules_category_can_be_proposed_over(session: Session) -> None:
         (99, "Dining", "why", "transaction not found"),
         (1, "Nope", "why", "category not found"),
         (1, "Food", "why", "rules and transactions take a category, not a group"),
-        (3, "Dining", "why", "a person has already decided this transaction"),
         (4, "Dining", "why", "a person has already decided this transaction"),
     ],
 )
diff --git a/tests/integration/test_transfer_proposals_more.py b/tests/integration/test_transfer_proposals_more.py
index 4844ebd..7f2d451 100644
--- a/tests/integration/test_transfer_proposals_more.py
+++ b/tests/integration/test_transfer_proposals_more.py
@@ -39,6 +39,7 @@ PAIR = {
     "alias": None,
     "new": None,
     "waits_for": None,
+    "rule_change": None,
     "reason": "interest, not a transfer",
     "status": "open",
     "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/support.py b/tests/support.py
index 3faac29..b46f8d2 100644
--- a/tests/support.py
+++ b/tests/support.py
@@ -178,6 +178,7 @@ MCP_TOOLS = [
     "propose_new_category",
     "propose_not_transfer",
     "propose_rule",
+    "propose_rule_change",
     "propose_transfer",
 ]
 MCP_WRITERS = (
@@ -188,5 +189,6 @@ MCP_WRITERS = (
     "propose_merchant_alias",
     "propose_group",
     "propose_new_category",
+    "propose_rule_change",
     "log_advice",
 )
diff --git a/tests/unit/test_proposal_rules.py b/tests/unit/test_proposal_rules.py
index a0cc9a1..03371f4 100644
--- a/tests/unit/test_proposal_rules.py
+++ b/tests/unit/test_proposal_rules.py
@@ -19,7 +19,17 @@ from finances.domain.text import ADVICE_TEXT_LIMIT, PROPOSAL_TEXT_LIMIT
 def test_the_lists_and_limits() -> None:
     assert (CATEGORY, KINDS) == (
         "category",
-        ("category", "transfer", "not_transfer", "rule", "alias", "group", "new_category"),
+        (
+            "category",
+            "transfer",
+            "not_transfer",
+            "rule",
+            "alias",
+            "group",
+            "new_category",
+            "rule_edit",
+            "rule_delete",
+        ),
     )
     assert (OPEN, ACCEPTED, DECLINED, STATUSES) == (
         "open",
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index 476a2c7..6f24eea 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -155,6 +155,9 @@ HOMES = {
         "share_transaction",
         "unshare_transaction",
     ],
+    "rule_changes": [
+        "propose_rule_change",
+    ],
     "splits": [
         "clear_split",
         "set_split",
@@ -191,7 +194,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 133
+    assert len(expected) == 134
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
diff --git a/tests/unit/test_rule_proposal_rules.py b/tests/unit/test_rule_proposal_rules.py
index 110135f..a9f6b75 100644
--- a/tests/unit/test_rule_proposal_rules.py
+++ b/tests/unit/test_rule_proposal_rules.py
@@ -25,6 +25,8 @@ def test_the_kinds() -> None:
         "alias",
         "group",
         "new_category",
+        "rule_edit",
+        "rule_delete",
     )
 
 
```

## Given tests

17 tests in two files. Do not change them.

`tests/integration/test_migration_0024.py`

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
ADDED = ("before", "VARCHAR(200)", True)


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


def test_0024_follows_0023() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0024")
    assert script.down_revision == "0023"


def test_the_columns_come_and_go_and_the_rows_stay(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = make_config(url)
    command.upgrade(config, "0023")
    engine = get_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO proposals (kind, target_id, value, reason, status, created_at)"
                " VALUES ('category', 1, 'Dining', 'a cafe', 'open', '2026-05-25 12:00:00.000000')"
            )
        )
    engine.dispose()
    command.upgrade(config, "0024")
    found = columns(url)
    assert found[-1] == ADDED
    orm = [(c.name, str(c.type), c.nullable) for c in ProposalRow.__table__.columns]
    assert orm[: len(found)] == found
    assert reasons(url) == ["a cafe"]
    command.downgrade(config, "0023")
    assert columns(url)[-1] == ("parent_id", "INTEGER", True)
    assert reasons(url) == ["a cafe"]
    command.upgrade(config, "0024")
    assert columns(url)[-1] == ADDED
```

`tests/integration/test_mcp_rule_changes.py`

```python
from datetime import UTC, date, datetime

import anyio
import pytest
from mcp.client import Client

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_rule,
    list_categories,
    list_category_assignments,
    set_category_by_hand,
)
from finances.mcp_server.server import build_server
from tests.support import failed_cleanly, run, table_rows

BEFORE = 'contains "ACME" -> Dining (priority 0)'
CHANGE = {"rule_id": 1, "reason": "a coffee shop", "category": "Coffee & Dessert", "priority": 5}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def error(name: str, arguments: dict) -> list[str]:
    return [item.text for item in call(name, arguments).content]


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Rule 1 puts ACME in Dining, so transaction 1 (ACME COFFEE) is Dining by the rule;
    a person set transaction 2 (FOOBAR GROCERY) to Groceries by hand."""
    monkeypatch.setattr(
        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    )
    monkeypatch.setattr(
        "finances.db.repositories.rule_changes._now",
        lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
    )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-500, "ACME COFFEE"), (-2599, "FOOBAR GROCERY")), start=1
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
        create_rule(session, "ACME", "Dining")
        categorize(session)
        set_category_by_hand(session, 2, "Groceries")
    engine.dispose()
    return tmp_settings


def category_of(transaction_id: int) -> str | None:
    engine = get_engine()
    with session_scope(engine) as session:
        found = list_category_assignments(session).get(transaction_id)
        names = {category.id: category.name for category in list_categories(session)}
    engine.dispose()
    return None if found is None else names[found.category_id]


def review_row() -> list[str]:
    return table_rows(run("review", "list").stdout)[1]


def test_a_persons_choice_can_be_proposed_over(card: Settings) -> None:
    made = call("propose_category", {"transaction_id": 2, "category": "Dining", "reason": "a deli"})
    assert made.structured_content["proposal"]["category"] == "Dining"
    assert review_row()[5:] == ["Groceries", "Dining", "a deli", "open"]
    accepted = run("review", "accept", "--id", "1")
    assert accepted.stdout == "Accepted proposal 1: Dining for transaction 2.\n"
    assert category_of(2) == "Dining"


def test_the_category_it_has_is_refused(card: Settings) -> None:
    arguments = {"transaction_id": 2, "category": "groceries", "reason": "a grocer"}
    assert error("propose_category", arguments) == [
        "Error executing tool propose_category: the transaction already has this category"
    ]


def test_a_person_changing_it_since_puts_it_out_of_date(card: Settings) -> None:
    call("propose_category", {"transaction_id": 2, "category": "Dining", "reason": "a deli"})
    run("transactions", "set-category", "--id", "2", "--category", "Coffee & Dessert")
    assert review_row()[8] == "out of date"
    assert failed_cleanly(
        run("review", "accept", "--id", "1"),
        "proposal 1 is out of date: the transaction was decided since",
    )


def test_the_agent_proposes_changing_a_rule(card: Settings) -> None:
    made = call("propose_rule_change", CHANGE).structured_content["proposal"]
    assert {key: made[key] for key in ("kind", "transaction_id", "category", "rule")} == {
        "kind": "rule_edit",
        "transaction_id": None,
        "category": "Coffee & Dessert",
        "rule": {"match": "contains", "pattern": "ACME", "priority": 5},
    }
    assert made["rule_change"] == {"rule_id": 1, "before": BEFORE, "delete": False}
    assert review_row() == [
        "1",
        "",
        "",
        "",
        "",
        BEFORE,
        'rule 1: contains "ACME" -> Coffee & Dessert (priority 5)',
        "a coffee shop",
        "open",
    ]
    accepted = run("review", "accept", "--id", "1")
    assert accepted.stdout == (
        'Accepted proposal 1: rule 1 is now contains "ACME" -> Coffee & Dessert (priority 5).\n'
        "Categorized 2 transactions: 1 changed, 0 without a category.\n"
    )
    assert (category_of(1), category_of(2)) == ("Coffee & Dessert", "Groceries")


def test_the_agent_proposes_deleting_a_rule(card: Settings) -> None:
    made = call("propose_rule_change", {"rule_id": 1, "reason": "too broad", "delete": True})
    proposal = made.structured_content["proposal"]
    assert (proposal["kind"], proposal["rule_change"]) == (
        "rule_delete",
        {"rule_id": 1, "before": BEFORE, "delete": True},
    )
    assert review_row()[5:7] == [BEFORE, "delete rule 1"]
    accepted = run("review", "accept", "--id", "1")
    assert accepted.stdout == (
        "Accepted proposal 1: rule 1 deleted.\n"
        "Categorized 2 transactions: 0 changed, 1 without a category.\n"
    )
    assert table_rows(run("rules", "list").stdout)[1:] == []


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({**CHANGE, "rule_id": 9}, "rule not found"),
        ({"rule_id": 1, "reason": "why"}, "name at least one field to change"),
        ({**CHANGE, "delete": True}, "a deletion changes no fields"),
        ({"rule_id": 1, "reason": "why", "category": "dining"}, "the rule already is like this"),
        ({**CHANGE, "category": "Food"}, "rules and transactions take a category, not a group"),
        ({**CHANGE, "category": "Pets"}, "category not found"),
        ({**CHANGE, "reason": " "}, "a reason must be 1 to 200 characters"),
    ],
)
def test_a_refused_rule_change(card: Settings, arguments: dict, message: str) -> None:
    assert error("propose_rule_change", arguments) == [
        f"Error executing tool propose_rule_change: {message}"
    ]


def test_one_open_change_for_a_rule(card: Settings) -> None:
    call("propose_rule_change", CHANGE)
    assert error("propose_rule_change", {"rule_id": 1, "reason": "x", "delete": True}) == [
        "Error executing tool propose_rule_change: this rule already has an open proposal"
    ]


def test_a_rule_edited_since_puts_it_out_of_date(card: Settings) -> None:
    call("propose_rule_change", CHANGE)
    run("rules", "edit", "--id", "1", "--priority", "3")
    assert review_row()[8] == "out of date"
    assert failed_cleanly(
        run("review", "accept", "--id", "1"),
        "proposal 1 is out of date: the rules or categories changed since",
    )


def test_a_declined_change_is_not_proposed_again(card: Settings) -> None:
    call("propose_rule_change", CHANGE)
    run("review", "decline", "--id", "1")
    assert error("propose_rule_change", CHANGE) == [
        "Error executing tool propose_rule_change: a person declined this proposal already"
    ]
    assert (
        call("propose_rule_change", {**CHANGE, "priority": 6}).structured_content["proposal"]["id"]
        == 2
    )
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_rule_changes_more.py` (section core):

- a category proposal over a person's choice (`before` `Groceries`): a person setting `Groceries` again by hand leaves it open; a person clearing it (`fin transactions set-category --clear`, so a rule or nothing sets it) leaves it open; a person setting `Dining` puts it out of date;
- a category proposal made with `before` None (as every proposal before this phase) goes out of date when a person sets any category, as today;
- a split transaction and one in a transfer are still refused with `a person has already decided this transaction`;
- `propose_rule_change` with a new pattern another rule already has (same match) is refused with that message, and with only the match changed to one that makes a duplicate, too;
- a delete proposal's stored `value`, `pattern`, `match`, and `priority` are the rule's current ones;
- History records `proposal_accepted` with `rule 1: …` and `delete rule 1`, and the `rule_edited` and `rule_deleted` that `edit_rule` and `delete_rule` already record;
- the Review page lists a rule change with empty transaction cells and accepts it (`POST /review`).

## Rules for this phase

- The tool only stores proposals: nothing in `mcp_server` calls `edit_rule` or `delete_rule`.
- Earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the check: `.venv/bin/python scripts/check.py --first migrations,core,mcp,cli,web`;
- the given test files above, 17 tests; at least N + 17 passed in all;
- `git diff --stat HEAD -- tests` lists only `tests/support.py` and the twelve files of the given diff;
- `git grep -n -e "edit_rule" -e "delete_rule" -- src/finances/mcp_server` prints nothing;
- the coverage command: `.venv/bin/python -m coverage report --include="*/finances/db/orm.py,*/finances/domain/proposals.py,*/finances/db/repositories/proposals.py,*/finances/db/repositories/rule_changes.py,*/finances/categorize/service.py,*/finances/analysis/review.py,*/finances/views/review.py,*/finances/mcp_server/tools.py,*/finances/mcp_server/server.py" --fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 44a: proposing over a person's choice, and changing a rule (YYYY-MM-DD)`.
