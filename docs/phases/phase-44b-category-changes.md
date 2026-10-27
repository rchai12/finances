# Phase 44b: renaming and deleting categories by proposal

## Goal

The last part of Phase 44. With the owner's choices (2026-10-26 and 27), a new `propose_category_change` lets the agent propose:

- **renaming** a category or a group;
- **deleting** a category, naming the existing category its transactions, rules, and budget move to when it is in use, or an empty group.

Like every proposal it changes nothing until a person accepts it in `fin review` or on the Review page, and it goes through the same code a person uses (`rename_category`, `delete_category`), so its refusals are word for word those of `fin categories rename` and `fin categories delete`. When a person accepts:

- a **rename**, the agent's other open proposals that name the old name now name the new one, so they stay usable;
- a **delete**, the agent's other open proposals that name the deleted category go out of date.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-44a-proposing-over-a-choice-and-rule-changes.md`, `src/finances/db/repositories/rule_changes.py` (the shape to follow), `src/finances/db/repositories/categories.py` (`rename_category`, `delete_category`, `_category_row`, `_leaf_category`), `src/finances/db/repositories/proposals.py` and `chains.py` (out of date and accepting), `src/finances/analysis/review.py`, `src/finances/views/review.py`, `src/finances/mcp_server/tools.py`, `src/finances/mcp_server/server.py`

## Starting state

N is `4190` when Phase 44a is the last phase built. **Sections: core, mcp, cli, web.** `proposals.py` and `categories.py` are at 398 of the 400 lines the split test allows: the new kinds' checks, out of date, and accepting live in a new `repositories/category_changes.py`. `proposals.before` exists since 44a. No migration. A spike showed that `rename_category` and `delete_category` run inside `session.begin_nested()` and rolled back leave nothing behind, History included.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/proposals.py` | `CATEGORY_RENAME`, `CATEGORY_DELETE`, `KINDS`, `proposal_text` (R1) |
| `src/finances/db/repositories/category_changes.py` (new), `__init__.py` | `propose_category_change`, its out of date and accepting, and what accepting does to other proposals (R2 to R5) |
| `src/finances/db/repositories/proposals.py`, `chains.py`, `rule_changes.py` | dispatch to the new module; a category proposal or rule change whose category is gone is out of date (R4) |
| `src/finances/analysis/review.py`, `src/finances/views/review.py` | the rows and texts (R6) |
| `src/finances/mcp_server/tools.py`, `server.py` | the tool; `"category_change"` on every item; the description (R7) |
| `tests/support.py` and eleven earlier test files | the given diff (R8) |
| `tests/integration/test_mcp_category_changes.py` | new: given |
| `tests/integration/test_category_changes_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Moving a category to another group; changing a group's flags; a delete whose `move_to` is still only proposed; a chain through a category change.

## Dependencies

None new.

## Design

```python
# src/finances/domain/proposals.py
CATEGORY_RENAME = "category_rename"
CATEGORY_DELETE = "category_delete"
KINDS = (..., RULE_EDIT, RULE_DELETE, CATEGORY_RENAME, CATEGORY_DELETE)

