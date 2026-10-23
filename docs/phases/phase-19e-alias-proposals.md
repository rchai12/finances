# Phase 19e: the agent proposes merchant aliases

## Goal

The agent can suggest that two merchant names are one merchant, and only suggest. After this phase:

- a new MCP tool, `propose_merchant_alias`, writes a proposal to merge the merchant of an **example** transaction (its cleaned name, so the agent cannot mistype it) into another merchant, with a one-line reason a person will read;
- a person decides it as every other proposal, in `fin review` and on the Review page: accepting it adds the alias through 28a's `add_alias`, so the audit trail shows the person's choice, and then the rules run once, as after a rule proposal;
- an alias proposal is **out of date** once 28a's alias rules would refuse it (for example, a person merged that merchant elsewhere since).

One migration adds the merchant to merge to `proposals`. Phase 19's last kind, a finding's status, waits for findings to have a status.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-19d-rule-proposals.md`, `docs/phases/phase-28a-merchant-aliases.md`
- `src/finances/domain/proposals.py`, `src/finances/domain/merchants.py` (`clean_merchant`, `check_alias`)
- `src/finances/db/repositories/proposals.py` (`propose_rule`, `proposal_out_of_date`, `accept_proposal`), `src/finances/db/repositories/aliases.py` (`alias_map`, `add_alias`)
- `src/finances/categorize/service.py` (`accept_proposals`), `src/finances/views/review.py`
- `src/finances/mcp_server/tools.py` (`_proposal_item`, `propose_rule`), `src/finances/mcp_server/server.py`

## Starting state

N is `3534` when Phase 28b is the last phase built. The newest migration is `0016`. The migration tests of 0013 to 0015 compare only the columns they made, so a new column breaks none of them.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0017_proposal_aliases.py` | new: given (R1) |
| `src/finances/db/orm.py` | `ProposalRow.source`, `to_proposal` (R1) |
| `src/finances/domain/proposals.py` | `ALIAS`, `Proposal.source`, `proposal_text` (R2) |
| `src/finances/db/repositories/proposals.py`, `src/finances/db/repositories/__init__.py` | `propose_merchant_alias`; out of date and accepting for an alias (R3 to R5) |
| `src/finances/categorize/service.py` | `accept_proposals` runs the rules after an alias too (R5) |
| `src/finances/views/review.py` | `proposed_text`, `accepted_text` for an alias (R6) |
| `src/finances/mcp_server/tools.py`, `server.py` | the tool; `"alias"` on every proposal item (R7) |
| `tests/support.py` and nine earlier test files | the given diff (R8) |
| `tests/integration/test_migration_0017.py`, `tests/integration/test_mcp_alias_proposals.py` | new: given |
| `tests/integration/test_alias_proposals.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Finding-status proposals; a proposal to remove an alias; an MCP tool that lists aliases.
- Any change to `fin aliases`, the aliases card, 28a's alias rules, or the Review page's template.
- Any tool that accepts, declines, or adds an alias itself.

## Dependencies

None new. One migration, given below.

## Design

```python
# src/finances/domain/proposals.py
ALIAS = "alias"
KINDS = (CATEGORY, TRANSFER, NOT_TRANSFER, RULE, ALIAS)

@dataclass(frozen=True)
class Proposal:
    ...                         # the fields of 19d, unchanged and in order
    source: str | None = None   # an alias proposal's merchant to merge; None for the other kinds

def proposal_text(proposal: Proposal) -> str: ...
# 19d's four texts, and for an alias "alias: ACME CAFE -> ACME COFFEE" (source -> value)

# src/finances/db/repositories/proposals.py
def propose_merchant_alias(
    session: Session, example_id: int, target: str, reason: str
) -> Proposal: ...

# src/finances/views/review.py
# proposed_text of an alias:  "merge ACME CAFE into ACME COFFEE"
# accepted_text of an alias:  "Accepted proposal 1: ACME CAFE merged into ACME COFFEE."

