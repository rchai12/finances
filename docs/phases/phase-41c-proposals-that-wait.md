# Phase 41c: proposals that wait for another

## Goal

The last part of Phase 41. With 41b the agent proposes a new group, or a new category in an existing group. With the owner's choices (2026-10-25), it may now chain them:

- a new category in a group that is **still only proposed**;
- a transaction (`propose_category`) or a rule (`propose_rule`) put in a category that is **still only proposed**.

Such a proposal **waits for** the one it names. In `fin review list` and on the Review page its State reads `waits for #12` instead of `open`. A person accepts it only with or after what it waits for: accepting several applies parents first, and accepting a waiting one without its parent is refused. Declining a proposal also declines every proposal that waits for it, at any depth, and says so. A proposal waits only while the category or group it names does not exist: if a person makes it by hand, the proposals stop waiting and can be accepted on their own, and declining the agent's own proposal for that name (now out of date) declines nothing else.

```
ID  Proposed                                             State
4   a rule: contains "FOOBAR PET" -> Dog Food (priority 0)  waits for #2
3   Dog Food                                             waits for #2
2   a new category: Dog Food in Pets                     waits for #1
1   a new group: Pets                                    open
```

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-41b-group-and-category-proposals.md`, `src/finances/db/repositories/new_categories.py`, `src/finances/db/repositories/proposals.py` (`propose_category`, `propose_rule`, `proposal_out_of_date`, `accept_proposal`, `decline_proposal`), `src/finances/categorize/service.py` (`accept_proposals`), `src/finances/analysis/review.py`, `src/finances/views/review.py`, `src/finances/cli/review.py`, `src/finances/web/routes/review.py`, `src/finances/mcp_server/tools.py` (`_proposal_item`), `src/finances/mcp_server/server.py`

## Starting state

N is `4116` when Phase 41b is the last phase built. **Sections: core, mcp, cli, web.** `proposals.parent_id` exists since 41b's migration and is always None. `repositories/proposals.py` is 393 lines and `categories.py` 390, against the 400 the split test allows: the new rules go in a new area module, and those two files may lose lines, not gain more than they can hold. No migration.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/repositories/chains.py` (new), `__init__.py` | `waits_for`, `accepting_order`, `decline_proposals` (R1, R5, R6) |
| `src/finances/db/repositories/proposals.py`, `new_categories.py` | a proposed target in `propose_category`, `propose_rule`, `propose_new_category`; out of date and accepting with a parent (R2 to R4) |
| `src/finances/categorize/service.py` | `accept_proposals` in `accepting_order` (R5) |
| `src/finances/analysis/review.py` | `ReviewItem.waits_for`; `open_suggestions` leaves waiting ones out (R7) |
| `src/finances/views/review.py` | the state and the cascaded decline line (R7) |
| `src/finances/cli/review.py`, `src/finances/web/routes/review.py`, `src/finances/web/render.py` | declining through `decline_proposals`; the web notice (R6, R8) |
| `src/finances/web/templates/review.html` | the given diff (R8) |
| `src/finances/mcp_server/tools.py`, `server.py` | `"waits_for"` on every item; three descriptions (R9) |
| six earlier test files and `tests/unit/test_repositories_split.py` | the given diff (R10) |
| `tests/integration/test_mcp_chains.py`, `tests/integration/test_web_chains.py` | new: given |
| `tests/integration/test_chains_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- A confirmation page before a cascading decline; grouping or indenting a chain in the list.
- Accepting a parent on a dependent's behalf; chains through any other kind (a transfer, a merchant alias).
- A migration.

## Dependencies

None new.

## Design

**What a proposal names.** A proposal's target is the category named by its `value` for a `CATEGORY` or `RULE` proposal, and the group named by its `group` for a `NEW_CATEGORY` proposal; a `GROUP` proposal has none. Names are compared ignoring case.

```python
# src/finances/db/repositories/chains.py
def waits_for(session: Session, proposal: Proposal) -> int | None: ...
def accepting_order(session: Session, proposal_ids: list[int]) -> list[int]: ...
def decline_proposals(session: Session, proposal_ids: list[int]) -> list[tuple[Proposal, bool]]: ...
```

| Name | Rule |
|---|---|
| `waits_for` | the proposal's `parent_id` when it is open, it has a `parent_id`, the parent is open, and the target does not exist (for `CATEGORY` and `RULE` a category, for `NEW_CATEGORY` a group); otherwise None |
| `accepting_order` | the same ids, each once: going through them in the order given, each id is placed after its ancestors that are in the list and not yet placed (by `parent_id`, at any depth), oldest ancestor first. So `[3, 9, 1, 2]`, where 3 waits for 2 and 2 for 1, gives `[1, 2, 3, 9]` |
| `decline_proposals` | for each id in the order given, unless this call already declined it: `decline_proposal(session, id)` (its refusals unchanged), then, depth first and in id order, every open proposal whose `parent_id` is that id and whose target does not exist is declined too, and in turn its own. Returns each declined proposal once, in the order declined, with `True` for one declined because it waited (the cascade) and `False` for one the caller named |

**Proposing.** When the name given is not an existing category (for `propose_category` and `propose_rule`) or group (for `propose_new_category`), but an **open** `NEW_CATEGORY` (respectively `GROUP`) proposal has that name, the new proposal is stored with `parent_id` = that proposal's id and the name as that proposal spells it (`value` for a category or rule, `group` for a new category). Otherwise the checks and messages are those of today (`category not found`, `rules and transactions take a category, not a group`, `group not found`), in today's order. `propose_rule` checks its pattern against the example as today; the proposed category's id plays no part.

**Out of date.** A proposal that waits (`waits_for` not None) is not out of date for want of its target. A proposal with a `parent_id` whose target does not exist and whose parent is no longer open is out of date. Every other rule of `proposal_out_of_date` is unchanged, and it is checked first: a waiting `CATEGORY` proposal whose transaction a person decided since is out of date.

**Accepting.** `accept_proposal` refuses a waiting proposal before anything else: `proposal N waits for proposal P`. `accept_proposals` accepts the ids in `accepting_order`, so `Accepted.proposals` lists them parents first; a refusal of any (a waiting one whose parent is not in the list, for example) refuses the whole call, as today.

**Declining.** `fin review decline` and the Review page decline through `decline_proposals`. The terminal prints `Declined proposal N.` for one named and `Declined proposal N, which waited for P.` for one cascaded (P its `parent_id`). The page redirects to `/review?notice=proposals-declined-waiting` when any was cascaded, whose notice is `Proposals declined, with the ones that waited for them. The agent will not propose them again.`, and to the existing `proposals-declined` otherwise. History records each decline as today, through `decline_proposal`.

**Showing.** `ReviewItem` gains `waits_for: int | None = None` as its last field, filled by `waits_for`. A row's state is `out of date` when out of date, else `waits for #P` when it waits, else the status. `open_suggestions` leaves out a waiting proposal. Every MCP proposal item gains `"waits_for"`: the same value.

