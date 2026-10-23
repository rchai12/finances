# Phase 19c: the agent proposes transfers

## Goal

The agent can suggest how money moved between accounts, and only suggest. After this phase:

- two new MCP tools write proposals: `propose_transfer` (this money out and that money in are one transfer) and `propose_not_transfer` (they look like one but are not), each with a one-line reason a person will read;
- a person decides them as they decide category proposals, in `fin review` and on the Review page (19b): accepting a transfer proposal pairs the two as a **confirmed** transfer, and accepting a not-a-transfer proposal records that the two are not a transfer, through the same functions `fin transfers` uses, so each change is the person's choice in the audit trail;
- a pair proposal is **out of date** once either transaction is gone or in a pair, or a person said the two are not a transfer.

One migration adds the second transaction's id to `proposals`. Rule proposals are Phase 19d.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-19a-proposals-and-advice.md`, `docs/phases/phase-11c-transfers.md`
- `src/finances/domain/proposals.py`, `src/finances/db/repositories/proposals.py`, `src/finances/db/repositories/transfers.py` (`_check_transfer`, `create_transfer_pair`, `reject_transfer`, `list_transfer_rejections`), `src/finances/analysis/review.py`, `src/finances/views/review.py`, `src/finances/mcp_server/tools.py` (`_proposal_item`, `propose_category`), `src/finances/mcp_server/server.py`

## Starting state

N is `3417` when Phase 19b is the last phase built. The newest migration is `0013`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0014_proposal_pairs.py` | new: given (R1) |
| `src/finances/db/orm.py` | `ProposalRow.other_id`, `to_proposal` (R1) |
| `src/finances/domain/proposals.py` | two kinds, `Proposal.other_id`, `pair_out_of_date`, `proposal_text` (R2) |
| `src/finances/db/repositories/proposals.py`, `src/finances/db/repositories/__init__.py` | two functions; out of date and accepting by kind (R3 to R5) |
| `src/finances/analysis/review.py` | `open_suggestions` takes category proposals only (R6) |
| `src/finances/views/review.py` | `proposed_text`; `accepted_text` by kind (R7) |
| `src/finances/mcp_server/tools.py`, `server.py` | two tools; `in_id` on every proposal (R8, R9) |
| `tests/support.py` and ten earlier test files | the given diff (R10) |
| `tests/unit/test_pair_proposal_rules.py`, `tests/integration/test_migration_0014.py`, `tests/integration/test_transfer_proposals.py`, `tests/integration/test_mcp_transfer_proposals.py` | new: given |
| `tests/integration/test_transfer_proposals_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Rule proposals (19d); merchant alias and finding-status proposals (after Phase 28).
- A proposal to unpair a pair already made; proposals in the Suggested column of Categories; any change to `fin transfers`, the Transfers page, or the Review page's template.
- Any tool that accepts, declines, or makes a pair itself.

## Dependencies

None new. One migration, given below.

## Design

```python
# src/finances/domain/proposals.py
CATEGORY = "category"
TRANSFER = "transfer"
NOT_TRANSFER = "not_transfer"
KINDS = (CATEGORY, TRANSFER, NOT_TRANSFER)

@dataclass(frozen=True)
class Proposal:
    ...                         # the fields of 19a, unchanged and in order
    other_id: int | None = None  # the money in, for a pair proposal; None for a category

def pair_out_of_date(*, exists: bool, paired: bool, rejected: bool) -> bool: ...
def proposal_text(proposal: Proposal) -> str: ...
# "transaction 1: Dining" | "1 -> 2: a transfer" | "1 -> 2: not a transfer"

# src/finances/db/repositories/proposals.py
def propose_transfer(session: Session, out_id: int, in_id: int, reason: str) -> Proposal: ...
def propose_not_transfer(session: Session, out_id: int, in_id: int, reason: str) -> Proposal: ...

# src/finances/views/review.py
def proposed_text(proposal: Proposal) -> str: ...
# "Dining" | "a transfer with transaction 2" | "not a transfer with transaction 2"

# src/finances/mcp_server/tools.py
def propose_transfer(out_id: int, in_id: int, reason: str) -> dict[str, Any]: ...
def propose_not_transfer(out_id: int, in_id: int, reason: str) -> dict[str, Any]: ...

# src/finances/mcp_server/server.py
PROPOSE_TRANSFER_DESCRIPTION = (
    "Propose that money out (out_id) and money in (in_id) on another account, of the same "
    "amount, are one transfer, with a one-line reason a person will read. It changes nothing "
    "until a person accepts it. Refused when either is already in a pair, a person said they "
    "are not a transfer, declined this proposal, or another proposal for the two is open."
)
PROPOSE_NOT_TRANSFER_DESCRIPTION = (
    "Propose that money out (out_id) and money in (in_id) are not one transfer though they "
    "look like one, with a one-line reason. It changes nothing until a person accepts it; the "
    "same refusals as propose_transfer apply."
)
```