# src/finances/mcp_server/tools.py
def propose_merchant_alias(example_id: int, target: str, reason: str) -> dict[str, Any]: ...

# src/finances/mcp_server/server.py
PROPOSE_MERCHANT_ALIAS_DESCRIPTION = (
    "Propose merging the merchant of an example transaction (its cleaned name) into another "
    "merchant (target), with a one-line reason a person will read, so reports count them as "
    "one and a rule on either name matches both. It changes nothing until a person accepts "
    "it; then the rules run over every transaction. Refused when the two are the same, "
    "either is already merged, other merchants are merged into the example's, a person "
    "declined it, or another proposal for that merchant is open. No amounts."
)
```

## Requirements

### Storage

- **R1.** Add the given migration exactly. `ProposalRow` gains `source` (`String(MERCHANT_NAME_LIMIT)`, nullable) after `priority`; `to_proposal` reads it.
- **R2.** `domain/proposals.py` as designed. `proposal_text` of an alias is `alias: ` then the source, ` -> `, and the target (`value`).

### Proposing and deciding

- **R3.** `propose_merchant_alias` checks, in this order, and refuses with `ValueError`:
  1. the reason, with runs of white space made one space, is 1 to 200 characters (`a reason must be 1 to 200 characters`);
  2. the example transaction exists (`transaction not found`);
  3. `check_alias(clean_merchant(example.description), target, alias_map(session))` passes (its own messages); it gives the source and the target, normalized;
  4. no **declined** alias proposal has this source and this target (`a person declined this proposal already`);
  5. no **open** alias proposal has this source, whatever its target (`this merchant already has an open proposal`).

  It stores an open proposal with `target_id` the example, `value` the target, `source` the source, and `other_id`, `pattern`, `match`, `priority` None; stamps `created_at` with `_now()`; flushes; and returns it. Nothing else changes. It is re-exported from `finances.db.repositories`.
- **R4.** `proposal_out_of_date` of an alias proposal is true when `check_alias(source, value, alias_map(session))` refuses.
- **R5.** `accept_proposal` refuses an alias proposal out of date with `proposal N is out of date: the merchant aliases changed since`, then calls `add_alias(session, source, value)`, and marks and records the proposal as for the other kinds. `accept_proposals` runs `categorize` once after the last proposal when at least one accepted proposal is a **rule or an alias**.

### Showing and the tool

- **R6.** `proposed_text` and `accepted_text` of an alias as designed; the other kinds' texts are unchanged. `fin review` and the Review page need no other change.
- **R7.** Every proposal item of the tools gains `"alias"`: `{"source": ..., "target": ...}` for an alias proposal, null for the other kinds; `"category"` is null for an alias proposal. `propose_merchant_alias` returns `{"proposal": {...}}` through `writing()`, and a `ValueError` becomes a `ToolError` with its message. It is registered with `WRITES_PROPOSALS` and `PROPOSE_MERCHANT_ALIAS_DESCRIPTION` after `propose_rule`, and is in `_WRITES`. `mcp_server` imports from `finances.db.repositories` exactly the names the given diff lists.
- **R8.** Apply the given diff to `tests/support.py` and nine earlier test files: the tool lists, writers, cents exemptions, description table, and repository names gain `propose_merchant_alias`; both `KINDS` pins have five entries; four pinned proposal items gain `"alias": None`. No other earlier test changes.

## Given migration

`src/finances/db/migrations/versions/0017_proposal_aliases.py` (do not change)

```python
"""Add proposals.source: the merchant an alias proposal would merge."""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.add_column(sa.Column("source", sa.String(100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.drop_column("source")
```

## Given diff to earlier tests

```text
diff --git a/tests/integration/test_mcp_accounts.py b/tests/integration/test_mcp_accounts.py
index e98c16d..0d381c2 100644
--- a/tests/integration/test_mcp_accounts.py
+++ b/tests/integration/test_mcp_accounts.py
@@ -27,6 +27,7 @@ NO_AMOUNTS = (
     "list_rules",
     "find_merchants",
     "propose_category",
+    "propose_merchant_alias",
     "list_proposals",
     "list_advice",
     "propose_transfer",
diff --git a/tests/integration/test_mcp_more.py b/tests/integration/test_mcp_more.py
index 5581d53..3e0a9c1 100644
--- a/tests/integration/test_mcp_more.py
+++ b/tests/integration/test_mcp_more.py
@@ -35,6 +35,7 @@ from finances.mcp_server.server import (
     LOG_ADVICE_DESCRIPTION,
     MONTH_OVER_MONTH_DESCRIPTION,
     PROPOSE_CATEGORY_DESCRIPTION,
+    PROPOSE_MERCHANT_ALIAS_DESCRIPTION,
     PROPOSE_NOT_TRANSFER_DESCRIPTION,
     PROPOSE_RULE_DESCRIPTION,
     PROPOSE_TRANSFER_DESCRIPTION,
@@ -158,6 +159,7 @@ def test_each_tool_description_matches_the_table(tmp_settings: Settings) -> None
         "data_coverage": DATA_COVERAGE_DESCRIPTION,
         "find_merchants": FIND_MERCHANTS_DESCRIPTION,
         "propose_category": PROPOSE_CATEGORY_DESCRIPTION,
+        "propose_merchant_alias": PROPOSE_MERCHANT_ALIAS_DESCRIPTION,
         "propose_transfer": PROPOSE_TRANSFER_DESCRIPTION,
         "propose_not_transfer": PROPOSE_NOT_TRANSFER_DESCRIPTION,
         "propose_rule": PROPOSE_RULE_DESCRIPTION,
diff --git a/tests/integration/test_mcp_proposals.py b/tests/integration/test_mcp_proposals.py
index f5ffcc0..7053c85 100644
--- a/tests/integration/test_mcp_proposals.py
+++ b/tests/integration/test_mcp_proposals.py
@@ -32,6 +32,7 @@ FROM_REPOSITORIES = {
     "log_advice",
     "proposal_out_of_date",
     "propose_category",
+    "propose_merchant_alias",
     "propose_not_transfer",
     "propose_rule",
     "propose_transfer",
@@ -104,6 +105,7 @@ def test_a_proposal_and_its_listing(one: Settings) -> None:
         "in_id": None,
         "category": "Coffee & Dessert",
         "rule": None,
+        "alias": None,
         "reason": "a cafe",
         "status": "open",
         "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_rule_proposals.py b/tests/integration/test_mcp_rule_proposals.py
index 864e260..a7183ce 100644
--- a/tests/integration/test_mcp_rule_proposals.py
+++ b/tests/integration/test_mcp_rule_proposals.py
@@ -67,6 +67,7 @@ def test_the_agent_proposes_a_rule(card: Settings) -> None:
             "in_id": None,
             "category": "Dining",
             "rule": {"match": "equals", "pattern": "ACME COFFEE", "priority": 5},
+            "alias": None,
             "reason": "a cafe",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_transfer_proposals.py b/tests/integration/test_mcp_transfer_proposals.py
index 4a66ce4..50febe5 100644
--- a/tests/integration/test_mcp_transfer_proposals.py
+++ b/tests/integration/test_mcp_transfer_proposals.py
@@ -59,6 +59,7 @@ def test_the_agent_proposes_a_transfer(moved: Settings) -> None:
             "in_id": 2,
             "category": None,
             "rule": None,
+            "alias": None,
             "reason": "same day, same amount",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_transfer_proposals_more.py b/tests/integration/test_transfer_proposals_more.py
index e0254a3..293e204 100644
--- a/tests/integration/test_transfer_proposals_more.py
+++ b/tests/integration/test_transfer_proposals_more.py
@@ -36,6 +36,7 @@ PAIR = {
     "in_id": 2,
     "category": None,
     "rule": None,
+    "alias": None,
     "reason": "interest, not a transfer",
     "status": "open",
     "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/support.py b/tests/support.py
index e6bdf34..ab1574b 100644
--- a/tests/support.py
+++ b/tests/support.py
@@ -173,6 +173,7 @@ MCP_TOOLS = [
     "log_advice",
     "month_over_month",
     "propose_category",
+    "propose_merchant_alias",
     "propose_not_transfer",
     "propose_rule",
     "propose_transfer",
@@ -182,5 +183,6 @@ MCP_WRITERS = (
     "propose_transfer",
     "propose_not_transfer",
     "propose_rule",
+    "propose_merchant_alias",
     "log_advice",
 )
diff --git a/tests/unit/test_proposal_rules.py b/tests/unit/test_proposal_rules.py
index 43da418..40f32f6 100644
--- a/tests/unit/test_proposal_rules.py
+++ b/tests/unit/test_proposal_rules.py
@@ -17,7 +17,10 @@ from finances.domain.text import ADVICE_TEXT_LIMIT, PROPOSAL_TEXT_LIMIT
 
 
 def test_the_lists_and_limits() -> None:
-    assert (CATEGORY, KINDS) == ("category", ("category", "transfer", "not_transfer", "rule"))
+    assert (CATEGORY, KINDS) == (
+        "category",
+        ("category", "transfer", "not_transfer", "rule", "alias"),
+    )
     assert (OPEN, ACCEPTED, DECLINED, STATUSES) == (
         "open",
         "accepted",
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index d86899a..0a74ec4 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -95,6 +95,7 @@ HOMES = {
         "log_advice",
         "proposal_out_of_date",
         "propose_category",
+        "propose_merchant_alias",
         "propose_not_transfer",
         "propose_rule",
         "propose_transfer",
@@ -150,7 +151,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 104
+    assert len(expected) == 105
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
diff --git a/tests/unit/test_rule_proposal_rules.py b/tests/unit/test_rule_proposal_rules.py
index 00e1683..ca6f57f 100644
--- a/tests/unit/test_rule_proposal_rules.py
+++ b/tests/unit/test_rule_proposal_rules.py
@@ -17,7 +17,7 @@ MADE = datetime(2026, 5, 25, tzinfo=UTC)
 
 def test_the_kinds() -> None:
     assert RULE == "rule"
-    assert KINDS == ("category", "transfer", "not_transfer", "rule")
+    assert KINDS == ("category", "transfer", "not_transfer", "rule", "alias")
 
 
 @pytest.mark.parametrize(
```

## Given tests

5 tests in two files. Do not change them.

`tests/integration/test_migration_0017.py`

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
ADDED = ("source", "VARCHAR(100)", True)


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


def test_0017_follows_0016() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0017")
    assert script.down_revision == "0016"


def test_the_source_column_comes_and_goes(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = make_config(url)
    command.upgrade(config, "0017")
    found = columns(url)
    assert found[-1] == ADDED
    orm = [(c.name, str(c.type), c.nullable) for c in ProposalRow.__table__.columns]
    assert orm[: len(found)] == found
    command.downgrade(config, "0016")
    assert columns(url)[-1] == ("priority", "INTEGER", True)
    command.upgrade(config, "0017")
    assert columns(url)[-1] == ADDED
```

`tests/integration/test_mcp_alias_proposals.py`

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
from finances.db.repositories import create_account, create_rule
from finances.mcp_server.server import build_server
from tests.support import run, table_rows

PROPOSED = {"example_id": 1, "target": "acme   coffee", "reason": "the same shop"}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Two card purchases: 1 cleans to ACME CAFE, 2 to ACME COFFEE; a rule puts ACME COFFEE in
    Dining, so 2 is categorized and 1 is not."""
    monkeypatch.setattr(
        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-450, "SQ *ACME CAFE 12345"), (-500, "ACME COFFEE")), start=1
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
        create_rule(session, "ACME COFFEE", "Dining")
        categorize(session)
    engine.dispose()
    return tmp_settings


def test_the_agent_proposes_an_alias(card: Settings) -> None:
    made = call("propose_merchant_alias", PROPOSED)
    assert made.structured_content == {
        "proposal": {
            "id": 1,
            "kind": "alias",
            "transaction_id": 1,
            "in_id": None,
            "category": None,
            "rule": None,
            "alias": {"source": "ACME CAFE", "target": "ACME COFFEE"},
            "reason": "the same shop",
            "status": "open",
            "created_at": "2026-05-25T12:00:00+00:00",
            "decided_at": None,
            "out_of_date": False,
        }
    }


def test_a_refused_alias(card: Settings) -> None:
    refused = call("propose_merchant_alias", {**PROPOSED, "target": "Acme Cafe"})
    assert [item.text for item in refused.content] == [
        "Error executing tool propose_merchant_alias: a merchant cannot be merged into itself"
    ]


def test_a_person_accepts_it_in_the_terminal(card: Settings) -> None:
    call("propose_merchant_alias", PROPOSED)
    rows = table_rows(run("review", "list").stdout)
    assert rows[1] == [
        "1",
        "2026-05-01",
        "Test Card",
        "SQ *ACME CAFE 12345",
        "-$4.50",
        "",
        "merge ACME CAFE into ACME COFFEE",
        "the same shop",
        "open",
    ]
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: ACME CAFE merged into ACME COFFEE.\n"
        "Categorized 2 transactions: 1 changed, 0 without a category.\n",
    )
    assert table_rows(run("aliases", "list").stdout) == [
        ["From", "To"],
        ["ACME CAFE", "ACME COFFEE"],
    ]
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_alias_proposals.py`, on purchases `SQ *ACME CAFE 12345` (1), `ACME COFFEE` (2), and `ACME CAFE #2` (3, which also cleans to `ACME CAFE`), with a rule `contains "ACME COFFEE" -> Dining` already run, so only 2 has a category:

- a stored proposal compared whole (target ` acme   coffee ` stored as `ACME COFFEE`, source `ACME CAFE`), with no alias added;
- a blank reason with a target the same as the source gives the reason's message (the order of checks 1 and 3); example 99 gives `transaction not found`;
- with the alias `ACME CAFE -> BAZ CAFE` added by a person, proposing `ACME CAFE -> ACME COFFEE` is refused with `this merchant is already merged into another` (the check reads the stored aliases);
- after declining `ACME CAFE -> ACME COFFEE`, the same is refused and `ACME CAFE -> BAZ CAFE` is stored;
- with `ACME CAFE -> ACME COFFEE` open, example 3 into `BAZ CAFE` is refused: the open check keys on the source only;
- after a person adds `ACME CAFE -> BAZ CAFE`, the open proposal is out of date and accepting it is refused with R5's message, adding nothing; after a person adds `QUX CAFE -> BAZ CAFE` instead, it is not out of date;
- accepting an alias proposal alone gives `Accepted([the accepted proposal], CategorizeResult(3, 2, 0))` and records `proposal_accepted` then `alias_added`, both by `person`;
- on the Review page, accepting it sets purchase 1 to Dining;
- `list_proposals` shows `"alias"` for an alias proposal beside `null` for a category one.

## Rules for this phase

- Accepting goes through `add_alias` and `categorize` only, so 28a's rules and the audit trail hold.
- The tool writes nothing but a proposal; the agent cannot accept, decline, or add an alias.
- Merchant names come from statements and the feed: no message echoes one; every message here is a constant.
- Keep `repositories/proposals.py` under 400 lines (`tests/unit/test_repositories_split.py`).

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 5 tests; at least N + 5 passed in all;
- `git diff --stat HEAD -- tests` lists only the ten files of the given diff;
- `git grep -n "add_alias" -- src/finances/mcp_server` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.proposals --cov=finances.db.repositories --cov=finances.categorize.service --cov=finances.views.review --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 19e: the agent proposes merchant aliases (YYYY-MM-DD)`.