**The descriptions**, exactly:

```python
PROPOSE_CATEGORY_DESCRIPTION = (
    "Propose a category for a transaction without one (or set only by a rule), with a one-line "
    "reason a person will read. The category may be one still proposed with "
    "propose_new_category; this proposal then waits for that one. It changes nothing: a person "
    "accepts or declines it with fin review. Refused when a person already decided the "
    "transaction, declined this same proposal, or another proposal for it is open."
)
PROPOSE_RULE_DESCRIPTION = (
    "Propose a rule that puts every transaction whose merchant matches pattern in a category "
    "(match: contains, starts_with, or equals; priority -1000 to 1000, higher tried first), "
    "with an example transaction it matches and a one-line reason a person will read. The "
    "category may be one still proposed with propose_new_category; this proposal then waits "
    "for that one. It changes nothing until a person accepts it; then the rules run over every "
    "transaction. Refused when it does not match the example, a rule with this pattern and "
    "match exists, a person declined it, or another proposal for it is open. No amounts."
)
PROPOSE_NEW_CATEGORY_DESCRIPTION = (
    "Propose a new category (a name) in a group, tax-relevant or not, with an example "
    "transaction it is for and a one-line reason a person will read. The group may be one still "
    "proposed with propose_group; this proposal then waits for that one. It changes nothing "
    "until a person accepts it with fin review; then propose_category can put transactions in "
    "it. Refused when the group neither exists nor is proposed, a category or group has the "
    "name, a person declined it, or another proposal for that name is open. No amounts."
)
```