# src/finances/db/repositories/category_changes.py
def propose_category_change(
    session: Session, name: str, reason: str, *, rename_to: str | None = None,
    delete: bool = False, move_to: str | None = None,
) -> Proposal: ...
```

**Checks**, in this order (all `ValueError`, or `CategoryExistsError` where `rename_category` raises it):

| Check | Refusal |
|---|---|
| the reason, whitespace collapsed, is 1 to 200 characters | `a reason must be 1 to 200 characters` |
| a category or group has `name` (ignoring case) | `category not found` |
| not both `rename_to` and `delete` | `rename or delete, not both` |
| one of them | `name a new name or delete=true` |
| a rename's new name, stripped, differs from the name now | `the name already is like this` |
| the change itself: `rename_category(session, name, rename_to)` or `delete_category(session, name, move_to or "")`, called inside `session.begin_nested()` and always rolled back | whatever it raises, word for word |
| no declined proposal of the same kind for this category with the same `rename_to` or `move_to` | `a person declined this proposal already` |
| no open rename or delete proposal for this category | `this category already has an open proposal` |

Stored: kind `CATEGORY_RENAME` or `CATEGORY_DELETE`; `target_id` = the category's id; `before` = its name now; `value` = the new name as stripped (a rename), or the `move_to` category's name as the database spells it, or `""` (a delete without one); every other column None. `created_at` comes from a `_now()` of `category_changes.py`'s own (the given test patches it).

**Out of date** when the category (by `target_id`) is gone, its name differs from `before`, or the change would now be refused (the same dry run inside a savepoint). Accepting one out of date is refused with `proposal N is out of date: the categories changed since`.

**Accepting.** A rename calls `rename_category(session, before, value)`; a delete calls `delete_category(session, before, value)`. Neither runs categorize (the terminal's commands do not). Then:

- **after a rename**, every open proposal of the kinds `CATEGORY`, `RULE`, `RULE_EDIT`, and `RULE_DELETE` whose `value` is the old name, and every open `NEW_CATEGORY` whose `group` is the old name, takes the new name instead (as the database spells it); and every open `RULE_EDIT` or `RULE_DELETE` whose `before` was its rule's line just before the rename gets its rule's line after it, so a proposal that was not out of date before the rename is not out of date after it;
- **after a delete**, nothing is rewritten: proposals that name the deleted category go out of date, since a `CATEGORY` proposal and a `RULE_EDIT` whose category no longer exists (and that does not wait, as 41c defines it) are now out of date too, beside the rules of today. A rule change whose rule `delete_category` moved is out of date already, since its line changed.

| Text | Rename `Dining` to `Restaurants` | Delete `Dining`, uses to `Coffee & Dessert` | Delete `Spare` (no `move_to`) |
|---|---|---|---|
| `proposal_text` (History) | `category Dining: rename to Restaurants` | `category Dining: delete, moving its uses to Coffee & Dessert` | `category Spare: delete` |
| review: Now / Proposed | `Dining` / `rename to Restaurants` | `Dining` / `delete, moving its uses to Coffee & Dessert` | `Spare` / `delete` |
| `accepted_text` | `Accepted proposal N: Dining is now Restaurants.` | `Accepted proposal N: Dining deleted, its uses moved to Coffee & Dessert.` | `Accepted proposal N: Spare deleted.` |

A category change has no transaction: `review_items` gives it `transaction` None, `account` None, and `current` = `before`.

**MCP.** `propose_category_change` is registered after `propose_rule_change`, with the writers' annotations:

```python
def propose_category_change(
    name: str, reason: str, rename_to: str | None = None, delete: bool = False,
    move_to: str | None = None,
) -> dict[str, Any]: ...
```

Every proposal item gains `"category_change"`: None, except for the two new kinds: `{"name": <before>, "rename_to": <value or None>, "delete": <bool>, "move_to": <value, or None when empty or a rename>}`; for them `"transaction_id"` and `"category"` are None. The description, exactly:

```python
PROPOSE_CATEGORY_CHANGE_DESCRIPTION = (
    "Propose renaming a category or group (rename_to), or deleting one (delete=true): a "
    "category in use needs move_to, the existing category its transactions, rules, and budget "
    "move to; a group must be empty. Give a one-line reason a person will read. It changes "
    "nothing until a person accepts it with fin review; then a rename carries your other open "
    "proposals to the new name. Refused as fin categories rename and delete refuse, and when a "
    "person declined it or another proposal for that category is open. No amounts."
)
```

## Requirements

- **R1.** `CATEGORY_RENAME`, `CATEGORY_DELETE`, `KINDS`, and `proposal_text` as designed.
- **R2.** `propose_category_change` as designed, its checks in the table's order, exported from `finances.db.repositories`.
- **R3.** Accepting the two kinds as designed.
- **R4.** Out of date for the two kinds, and for a `CATEGORY` proposal and a `RULE_EDIT` whose category is gone, as designed.
- **R5.** What accepting a rename does to the other open proposals, as designed.
- **R6.** The review rows and the texts as designed.
- **R7.** The MCP tool, `"category_change"` on every item, and the description as designed.
- **R8.** Apply the given diff to `tests/support.py` and the eleven earlier test files. No other earlier test changes.

## Given diff to earlier tests

The tool lists, the description table, the repository areas, the kinds, and `"category_change": None` beside `"rule_change"` in every whole proposal item. With `"category_change"` added to the item, all of these pass except the two that need the new tool registered.

```text
diff --git a/tests/integration/test_mcp_accounts.py b/tests/integration/test_mcp_accounts.py
index 0a6356c..bf88cc9 100644
--- a/tests/integration/test_mcp_accounts.py
+++ b/tests/integration/test_mcp_accounts.py
@@ -36,6 +36,7 @@ NO_AMOUNTS = (
     "propose_group",
     "propose_new_category",
     "propose_rule_change",
+    "propose_category_change",
 )
 READ_ONLY = {
     "read_only_hint": True,
diff --git a/tests/integration/test_mcp_alias_proposals.py b/tests/integration/test_mcp_alias_proposals.py
index 596fad4..40f90e8 100644
--- a/tests/integration/test_mcp_alias_proposals.py
+++ b/tests/integration/test_mcp_alias_proposals.py
@@ -69,6 +69,7 @@ def test_the_agent_proposes_an_alias(card: Settings) -> None:
             "new": None,
             "waits_for": None,
             "rule_change": None,
+            "category_change": None,
             "reason": "the same shop",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_more.py b/tests/integration/test_mcp_more.py
index 050592a..8fbdd78 100644
--- a/tests/integration/test_mcp_more.py
+++ b/tests/integration/test_mcp_more.py
@@ -34,6 +34,7 @@ from finances.mcp_server.server import (
     LIST_UNCATEGORIZED_DESCRIPTION,
     LOG_ADVICE_DESCRIPTION,
     MONTH_OVER_MONTH_DESCRIPTION,
+    PROPOSE_CATEGORY_CHANGE_DESCRIPTION,
     PROPOSE_CATEGORY_DESCRIPTION,
     PROPOSE_GROUP_DESCRIPTION,
     PROPOSE_MERCHANT_ALIAS_DESCRIPTION,
@@ -169,6 +170,7 @@ def test_each_tool_description_matches_the_table(tmp_settings: Settings) -> None
         "propose_group": PROPOSE_GROUP_DESCRIPTION,
         "propose_new_category": PROPOSE_NEW_CATEGORY_DESCRIPTION,
         "propose_rule_change": PROPOSE_RULE_CHANGE_DESCRIPTION,
+        "propose_category_change": PROPOSE_CATEGORY_CHANGE_DESCRIPTION,
         "list_proposals": LIST_PROPOSALS_DESCRIPTION,
         "log_advice": LOG_ADVICE_DESCRIPTION,
         "list_advice": LIST_ADVICE_DESCRIPTION,
diff --git a/tests/integration/test_mcp_new_categories.py b/tests/integration/test_mcp_new_categories.py
index f83ce92..a003bff 100644
--- a/tests/integration/test_mcp_new_categories.py
+++ b/tests/integration/test_mcp_new_categories.py
@@ -68,6 +68,7 @@ def item(kind: str, new: dict, reason: str) -> dict:
             "new": new,
             "waits_for": None,
             "rule_change": None,
+            "category_change": None,
             "reason": reason,
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_proposals.py b/tests/integration/test_mcp_proposals.py
index 6a80f42..965945c 100644
--- a/tests/integration/test_mcp_proposals.py
+++ b/tests/integration/test_mcp_proposals.py
@@ -32,6 +32,7 @@ FROM_REPOSITORIES = {
     "log_advice",
     "proposal_out_of_date",
     "propose_category",
+    "propose_category_change",
     "propose_group",
     "propose_merchant_alias",
     "propose_new_category",
@@ -112,6 +113,7 @@ def test_a_proposal_and_its_listing(one: Settings) -> None:
         "new": None,
         "waits_for": None,
         "rule_change": None,
+        "category_change": None,
         "reason": "a cafe",
         "status": "open",
         "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_rule_proposals.py b/tests/integration/test_mcp_rule_proposals.py
index 6e259ab..b1a848f 100644
--- a/tests/integration/test_mcp_rule_proposals.py
+++ b/tests/integration/test_mcp_rule_proposals.py
@@ -71,6 +71,7 @@ def test_the_agent_proposes_a_rule(card: Settings) -> None:
             "new": None,
             "waits_for": None,
             "rule_change": None,
+            "category_change": None,
             "reason": "a cafe",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_transfer_proposals.py b/tests/integration/test_mcp_transfer_proposals.py
index 0d6d77b..af7b453 100644
--- a/tests/integration/test_mcp_transfer_proposals.py
+++ b/tests/integration/test_mcp_transfer_proposals.py
@@ -63,6 +63,7 @@ def test_the_agent_proposes_a_transfer(moved: Settings) -> None:
             "new": None,
             "waits_for": None,
             "rule_change": None,
+            "category_change": None,
             "reason": "same day, same amount",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_transfer_proposals_more.py b/tests/integration/test_transfer_proposals_more.py
index 7f2d451..1138113 100644
--- a/tests/integration/test_transfer_proposals_more.py
+++ b/tests/integration/test_transfer_proposals_more.py
@@ -40,6 +40,7 @@ PAIR = {
     "new": None,
     "waits_for": None,
     "rule_change": None,
+    "category_change": None,
     "reason": "interest, not a transfer",
     "status": "open",
     "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/support.py b/tests/support.py
index b46f8d2..a0b78f4 100644
--- a/tests/support.py
+++ b/tests/support.py
@@ -173,6 +173,7 @@ MCP_TOOLS = [
     "log_advice",
     "month_over_month",
     "propose_category",
+    "propose_category_change",
     "propose_group",
     "propose_merchant_alias",
     "propose_new_category",
@@ -190,5 +191,6 @@ MCP_WRITERS = (
     "propose_group",
     "propose_new_category",
     "propose_rule_change",
+    "propose_category_change",
     "log_advice",
 )
diff --git a/tests/unit/test_proposal_rules.py b/tests/unit/test_proposal_rules.py
index 03371f4..6a51472 100644
--- a/tests/unit/test_proposal_rules.py
+++ b/tests/unit/test_proposal_rules.py
@@ -29,6 +29,8 @@ def test_the_lists_and_limits() -> None:
             "new_category",
             "rule_edit",
             "rule_delete",
+            "category_rename",
+            "category_delete",
         ),
     )
     assert (OPEN, ACCEPTED, DECLINED, STATUSES) == (
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index 6f24eea..b4819a0 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -90,6 +90,9 @@ HOMES = {
         "record_sync_failure",
         "set_feed_account_ignored",
     ],
+    "category_changes": [
+        "propose_category_change",
+    ],
     "chains": [
         "accepting_order",
         "decline_proposals",
@@ -194,7 +197,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 134
+    assert len(expected) == 135
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
diff --git a/tests/unit/test_rule_proposal_rules.py b/tests/unit/test_rule_proposal_rules.py
index a9f6b75..72fcf9b 100644
--- a/tests/unit/test_rule_proposal_rules.py
+++ b/tests/unit/test_rule_proposal_rules.py
@@ -27,6 +27,8 @@ def test_the_kinds() -> None:
         "new_category",
         "rule_edit",
         "rule_delete",
+        "category_rename",
+        "category_delete",
     )
 
 
```

## Given tests

18 tests in one file. Do not change them.

`tests/integration/test_mcp_category_changes.py`

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

RENAME = {"name": "dining", "reason": "clearer", "rename_to": "Restaurants"}
DELETE = {"name": "Dining", "reason": "a duplicate", "delete": True, "move_to": "coffee & dessert"}
IN_USE = "Dining is in use (transactions: 1, rules: 1); choose a category to move them to"


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def made(name: str, arguments: dict) -> dict:
    return call(name, arguments).structured_content["proposal"]


def error(name: str, arguments: dict) -> list[str]:
    return [item.text for item in call(name, arguments).content]


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Rule 1 puts ACME in Dining, so transaction 1 (ACME COFFEE) is Dining by the rule;
    a person set transaction 2 (FOOBAR GROCERY) to Groceries by hand."""
    for module in ("proposals", "category_changes"):
        monkeypatch.setattr(
            f"finances.db.repositories.{module}._now",
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


def rows() -> list[list[str]]:
    return table_rows(run("review", "list").stdout)[1:]


def test_the_agent_proposes_renaming_a_category(card: Settings) -> None:
    proposal = made("propose_category_change", RENAME)
    assert (proposal["kind"], proposal["transaction_id"], proposal["category_change"]) == (
        "category_rename",
        None,
        {"name": "Dining", "rename_to": "Restaurants", "delete": False, "move_to": None},
    )
    assert rows() == [["1", "", "", "", "", "Dining", "rename to Restaurants", "clearer", "open"]]
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: Dining is now Restaurants.\n",
    )
    assert ["Food", "Restaurants", ""] in table_rows(run("categories", "list").stdout)
    assert category_of(1) == "Restaurants"


def test_a_rename_carries_the_agents_other_proposals(card: Settings) -> None:
    made("propose_category", {"transaction_id": 2, "category": "Dining", "reason": "a deli"})
    made("propose_category_change", RENAME)
    run("review", "accept", "--id", "2")
    assert rows() == [
        [
            "1",
            "2026-05-02",
            "Test Card",
            "FOOBAR GROCERY",
            "-$25.99",
            "Groceries",
            "Restaurants",
            "a deli",
            "open",
        ]
    ]
    assert run("review", "accept", "--id", "1").exit_code == 0
    assert category_of(2) == "Restaurants"


def test_the_agent_proposes_deleting_a_category(card: Settings) -> None:
    proposal = made("propose_category_change", DELETE)
    assert proposal["category_change"] == {
        "name": "Dining",
        "rename_to": None,
        "delete": True,
        "move_to": "Coffee & Dessert",
    }
    assert rows()[0][5:7] == ["Dining", "delete, moving its uses to Coffee & Dessert"]
    accepted = run("review", "accept", "--id", "1")
    assert accepted.stdout == (
        "Accepted proposal 1: Dining deleted, its uses moved to Coffee & Dessert.\n"
    )
    assert category_of(1) == "Coffee & Dessert"


def test_a_delete_puts_the_agents_other_proposals_out_of_date(card: Settings) -> None:
    made("propose_category", {"transaction_id": 2, "category": "Dining", "reason": "a deli"})
    made("propose_category_change", DELETE)
    run("review", "accept", "--id", "2")
    assert [row[8] for row in rows()] == ["out of date"]


def test_the_agent_proposes_deleting_an_empty_group(card: Settings) -> None:
    run("categories", "add-group", "--name", "Spare")
    made("propose_category_change", {"name": "Spare", "reason": "unused", "delete": True})
    assert rows()[0][5:7] == ["Spare", "delete"]
    assert run("review", "accept", "--id", "1").stdout == "Accepted proposal 1: Spare deleted.\n"


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({**RENAME, "name": "Pets"}, "category not found"),
        ({"name": "Dining", "reason": "why"}, "name a new name or delete=true"),
        ({**RENAME, "delete": True}, "rename or delete, not both"),
        ({**RENAME, "rename_to": "groceries"}, "a category with this name already exists"),
        ({**RENAME, "rename_to": "Dining"}, "the name already is like this"),
        ({"name": "Dining", "reason": "why", "delete": True}, IN_USE),
        (
            {"name": "Food", "reason": "why", "delete": True},
            "a group can be deleted only when it has no categories",
        ),
        ({**DELETE, "move_to": "Food"}, "rules and transactions take a category, not a group"),
        ({**DELETE, "move_to": "Dining"}, "a category cannot be moved to itself"),
        ({**RENAME, "reason": " "}, "a reason must be 1 to 200 characters"),
    ],
)
def test_a_refused_change(card: Settings, arguments: dict, message: str) -> None:
    assert error("propose_category_change", arguments) == [
        f"Error executing tool propose_category_change: {message}"
    ]


def test_one_open_change_for_a_category(card: Settings) -> None:
    made("propose_category_change", RENAME)
    assert error("propose_category_change", DELETE) == [
        "Error executing tool propose_category_change: this category already has an open proposal"
    ]


def test_a_category_renamed_by_hand_since_puts_it_out_of_date(card: Settings) -> None:
    made("propose_category_change", RENAME)
    run("categories", "rename", "--name", "Dining", "--to", "Eating Out")
    assert rows()[0][8] == "out of date"
    assert failed_cleanly(
        run("review", "accept", "--id", "1"),
        "proposal 1 is out of date: the categories changed since",
    )


def test_a_declined_change_is_not_proposed_again(card: Settings) -> None:
    made("propose_category_change", RENAME)
    run("review", "decline", "--id", "1")
    assert error("propose_category_change", RENAME) == [
        "Error executing tool propose_category_change: a person declined this proposal already"
    ]
    assert made("propose_category_change", {**RENAME, "rename_to": "Eating Out"})["id"] == 2
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_category_changes_more.py` (section core):

- the dry run leaves nothing behind: after a refused delete and an accepted proposal of a rename, History (`list_changes`) holds only what the accepted rename and its `proposal_accepted` record;
- renaming a group carries an open `NEW_CATEGORY` proposal in that group to the new group name;
- a rule-change proposal (44a) on a rule into `Dining`, open when the rename of `Dining` is accepted, is still open afterwards, its `before` now naming `Restaurants`; one that was already out of date stays out of date;
- a category proposal that waits for a proposed category (41c) stays waiting, not out of date, after a delete of `Dining`; a `RULE_EDIT` whose new category is `Dining` is out of date after it;
- a delete proposal whose `move_to` category a person deleted since is out of date;
- a rename proposal whose new name a person took since (adding a category with it) is out of date;
- the Review page lists a category change with empty transaction cells and accepts it.

## Rules for this phase

- The tool only stores proposals: nothing in `mcp_server` calls `rename_category` or `delete_category`.
- Earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the check: `.venv/bin/python scripts/check.py --first core,mcp,cli,web`;
- the given test file above, 18 tests; at least N + 18 passed in all;
- `git diff --stat HEAD -- tests` lists only `tests/support.py` and the eleven files of the given diff;
- `git grep -n -e "rename_category" -e "delete_category" -- src/finances/mcp_server` prints nothing;
- the coverage command: `.venv/bin/python -m coverage report --include="*/finances/domain/proposals.py,*/finances/db/repositories/proposals.py,*/finances/db/repositories/chains.py,*/finances/db/repositories/rule_changes.py,*/finances/db/repositories/category_changes.py,*/finances/analysis/review.py,*/finances/views/review.py,*/finances/mcp_server/tools.py,*/finances/mcp_server/server.py" --fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 44b: renaming and deleting categories by proposal (YYYY-MM-DD)`.