## Requirements

### Storage and rules

- **R1.** Add the given migration exactly. `ProposalRow` gains `other_id` (Integer, nullable) as its last column, and `to_proposal` reads it.
- **R2.** `domain/proposals.py` as designed: `pair_out_of_date` is true when either transaction no longer exists, either is in a transfer pair, or the two were said not to be a transfer. `proposal_text` gives `transaction N: X` for a category proposal, `A -> B: a transfer` and `A -> B: not a transfer` for the two new kinds.

### Proposing and deciding

- **R3.** `propose_transfer` and `propose_not_transfer` check, in this order, and refuse with `ValueError`: the reason, with runs of white space made one space, is 1 to 200 characters (`a reason must be 1 to 200 characters`); the two can be one transfer, by `_check_transfer` (its own messages); neither is in a pair (`a person or the rules already paired one of these transactions`); the two were not said to be no transfer (`a person said these two are not a transfer`); a person has not declined a proposal of **this kind** for this out and in (`a person declined this proposal already`); no proposal of either kind for the two is open (`these two already have an open proposal`). Each stores an open proposal with `target_id` the money out, `other_id` the money in, and `value` `""`, stamps `created_at` with `_now()`, flushes, and returns it. Nothing else changes. Both are re-exported from `finances.db.repositories`.
- **R4.** `proposal_out_of_date` applies `pair_out_of_date` to a pair proposal's two stored transactions, and 19a's rule to a category proposal.
- **R5.** `accept_proposal` refuses a pair proposal out of date with `proposal N is out of date: the transactions were decided since` (a category proposal keeps 19a's message). Then it does what the kind says: a transfer by `create_transfer_pair(session, out, in, CONFIRMED)`, not a transfer by `reject_transfer(session, out, in)`, a category by `set_category_by_hand` as before. It then marks and records the proposal as 19a does. `decline_proposal` is unchanged.

### Reading and the tools

- **R6.** `open_suggestions` maps only **category** proposals.
- **R7.** The review table's Proposed column is `proposed_text(proposal)`. `accepted_text` of a pair proposal is `Accepted proposal N: transactions A and B are a transfer.` or `... are not a transfer.`; a category proposal's line is unchanged. `fin review` and the Review page need no other change.
- **R8.** Every proposal item of the tools gains `"in_id"` after `"transaction_id"` (the money in, null for a category proposal), and its `"category"` is null for a pair proposal. The two new tools return `{"proposal": {...}}` through `writing()`; a `ValueError` becomes a `ToolError` with its message.
- **R9.** Both tools are registered with `WRITES_PROPOSALS` and the descriptions above, after `propose_category`. `mcp_server` imports from `finances.db.repositories` exactly the names the given diff lists.
- **R10.** Apply the given diff to `tests/support.py` and ten earlier test files: the tool lists move to `MCP_TOOLS` and `MCP_WRITERS` in `tests/support.py`, the description table and the cents exemptions gain the two tools, the imported repository names gain two, `KINDS` has three entries, and the 0013 migration test compares the columns it made. No other earlier test changes.

## Given migration

`src/finances/db/migrations/versions/0014_proposal_pairs.py` (do not change)

```python
"""Add proposals.other_id: the inflow of a proposed transfer (or of one said not to be)."""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proposals", sa.Column("other_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.drop_column("other_id")
```

## Given diff to earlier tests

```text
diff --git a/tests/integration/test_mcp_accounts.py b/tests/integration/test_mcp_accounts.py
index 98a9d55..cd63053 100644
--- a/tests/integration/test_mcp_accounts.py
+++ b/tests/integration/test_mcp_accounts.py
@@ -19,6 +19,7 @@ from finances.db.repositories import (
 from finances.domain.models import DataSource
 from finances.mcp_server.access import reading
 from finances.mcp_server.server import INSTRUCTIONS, build_server
+from tests.support import MCP_TOOLS, MCP_WRITERS
 
 NO_AMOUNTS = (
     "list_accounts",
@@ -28,6 +29,8 @@ NO_AMOUNTS = (
     "propose_category",
     "list_proposals",
     "list_advice",
+    "propose_transfer",
+    "propose_not_transfer",
 )
 READ_ONLY = {
     "read_only_hint": True,
@@ -80,32 +83,9 @@ def test_the_server_and_its_tools(tmp_settings: Settings) -> None:
 
     name, instructions, tools = anyio.run(go)
     assert (name, instructions) == ("finances", INSTRUCTIONS)
-    assert sorted(tool.name for tool in tools) == [
-        "data_coverage",
-        "find_merchants",
-        "get_balances",
-        "get_budgets",
-        "get_forecast",
-        "get_insights",
-        "get_net_worth",
-        "get_recurring",
-        "get_spending",
-        "get_upcoming",
-        "list_accounts",
-        "list_advice",
-        "list_categories",
-        "list_proposals",
-        "list_rules",
-        "list_transactions",
-        "list_transfer_suggestions",
-        "list_transfers",
-        "list_uncategorized",
-        "log_advice",
-        "month_over_month",
-        "propose_category",
-    ]
+    assert sorted(tool.name for tool in tools) == MCP_TOOLS
     for tool in tools:
-        if tool.name not in ("propose_category", "log_advice"):
+        if tool.name not in MCP_WRITERS:
             assert tool.annotations.model_dump(include=set(READ_ONLY)) == READ_ONLY, tool.name
         assert "cents" in tool.description or tool.name in NO_AMOUNTS, tool.name
 
diff --git a/tests/integration/test_mcp_coverage.py b/tests/integration/test_mcp_coverage.py
index 30f9a9e..be4a70d 100644
--- a/tests/integration/test_mcp_coverage.py
+++ b/tests/integration/test_mcp_coverage.py
@@ -17,31 +17,9 @@ from finances.db.repositories import (
 )
 from finances.domain.models import DEFAULT_LINK
 from finances.mcp_server.server import build_server
+from tests.support import MCP_TOOLS, MCP_WRITERS
 
-TOOLS = [
-    "data_coverage",
-    "find_merchants",
-    "get_balances",
-    "get_budgets",
-    "get_forecast",
-    "get_insights",
-    "get_net_worth",
-    "get_recurring",
-    "get_spending",
-    "get_upcoming",
-    "list_accounts",
-    "list_advice",
-    "list_categories",
-    "list_proposals",
-    "list_rules",
-    "list_transactions",
-    "list_transfer_suggestions",
-    "list_transfers",
-    "list_uncategorized",
-    "log_advice",
-    "month_over_month",
-    "propose_category",
-]
+TOOLS = MCP_TOOLS
 
 
 def call(name: str, arguments: dict | None = None):
@@ -128,11 +106,7 @@ def test_eighteen_read_only_tools(tmp_settings: Settings) -> None:
 
     found = anyio.run(go)
     assert sorted(tool.name for tool in found) == TOOLS
-    assert all(
-        tool.annotations.read_only_hint
-        for tool in found
-        if tool.name not in ("propose_category", "log_advice")
-    )
+    assert all(tool.annotations.read_only_hint for tool in found if tool.name not in MCP_WRITERS)
 
 
 def test_data_coverage(data: Settings) -> None:
diff --git a/tests/integration/test_mcp_more.py b/tests/integration/test_mcp_more.py
index a89a368..21d08ea 100644
--- a/tests/integration/test_mcp_more.py
+++ b/tests/integration/test_mcp_more.py
@@ -35,6 +35,8 @@ from finances.mcp_server.server import (
     LOG_ADVICE_DESCRIPTION,
     MONTH_OVER_MONTH_DESCRIPTION,
     PROPOSE_CATEGORY_DESCRIPTION,
+    PROPOSE_NOT_TRANSFER_DESCRIPTION,
+    PROPOSE_TRANSFER_DESCRIPTION,
     build_server,
 )
 from tests.support import run
@@ -155,6 +157,8 @@ def test_each_tool_description_matches_the_table(tmp_settings: Settings) -> None
         "data_coverage": DATA_COVERAGE_DESCRIPTION,
         "find_merchants": FIND_MERCHANTS_DESCRIPTION,
         "propose_category": PROPOSE_CATEGORY_DESCRIPTION,
+        "propose_transfer": PROPOSE_TRANSFER_DESCRIPTION,
+        "propose_not_transfer": PROPOSE_NOT_TRANSFER_DESCRIPTION,
         "list_proposals": LIST_PROPOSALS_DESCRIPTION,
         "log_advice": LOG_ADVICE_DESCRIPTION,
         "list_advice": LIST_ADVICE_DESCRIPTION,
diff --git a/tests/integration/test_mcp_outlook.py b/tests/integration/test_mcp_outlook.py
index 03205a0..00b27ad 100644
--- a/tests/integration/test_mcp_outlook.py
+++ b/tests/integration/test_mcp_outlook.py
@@ -19,31 +19,9 @@ from finances.db.repositories import (
 )
 from finances.domain.models import DataSource
 from finances.mcp_server.server import build_server
+from tests.support import MCP_TOOLS, MCP_WRITERS
 
-TOOLS = [
-    "data_coverage",
-    "find_merchants",
-    "get_balances",
-    "get_budgets",
-    "get_forecast",
-    "get_insights",
-    "get_net_worth",
-    "get_recurring",
-    "get_spending",
-    "get_upcoming",
-    "list_accounts",
-    "list_advice",
-    "list_categories",
-    "list_proposals",
-    "list_rules",
-    "list_transactions",
-    "list_transfer_suggestions",
-    "list_transfers",
-    "list_uncategorized",
-    "log_advice",
-    "month_over_month",
-    "propose_category",
-]
+TOOLS = MCP_TOOLS
 CHECKING = {
     "account": "Test Checking",
     "balance_cents": 30000,
@@ -219,11 +197,7 @@ def test_the_read_only_tools(tmp_settings: Settings) -> None:
 
     found = anyio.run(go)
     assert sorted(tool.name for tool in found) == TOOLS
-    assert all(
-        tool.annotations.read_only_hint
-        for tool in found
-        if tool.name not in ("propose_category", "log_advice")
-    )
+    assert all(tool.annotations.read_only_hint for tool in found if tool.name not in MCP_WRITERS)
 
 
 def test_recurring_charges_are_negative(ahead: Settings) -> None:
diff --git a/tests/integration/test_mcp_proposals.py b/tests/integration/test_mcp_proposals.py
index 85bfce2..e07ff2e 100644
--- a/tests/integration/test_mcp_proposals.py
+++ b/tests/integration/test_mcp_proposals.py
@@ -13,8 +13,9 @@ from finances.db.migrate import upgrade_to_head
 from finances.db.orm import TransactionRow
 from finances.db.repositories import create_account, list_category_assignments, set_category_by_hand
 from finances.mcp_server.server import build_server
+from tests.support import MCP_WRITERS
 
-WRITERS = {"propose_category", "log_advice"}
+WRITERS = set(MCP_WRITERS)
 FROM_REPOSITORIES = {
     "account_names",
     "count_uncategorized",
@@ -31,6 +32,8 @@ FROM_REPOSITORIES = {
     "log_advice",
     "proposal_out_of_date",
     "propose_category",
+    "propose_not_transfer",
+    "propose_transfer",
 }
 
 
@@ -97,6 +100,7 @@ def test_a_proposal_and_its_listing(one: Settings) -> None:
         "id": 1,
         "kind": "category",
         "transaction_id": 1,
+        "in_id": None,
         "category": "Coffee & Dessert",
         "reason": "a cafe",
         "status": "open",
diff --git a/tests/integration/test_mcp_queues.py b/tests/integration/test_mcp_queues.py
index 6747823..b9ef634 100644
--- a/tests/integration/test_mcp_queues.py
+++ b/tests/integration/test_mcp_queues.py
@@ -13,31 +13,9 @@ from finances.db.orm import TransactionRow
 from finances.db.repositories import create_account, create_rule, create_transfer_pair
 from finances.domain.models import CONFIRMED
 from finances.mcp_server.server import build_server
+from tests.support import MCP_TOOLS, MCP_WRITERS
 
-TOOLS = [
-    "data_coverage",
-    "find_merchants",
-    "get_balances",
-    "get_budgets",
-    "get_forecast",
-    "get_insights",
-    "get_net_worth",
-    "get_recurring",
-    "get_spending",
-    "get_upcoming",
-    "list_accounts",
-    "list_advice",
-    "list_categories",
-    "list_proposals",
-    "list_rules",
-    "list_transactions",
-    "list_transfer_suggestions",
-    "list_transfers",
-    "list_uncategorized",
-    "log_advice",
-    "month_over_month",
-    "propose_category",
-]
+TOOLS = MCP_TOOLS
 TO_SAVINGS = {
     "id": 4,
     "posted": "2026-05-05",
@@ -145,11 +123,7 @@ def test_the_read_only_tools(tmp_settings: Settings) -> None:
 
     found = anyio.run(go)
     assert sorted(tool.name for tool in found) == TOOLS
-    assert all(
-        tool.annotations.read_only_hint
-        for tool in found
-        if tool.name not in ("propose_category", "log_advice")
-    )
+    assert all(tool.annotations.read_only_hint for tool in found if tool.name not in MCP_WRITERS)
 
 
 def test_uncategorized_latest_first_with_the_total(queues: Settings) -> None:
diff --git a/tests/integration/test_mcp_spending.py b/tests/integration/test_mcp_spending.py
index 0c29785..83d7416 100644
--- a/tests/integration/test_mcp_spending.py
+++ b/tests/integration/test_mcp_spending.py
@@ -12,31 +12,9 @@ from finances.db.migrate import upgrade_to_head
 from finances.db.orm import TransactionRow
 from finances.db.repositories import create_account, create_person, create_rule, set_account_owner
 from finances.mcp_server.server import build_server
+from tests.support import MCP_TOOLS, MCP_WRITERS
 
-TOOLS = [
-    "data_coverage",
-    "find_merchants",
-    "get_balances",
-    "get_budgets",
-    "get_forecast",
-    "get_insights",
-    "get_net_worth",
-    "get_recurring",
-    "get_spending",
-    "get_upcoming",
-    "list_accounts",
-    "list_advice",
-    "list_categories",
-    "list_proposals",
-    "list_rules",
-    "list_transactions",
-    "list_transfer_suggestions",
-    "list_transfers",
-    "list_uncategorized",
-    "log_advice",
-    "month_over_month",
-    "propose_category",
-]
+TOOLS = MCP_TOOLS
 REFUND = {
     "id": 2,
     "day": "2026-05-10",
@@ -120,9 +98,7 @@ def test_the_read_only_tools(tmp_settings: Settings) -> None:
     found = anyio.run(go)
     assert sorted(tool.name for tool in found) == TOOLS
     for tool in found:
-        assert tool.annotations.read_only_hint is (
-            tool.name not in ("propose_category", "log_advice")
-        ), tool.name
+        assert tool.annotations.read_only_hint is (tool.name not in MCP_WRITERS), tool.name
 
 
 def test_every_transaction_latest_first(money: Settings) -> None:
diff --git a/tests/integration/test_migration_0013.py b/tests/integration/test_migration_0013.py
index 129be81..f83c285 100644
--- a/tests/integration/test_migration_0013.py
+++ b/tests/integration/test_migration_0013.py
@@ -70,7 +70,9 @@ def test_the_tables_and_their_row_classes(
     assert shown == columns
     assert (primary["name"], primary["constrained_columns"]) == (key, ["id"])
     assert extras == ([], [], [])
-    assert [(c.name, str(c.type), c.nullable) for c in row.__table__.columns] == columns
+    assert [(c.name, str(c.type), c.nullable) for c in row.__table__.columns][
+        : len(columns)
+    ] == columns
 
 
 def test_down_and_up_again(url: str) -> None:
diff --git a/tests/support.py b/tests/support.py
index 894eefd..e893bc9 100644
--- a/tests/support.py
+++ b/tests/support.py
@@ -147,3 +147,33 @@ def post(client: TestClient, path: str, **fields: str):
 def texts(found: Page, kind: str) -> list[str]:
     """The texts of the page's paragraphs of this class, in order."""
     return [text for name, text in found.paragraphs if name == kind]
+
+
+# Every MCP tool, and the ones that write (proposals and the advice log only).
+MCP_TOOLS = [
+    "data_coverage",
+    "find_merchants",
+    "get_balances",
+    "get_budgets",
+    "get_forecast",
+    "get_insights",
+    "get_net_worth",
+    "get_recurring",
+    "get_spending",
+    "get_upcoming",
+    "list_accounts",
+    "list_advice",
+    "list_categories",
+    "list_proposals",
+    "list_rules",
+    "list_transactions",
+    "list_transfer_suggestions",
+    "list_transfers",
+    "list_uncategorized",
+    "log_advice",
+    "month_over_month",
+    "propose_category",
+    "propose_not_transfer",
+    "propose_transfer",
+]
+MCP_WRITERS = ("propose_category", "propose_transfer", "propose_not_transfer", "log_advice")
diff --git a/tests/unit/test_proposal_rules.py b/tests/unit/test_proposal_rules.py
index 5c259c4..9664019 100644
--- a/tests/unit/test_proposal_rules.py
+++ b/tests/unit/test_proposal_rules.py
@@ -17,7 +17,7 @@ from finances.domain.text import ADVICE_TEXT_LIMIT, PROPOSAL_TEXT_LIMIT
 
 
 def test_the_lists_and_limits() -> None:
-    assert (CATEGORY, KINDS) == ("category", ("category",))
+    assert (CATEGORY, KINDS) == ("category", ("category", "transfer", "not_transfer"))
     assert (OPEN, ACCEPTED, DECLINED, STATUSES) == (
         "open",
         "accepted",
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index 8ebe3b0..a5ef476 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -89,6 +89,8 @@ HOMES = {
         "log_advice",
         "proposal_out_of_date",
         "propose_category",
+        "propose_not_transfer",
+        "propose_transfer",
     ],
     "people": [
         "PersonExistsError",
@@ -140,7 +142,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 96
+    assert len(expected) == 98
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
```

## Given tests

27 tests in four files. Do not change them.

`tests/unit/test_pair_proposal_rules.py`

```python
from datetime import UTC, datetime

import pytest

from finances.domain.proposals import (
    CATEGORY,
    NOT_TRANSFER,
    OPEN,
    TRANSFER,
    Proposal,
    pair_out_of_date,
    proposal_text,
)

MADE = datetime(2026, 5, 25, tzinfo=UTC)


def test_the_kinds() -> None:
    assert (TRANSFER, NOT_TRANSFER) == ("transfer", "not_transfer")


@pytest.mark.parametrize(
    ("exists", "paired", "rejected", "stale"),
    [
        (True, False, False, False),
        (False, False, False, True),
        (True, True, False, True),
        (True, False, True, True),
    ],
)
def test_a_pair_out_of_date(exists: bool, paired: bool, rejected: bool, stale: bool) -> None:
    assert pair_out_of_date(exists=exists, paired=paired, rejected=rejected) is stale


@pytest.mark.parametrize(
    ("kind", "other_id", "value", "text"),
    [
        (TRANSFER, 2, "", "1 -> 2: a transfer"),
        (NOT_TRANSFER, 3, "", "1 -> 3: not a transfer"),
        (CATEGORY, None, "Dining", "transaction 1: Dining"),
    ],
)
def test_the_text_of_each_kind(kind: str, other_id: int | None, value: str, text: str) -> None:
    found = Proposal(4, kind, 1, value, "why", OPEN, MADE, None, other_id)
    assert proposal_text(found) == text


def test_a_category_proposal_has_no_other_id() -> None:
    assert Proposal(1, CATEGORY, 1, "Dining", "why", OPEN, MADE, None).other_id is None
```

`tests/integration/test_migration_0014.py`

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


def test_0014_follows_0013() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0014")
    assert script.down_revision == "0013"


def test_other_id_comes_and_goes(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = make_config(url)
    command.upgrade(config, "0014")
    assert columns(url)[-1] == ("other_id", "INTEGER", True)
    assert [(c.name, str(c.type), c.nullable) for c in ProposalRow.__table__.columns] == columns(
        url
    )
    command.downgrade(config, "0013")
    assert "other_id" not in [name for name, _, _ in columns(url)]
    command.upgrade(config, "0014")
    assert columns(url)[-1] == ("other_id", "INTEGER", True)
```

`tests/integration/test_transfer_proposals.py`

```python
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.review import open_suggestions
from finances.categorize.transfers import pair_transfers
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    accept_proposal,
    create_account,
    create_transfer_pair,
    decline_proposal,
    find_transfer_pair,
    list_changes,
    list_transfer_rejections,
    propose_not_transfer,
    propose_transfer,
    reject_transfer,
)
from finances.domain.models import CONFIRMED
from finances.domain.proposals import Proposal

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """A move to savings with two possible inflows (1 out; 2 and 3 in), waiting for review; a
    card payment the rules pair (4 and 5); a coffee (6) and money in of another amount (7)."""
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Checking", "Test Bank", "checking")
        create_account(opened, "Test Savings", "Test Bank", "savings")
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        rows = [
            (1, date(2026, 5, 5), -2000, "TRANSFER TO SAVINGS"),
            (2, date(2026, 5, 5), 2000, "TRANSFER FROM CHECKING"),
            (2, date(2026, 5, 6), 2000, "TRANSFER FROM CHECKING"),
            (1, date(2026, 5, 10), -5000, "PAYMENT TO CARD"),
            (3, date(2026, 5, 11), 5000, "PAYMENT THANK YOU"),
            (1, date(2026, 5, 12), -700, "ACME COFFEE"),
            (2, date(2026, 5, 12), 900, "INTEREST PAID"),
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
        pair_transfers(opened)
        yield opened


def test_a_transfer_proposal_changes_nothing(session: Session) -> None:
    found = propose_transfer(session, 1, 2, "  same day,   same amount ")
    assert found == Proposal(1, "transfer", 1, "", "same day, same amount", "open", NOON, None, 2)
    assert find_transfer_pair(session, 1) is None


@pytest.mark.parametrize(
    ("out_id", "in_id", "reason", "message"),
    [
        (1, 2, "", "a reason must be 1 to 200 characters"),
        (1, 99, "why", "transaction not found"),
        (1, 6, "why", "a transfer goes from one account to another"),
        (6, 7, "why", "a transfer pairs money out with the same amount in"),
        (4, 5, "why", "a person or the rules already paired one of these transactions"),
    ],
)
def test_refused_pair_proposals(
    session: Session, out_id: int, in_id: int, reason: str, message: str
) -> None:
    for propose in (propose_transfer, propose_not_transfer):
        with pytest.raises(ValueError, match=message):
            propose(session, out_id, in_id, reason)


def test_a_pair_said_not_to_be_a_transfer(session: Session) -> None:
    reject_transfer(session, 1, 3)
    with pytest.raises(ValueError, match="a person said these two are not a transfer"):
        propose_transfer(session, 1, 3, "why")


def test_one_open_proposal_per_pair(session: Session) -> None:
    propose_transfer(session, 1, 2, "why")
    with pytest.raises(ValueError, match="these two already have an open proposal"):
        propose_not_transfer(session, 1, 2, "why not")


def test_declined_then_only_the_other_kind(session: Session) -> None:
    propose_transfer(session, 1, 2, "why")
    decline_proposal(session, 1)
    with pytest.raises(ValueError, match="a person declined this proposal already"):
        propose_transfer(session, 1, 2, "really")
    assert propose_not_transfer(session, 1, 2, "then not").kind == "not_transfer"


def test_accepting_a_transfer(session: Session) -> None:
    propose_transfer(session, 1, 2, "same day")
    found = accept_proposal(session, 1)
    assert found.status == "accepted"
    pair = find_transfer_pair(session, 1)
    assert (pair.out_transaction_id, pair.in_transaction_id, pair.status) == (1, 2, "confirmed")
    assert [(c.who, c.action, c.kind, c.before, c.after) for c in list_changes(session)[:2]] == [
        ("person", "proposal_accepted", "proposal", None, "1 -> 2: a transfer"),
        ("person", "transfer_confirmed", "transfer", None, "1 -> 2"),
    ]


def test_accepting_not_a_transfer(session: Session) -> None:
    propose_not_transfer(session, 1, 3, "the next day is interest")
    accept_proposal(session, 1)
    assert (1, 3) in list_transfer_rejections(session)
    assert find_transfer_pair(session, 1) is None
    assert [c.action for c in list_changes(session)[:2]] == [
        "proposal_accepted",
        "transfer_rejected",
    ]


@pytest.mark.parametrize("decided", ["paired", "rejected"])
def test_an_out_of_date_pair_proposal(session: Session, decided: str) -> None:
    propose_transfer(session, 1, 2, "same day")
    if decided == "paired":
        create_transfer_pair(session, 1, 3, CONFIRMED)
    else:
        reject_transfer(session, 1, 2)
    with pytest.raises(
        ValueError, match="proposal 1 is out of date: the transactions were decided since"
    ):
        accept_proposal(session, 1)


def test_suggestions_are_categories_only(session: Session) -> None:
    propose_transfer(session, 1, 2, "same day")
    assert open_suggestions(session) == {}
```

`tests/integration/test_mcp_transfer_proposals.py`

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


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def moved(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """$20.00 out of checking (1) and into savings (2) the same day."""
    monkeypatch.setattr(
        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Checking", "Test Bank", "checking")
        create_account(session, "Test Savings", "Test Bank", "savings")
        for number, (account, cents, description) in enumerate(
            ((1, -2000, "TRANSFER TO SAVINGS"), (2, 2000, "TRANSFER FROM CHECKING")), start=1
        ):
            session.add(
                TransactionRow(
                    account_id=account,
                    posted_date=date(2026, 5, 5),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    return tmp_settings


def test_the_agent_proposes_a_transfer(moved: Settings) -> None:
    made = call("propose_transfer", {"out_id": 1, "in_id": 2, "reason": "same day, same amount"})
    assert made.structured_content == {
        "proposal": {
            "id": 1,
            "kind": "transfer",
            "transaction_id": 1,
            "in_id": 2,
            "category": None,
            "reason": "same day, same amount",
            "status": "open",
            "created_at": "2026-05-25T12:00:00+00:00",
            "decided_at": None,
            "out_of_date": False,
        }
    }
    refused = call("propose_not_transfer", {"out_id": 1, "in_id": 2, "reason": "why not"})
    assert [item.text for item in refused.content] == [
        "Error executing tool propose_not_transfer: these two already have an open proposal"
    ]


def test_a_person_reviews_it_in_the_terminal(moved: Settings) -> None:
    call("propose_transfer", {"out_id": 1, "in_id": 2, "reason": "same day, same amount"})
    rows = table_rows(run("review", "list").stdout)
    assert rows[1] == [
        "1",
        "2026-05-05",
        "Test Checking",
        "TRANSFER TO SAVINGS",
        "-$20.00",
        "",
        "a transfer with transaction 2",
        "same day, same amount",
        "open",
    ]
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: transactions 1 and 2 are a transfer.\n",
    )
```

## Tests to write

`tests/integration/test_transfer_proposals_more.py`:

- the `propose_not_transfer` tool's output, and `list_proposals` showing `in_id` for a pair and null for a category;
- `fin review list` and `fin review accept` for a not-a-transfer proposal (its Proposed text and its line);
- a pair proposal out of date when one of its transactions is deleted, and shown `out of date` in `fin review list`;
- accepting a transfer proposal on the Review page pairs the two, and the transaction's page shows the pair;
- declining a not-a-transfer proposal changes nothing, and the same kind cannot be proposed again;
- a transfer proposal whose two transactions the person pairs another way first cannot be accepted, and nothing changes.

## Rules for this phase

- Deciding goes through `create_transfer_pair`, `reject_transfer`, and `set_category_by_hand` only, so the audit trail and every rule of 11c hold.
- The tools write nothing but proposals; the agent cannot accept or decline.
- Keep `repositories/proposals.py` under the size limit of `scripts/check.py`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 27 tests; at least N + 27 passed in all;
- `git diff --stat HEAD -- tests` lists only the eleven files of the given diff;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.proposals --cov=finances.db.repositories --cov=finances.analysis.review --cov=finances.views.review --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 19c: the agent proposes transfers (YYYY-MM-DD)`.