## Requirements

- **R1.** `waits_for` as designed.
- **R2.** `propose_category`, `propose_rule`, and `propose_new_category` accept a proposed target as designed; nothing else about them changes.
- **R3.** Out of date as designed.
- **R4.** `accept_proposal` refuses a waiting proposal as designed.
- **R5.** `accepting_order`, and `accept_proposals` through it, as designed.
- **R6.** `decline_proposals` as designed; the terminal and the page decline through it.
- **R7.** `ReviewItem.waits_for`, the state, and `open_suggestions` as designed.
- **R8.** The terminal lines and the web notice as designed; apply the given template diff exactly.
- **R9.** `"waits_for"` on every MCP item and the three descriptions as designed.
- **R10.** Apply the given diff to the earlier tests. No other earlier test changes.

## Given template diff

Applied to `src/finances/web/templates/` (do not change). It changes one hint; no earlier test reads it.

```text
diff --git a/src/finances/web/templates/review.html b/src/finances/web/templates/review.html
index 08c4ba4..a37e3e3 100644
--- a/src/finances/web/templates/review.html
+++ b/src/finances/web/templates/review.html
@@ -16,7 +16,7 @@
 </table>
 <p class="fields"><button type="submit" name="decision" value="accept">Accept chosen</button> <button type="submit" name="decision" value="decline">Decline chosen</button></p>
 </form>
-<p class="hint">Accepting sets the category as your choice. Declining changes nothing, and the agent will not propose the same again. An out of date proposal can only be declined.</p>
+<p class="hint">Accepting sets the category as your choice. Declining changes nothing, and the agent will not propose the same again. An out of date proposal can only be declined. A proposal that waits for another can be accepted only with it or after it, and declining one also declines what waits for it.</p>
 {% else %}
 <p class="empty">No open proposals.</p>
 {% endif %}
```

## Given diff to earlier tests

`"waits_for": None` beside `"new"` in every whole proposal item an earlier test pins, and the new repository area. With `"waits_for"` added to the item, all 34 tests of those six files pass.

```text
diff --git a/tests/integration/test_mcp_alias_proposals.py b/tests/integration/test_mcp_alias_proposals.py
index c406130..0aa7107 100644
--- a/tests/integration/test_mcp_alias_proposals.py
+++ b/tests/integration/test_mcp_alias_proposals.py
@@ -67,6 +67,7 @@ def test_the_agent_proposes_an_alias(card: Settings) -> None:
             "rule": None,
             "alias": {"source": "ACME CAFE", "target": "ACME COFFEE"},
             "new": None,
+            "waits_for": None,
             "reason": "the same shop",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_new_categories.py b/tests/integration/test_mcp_new_categories.py
index 4d1808c..24538dc 100644
--- a/tests/integration/test_mcp_new_categories.py
+++ b/tests/integration/test_mcp_new_categories.py
@@ -66,6 +66,7 @@ def item(kind: str, new: dict, reason: str) -> dict:
             "rule": None,
             "alias": None,
             "new": new,
+            "waits_for": None,
             "reason": reason,
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_proposals.py b/tests/integration/test_mcp_proposals.py
index fd95d4f..273ad86 100644
--- a/tests/integration/test_mcp_proposals.py
+++ b/tests/integration/test_mcp_proposals.py
@@ -109,6 +109,7 @@ def test_a_proposal_and_its_listing(one: Settings) -> None:
         "rule": None,
         "alias": None,
         "new": None,
+        "waits_for": None,
         "reason": "a cafe",
         "status": "open",
         "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_rule_proposals.py b/tests/integration/test_mcp_rule_proposals.py
index b7c5b37..afed7ed 100644
--- a/tests/integration/test_mcp_rule_proposals.py
+++ b/tests/integration/test_mcp_rule_proposals.py
@@ -69,6 +69,7 @@ def test_the_agent_proposes_a_rule(card: Settings) -> None:
             "rule": {"match": "equals", "pattern": "ACME COFFEE", "priority": 5},
             "alias": None,
             "new": None,
+            "waits_for": None,
             "reason": "a cafe",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_transfer_proposals.py b/tests/integration/test_mcp_transfer_proposals.py
index c3c5cc8..f459eca 100644
--- a/tests/integration/test_mcp_transfer_proposals.py
+++ b/tests/integration/test_mcp_transfer_proposals.py
@@ -61,6 +61,7 @@ def test_the_agent_proposes_a_transfer(moved: Settings) -> None:
             "rule": None,
             "alias": None,
             "new": None,
+            "waits_for": None,
             "reason": "same day, same amount",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_transfer_proposals_more.py b/tests/integration/test_transfer_proposals_more.py
index 1ff1d26..4844ebd 100644
--- a/tests/integration/test_transfer_proposals_more.py
+++ b/tests/integration/test_transfer_proposals_more.py
@@ -38,6 +38,7 @@ PAIR = {
     "rule": None,
     "alias": None,
     "new": None,
+    "waits_for": None,
     "reason": "interest, not a transfer",
     "status": "open",
     "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index c4b19b7..11e9535 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -86,6 +86,11 @@ HOMES = {
         "record_sync_failure",
         "set_feed_account_ignored",
     ],
+    "chains": [
+        "accepting_order",
+        "decline_proposals",
+        "waits_for",
+    ],
     "new_categories": [
         "propose_group",
         "propose_new_category",
@@ -182,7 +187,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 128
+    assert len(expected) == 131
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
```

## Given tests

12 tests in two files. Do not change them. One (`test_an_unknown_name_is_still_refused`) is a guard that passes today and must still pass.

`tests/integration/test_mcp_chains.py`

```python
from datetime import UTC, date, datetime

import anyio
import pytest
from mcp.client import Client

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    get_category_by_name,
    list_categories,
    list_category_assignments,
)
from finances.mcp_server.server import build_server
from tests.support import failed_cleanly, run, table_rows

GROUP = {"name": "Pets", "example_id": 1, "reason": "pet costs"}
CATEGORY = {"name": "Dog Food", "group": "pets", "example_id": 1, "reason": "a pet shop"}
PUT = {"transaction_id": 1, "category": "dog food", "reason": "dog food"}
RULE = {"example_id": 1, "pattern": "FOOBAR PET", "category": "Dog Food", "reason": "the shop"}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def made(name: str, arguments: dict) -> dict:
    return call(name, arguments).structured_content["proposal"]


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


@pytest.fixture
def chain(card: Settings) -> Settings:
    """1 a group Pets; 2 a category Dog Food in it; 3 transaction 1 in Dog Food; 4 a rule into
    Dog Food. 2 waits for 1, and 3 and 4 wait for 2."""
    made("propose_group", GROUP)
    made("propose_new_category", CATEGORY)
    made("propose_category", PUT)
    made("propose_rule", RULE)
    return card


def states() -> list[list[str]]:
    return [[row[0], row[6], row[8]] for row in table_rows(run("review", "list").stdout)[1:]]


def category_of_transaction() -> str | None:
    engine = get_engine()
    with session_scope(engine) as session:
        found = list_category_assignments(session).get(1)
        names = {category.id: category.name for category in list_categories(session)}
    engine.dispose()
    return None if found is None else names[found.category_id]


def test_each_proposal_names_what_it_waits_for(card: Settings) -> None:
    assert made("propose_group", GROUP)["waits_for"] is None
    second = made("propose_new_category", CATEGORY)
    assert (second["new"]["group"], second["waits_for"]) == ("Pets", 1)
    third = made("propose_category", PUT)
    assert (third["category"], third["waits_for"]) == ("Dog Food", 2)
    fourth = made("propose_rule", RULE)
    assert (fourth["category"], fourth["waits_for"]) == ("Dog Food", 2)
    listed = call("list_proposals").structured_content["proposals"]
    assert [(item["id"], item["waits_for"]) for item in listed] == [
        (4, 2),
        (3, 2),
        (2, 1),
        (1, None),
    ]


def test_the_list_shows_what_waits(chain: Settings) -> None:
    assert states() == [
        ["4", 'a rule: contains "FOOBAR PET" -> Dog Food (priority 0)', "waits for #2"],
        ["3", "Dog Food", "waits for #2"],
        ["2", "a new category: Dog Food in Pets", "waits for #1"],
        ["1", "a new group: Pets", "open"],
    ]


def test_an_unknown_name_is_still_refused(card: Settings) -> None:
    refused = call("propose_category", {**PUT, "category": "Cat Food"})
    assert [item.text for item in refused.content] == [
        "Error executing tool propose_category: category not found"
    ]
    refused = call("propose_new_category", {**CATEGORY, "group": "Birds"})
    assert [item.text for item in refused.content] == [
        "Error executing tool propose_new_category: group not found"
    ]


def test_a_waiting_proposal_is_not_accepted_alone(chain: Settings) -> None:
    assert failed_cleanly(run("review", "accept", "--id", "3"), "proposal 3 waits for proposal 2")
    assert failed_cleanly(
        run("review", "accept", "--id", "3", "--id", "1"), "proposal 3 waits for proposal 2"
    )
    engine = get_engine()
    with session_scope(engine) as session:
        assert get_category_by_name(session, "Pets") is None
    engine.dispose()


def test_a_chain_accepted_together_goes_parents_first(chain: Settings) -> None:
    accepted = run("review", "accept", "--id", "3", "--id", "2", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: the group Pets.\n"
        "Accepted proposal 2: the category Dog Food in Pets.\n"
        "Accepted proposal 3: Dog Food for transaction 1.\n",
    )
    assert category_of_transaction() == "Dog Food"
    assert states() == [["4", 'a rule: contains "FOOBAR PET" -> Dog Food (priority 0)', "open"]]


def test_accepting_the_parent_ends_the_waiting(chain: Settings) -> None:
    run("review", "accept", "--id", "1")
    assert states()[-1] == ["2", "a new category: Dog Food in Pets", "open"]
    assert states()[0][2] == "waits for #2"


def test_declining_a_parent_declines_what_waits_on_it(chain: Settings) -> None:
    declined = run("review", "decline", "--id", "1")
    assert (declined.exit_code, declined.stdout) == (
        0,
        "Declined proposal 1.\n"
        "Declined proposal 2, which waited for 1.\n"
        "Declined proposal 3, which waited for 2.\n"
        "Declined proposal 4, which waited for 2.\n",
    )
    assert run("review", "list").stdout == "No open proposals.\n"


def test_a_parent_and_its_child_declined_together(chain: Settings) -> None:
    declined = run("review", "decline", "--id", "2", "--id", "3")
    assert (declined.exit_code, declined.stdout) == (
        0,
        "Declined proposal 2.\n"
        "Declined proposal 3, which waited for 2.\n"
        "Declined proposal 4, which waited for 2.\n",
    )
    assert states() == [["1", "a new group: Pets", "open"]]


def test_made_by_hand_the_proposals_stop_waiting(chain: Settings) -> None:
    run("categories", "add-group", "--name", "Pets")
    run("categories", "add", "--name", "Dog Food", "--group", "Pets")
    assert [row[2] for row in states()] == ["open", "open", "out of date", "out of date"]
    assert run("review", "decline", "--id", "2").stdout == "Declined proposal 2.\n"
    accepted = run("review", "accept", "--id", "3")
    assert accepted.stdout == "Accepted proposal 3: Dog Food for transaction 1.\n"
    assert category_of_transaction() == "Dog Food"
```

`tests/integration/test_web_chains.py`

```python
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    count_open_proposals,
    create_account,
    propose_group,
    propose_new_category,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, page, post, texts

WAITING = (
    "Proposals declined, with the ones that waited for them. The agent will not propose them again."
)


@pytest.fixture
def home(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """1 a group Pets; 2 a category Dog Food in it, which waits for 1."""
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
        session.flush()
        propose_group(session, 1, "Pets", "pet costs")
        propose_new_category(session, 1, "Dog Food", "Pets", "a pet shop")
    engine.dispose()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/review")
    return client


def open_count() -> int:
    engine = get_engine()
    with session_scope(engine) as session:
        found = count_open_proposals(session)
    engine.dispose()
    return found


def test_the_review_page_shows_what_waits(home: TestClient) -> None:
    rows = page(home, "/review").rows
    assert [row[-1] for row in rows if row and row[0] in ("1", "2")] == ["waits for #1", "open"]


def test_declining_a_parent_says_what_else_was_declined(home: TestClient) -> None:
    response = post(home, "/review", decision="decline", id="1")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/review?notice=proposals-declined-waiting",
    )
    assert texts(page(home, response.headers["location"]), "notice") == [WAITING]
    assert open_count() == 0


def test_declining_with_nothing_waiting_keeps_the_old_notice(home: TestClient) -> None:
    response = post(home, "/review", decision="decline", id="2")
    assert response.headers["location"] == "/review?notice=proposals-declined"
    assert open_count() == 1
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_chains_more.py` (section core):

- `accepting_order` for `[3, 9, 1, 2]`, where 3 waits for 2, 2 for 1, and 9 stands alone, gives `[1, 2, 3, 9]`; for `[9, 2]` with 2 waiting for 1 (not in the list) it gives `[9, 2]`;
- a category proposal in a proposed category whose parent was declined by `decline_proposal` alone (not the cascade) is out of date, and `waits_for` gives None;
- a waiting category proposal whose transaction a person then decided is out of date, not waiting;
- `open_suggestions` leaves out a waiting proposal and keeps one in an existing category;
- `decline_proposals` with an id that is already declined is refused with today's message, and with a closed one in the middle of a list refuses the whole call;
- `propose_category` with the name of an **accepted** or **declined** new-category proposal (no open one, no category) is refused with `category not found`.

## Rules for this phase

- Every decline, cascaded or not, goes through `decline_proposal`, so History records each.
- Earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the check: `.venv/bin/python scripts/check.py --first core,mcp,cli,web`;
- the given test files above, 12 tests; at least N + 12 passed in all;
- `git diff --stat HEAD -- tests` lists only the seven files of the given diff;
- the coverage command: `.venv/bin/python -m coverage report --include="*/finances/db/repositories/chains.py,*/finances/db/repositories/proposals.py,*/finances/db/repositories/new_categories.py,*/finances/categorize/service.py,*/finances/analysis/review.py,*/finances/views/review.py,*/finances/cli/review.py,*/finances/web/routes/review.py,*/finances/web/render.py,*/finances/mcp_server/tools.py,*/finances/mcp_server/server.py" --fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 41c: proposals that wait for another (YYYY-MM-DD)`.
