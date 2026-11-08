# Phase 45b: the agent proposes a finding's status

## Goal

The second part of Phase 45, and the last tool Phase 19 planned. With the owner's choices (2026-11-08):

- `get_insights` keeps `findings` as the open ones and adds `set_aside`: the findings a person handled or ignored, each with its status, so an agent adding up savings cannot count one a person already dealt with;
- a new `propose_finding_status` lets the agent propose marking an open finding handled (that month) or ignored (every month). Like every proposal it changes nothing until a person accepts it in `fin review` or on the Review page, and accepting stores the status exactly as `fin findings handle` and `ignore` do, History included;
- the proposal is out of date when the finding has a status by the time a person looks at it; a finding that no longer shows that month does not put it out of date (accepting then stores a status that matches nothing, which is harmless);
- a declined proposal is not made again, and a finding has at most one open proposal, as for every other kind.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-45a-findings-handled-or-ignored.md`, `docs/phases/phase-44b-category-changes.md` (the shape to follow), `src/finances/db/repositories/findings.py`, `src/finances/db/repositories/category_changes.py`, `src/finances/db/repositories/proposals.py` (`proposal_out_of_date`, `accept_proposal`), `src/finances/domain/findings.py`, `src/finances/domain/proposals.py`, `src/finances/analysis/insights.py` (`find_finding`), `src/finances/analysis/review.py`, `src/finances/views/review.py`, `src/finances/mcp_server/tools.py` (`get_insights`, `_proposal_item`, `_month_start`), `src/finances/mcp_server/server.py`

## Starting state

N is `4268` when Phase 45a is the last phase built. **Sections: migrations, core, mcp, cli, web.** The newest migration is `0025`. `repositories/proposals.py` is at 398 of the 400 lines the split test allows: the new kind's checks, out of date, and accepting live in a new `repositories/finding_proposals.py`, and you may move a private helper out of `proposals.py` to fit the dispatch lines (record it). `orm.py` names the widths 100, 200, and 500 by their `finances.domain.text` constants (`tests/unit/test_text.py`).

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0026_proposal_findings.py` | new: given (R1) |
| `src/finances/db/orm.py`, `src/finances/domain/proposals.py` | three columns on `ProposalRow`, three fields on `Proposal`, `to_proposal`; `FINDING_STATUS`, `KINDS`, `proposal_text` (R1, R2) |
| `src/finances/domain/findings.py` | `status_for` (R2) |
| `src/finances/db/repositories/finding_proposals.py` (new), `__init__.py`, `findings.py` | `propose_finding_status`, its out of date and accepting (R3, R4) |
| `src/finances/db/repositories/proposals.py` | dispatch to the new module (R4) |
| `src/finances/analysis/review.py`, `src/finances/views/review.py` | the rows and texts (R5) |
| `src/finances/mcp_server/tools.py`, `server.py` | `set_aside`; the tool; `"finding"` on every item; two descriptions (R6) |
| `tests/support.py` and twelve earlier test files | the given diff (R7) |
| `tests/integration/test_migration_0026.py`, `tests/integration/test_mcp_finding_proposals.py` | new: given |
| `tests/integration/test_finding_proposals_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- The agent proposing to reopen a finding; the proposal shown beside the finding on the Insights page; out of date when the finding no longer shows; a link from History to a finding; a chain through a finding proposal.

## Dependencies

None new.

## Design

```python
# src/finances/domain/proposals.py
FINDING_STATUS = "finding_status"
KINDS = (..., CATEGORY_RENAME, CATEGORY_DELETE, FINDING_STATUS)
# Proposal gains, last:
    finding_type: str | None = None
    finding_subject: str | None = None
    finding_month: date | None = None

# src/finances/domain/findings.py
def status_for(
    type: str, subject: str, month: date, statuses: Iterable[FindingStatus]
) -> str | None: ...
# The rule status_of applies, for a finding named by its parts; status_of calls it.

# src/finances/db/repositories/finding_proposals.py
def propose_finding_status(
    session: Session, finding: Finding, status: str, reason: str
) -> Proposal: ...
```

**Checks** of `propose_finding_status`, in this order (all `ValueError`):

| Check | Refusal |
|---|---|
| the reason, whitespace collapsed, is 1 to 200 characters | `a reason must be 1 to 200 characters` |
| status in `FINDING_STATUSES` | `status must be one of: handled, ignored` |
| `status_of` the finding is None | `this finding is already handled` or `ignored` |
| no declined `FINDING_STATUS` proposal with the same type, subject (ignoring case), and status, and for `handled` the same month | `a person declined this proposal already` |
| no open `FINDING_STATUS` proposal with the same type, subject (ignoring case), and month | `this finding already has an open proposal` |

Stored: kind `FINDING_STATUS`; `target_id` 0; `value` the status; the reason; `finding_type`, `finding_subject` (the finding's own spelling, cut with `fit` to 100), and `finding_month` (the finding's month, for either status); every other column None. `created_at` comes from a `_now()` of `finding_proposals.py`'s own.

**Out of date** when `status_for(finding_type, finding_subject, finding_month, list_finding_statuses(session))` is not None. Accepting one out of date is refused with `proposal N is out of date: a person set this finding's status since`.

**Accepting** stores the status as `set_finding_status` does: the same row (month None for ignored) and the same `finding_handled` or `finding_ignored` History record, through a private helper of `repositories/findings.py` that both use. Then `proposal_accepted` is recorded as for every kind, so History shows the status first and the acceptance after it.

| Text | Handled: spike, Dining, 2026-05 | Ignored: interest, 2026-05 |
|---|---|---|
| `proposal_text` (History) | `finding spike for Dining in 2026-05: handled` | `finding interest in every month: ignored` |
| review: Now / Proposed | `spike for Dining in 2026-05` / `mark handled` | `interest in 2026-05` / `ignore in every month` |
| `accepted_text` | `Accepted proposal N: spike for Dining in 2026-05 is handled.` | `Accepted proposal N: interest in every month is ignored.` |

`proposal_text` and `accepted_text` use `finding_text` with the month for handled and None for ignored; the review's Now uses it with the stored month. A finding proposal has no transaction: `review_items` gives it `transaction` None, `account` None, and `current` the Now text.

**MCP.** `get_insights` gains `"set_aside"`, last: one item per `closed` finding, in its order, `{"type", "severity", "subject", "savings_cents", "detail", "status"}`, `subject` None when empty as in `findings`. `propose_finding_status` is registered after `propose_category_change`, with the writers' annotations:

```python
def propose_finding_status(
    type: str, status: str, reason: str, about: str = "", month: str = ""
) -> dict[str, Any]: ...
# In one writing session: _month_start(month), then find_finding(session, start, type, about),
# then propose_finding_status. A ValueError becomes a ToolError with its message.
```

Every proposal item gains `"finding"`, after `"rule_change"` and before `"category_change"`: None, except for `FINDING_STATUS`: `{"type": <finding_type>, "about": <finding_subject>, "month": "YYYY-MM", "status": <value>}`; for it `"transaction_id"` and `"category"` are None. The descriptions, exactly:

```python
GET_INSIGHTS_DESCRIPTION = (
    "Findings for a month (YYYY-MM, default this month): each with its type, severity (high, "
    "medium, low), subject (a category or merchant, or null), what acting on it could save a "
    "month in integer cents, and a sentence; findings a person handled (that month) or ignored "
    "(every month) are left out of findings and listed in set_aside with their status; and each "
    "merchant's visits, spending, average, baseline from earlier months, change, and weekend "
    "visits, in integer cents."
)
PROPOSE_FINDING_STATUS_DESCRIPTION = (
    "Propose marking an open finding of get_insights handled (that month only) or ignored (its "
    "type and subject in every month). Name it by type, about (its subject; empty for interest "
    "and fees), and month (YYYY-MM, default this month), and give a one-line reason a person "
    "will read. It changes nothing until a person accepts it with fin review. Refused when the "
    "finding is not there or already has a status, and when a person declined it or another "
    "proposal for that finding is open. No amounts."
)
```

## Requirements

- **R1.** The given migration; the three columns on `ProposalRow` in its order; the three fields on `Proposal`; `to_proposal`.
- **R2.** `FINDING_STATUS`, `KINDS`, `proposal_text`, and `status_for` as designed.
- **R3.** `propose_finding_status` as designed, its checks in the table's order, exported from `finances.db.repositories`.
- **R4.** Out of date and accepting as designed.
- **R5.** The review rows and the texts as designed.
- **R6.** `set_aside`, the tool, `"finding"` on every item, and the two descriptions as designed.
- **R7.** Apply the given diff to `tests/support.py` and the twelve earlier test files. No other earlier test changes.

## Given migration

```python
"""Add the finding a proposal names: its type, subject, and month (finding_status proposals)."""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.add_column(sa.Column("finding_type", sa.String(30), nullable=True))
        batch.add_column(sa.Column("finding_subject", sa.String(100), nullable=True))
        batch.add_column(sa.Column("finding_month", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("proposals") as batch:
        batch.drop_column("finding_month")
        batch.drop_column("finding_subject")
        batch.drop_column("finding_type")
```

## Given diff to earlier tests

The tool lists, the description table, the repository areas, the kinds, `"set_aside": []` in the one whole `get_insights` answer, and `"finding": None` before `"category_change"` in every whole proposal item. A spike showed that with the item key, `set_aside`, and the kind in place, all of these pass except the seven that need the new tool registered.

```text
diff --git a/tests/integration/test_mcp_accounts.py b/tests/integration/test_mcp_accounts.py
index bf88cc9..2747177 100644
--- a/tests/integration/test_mcp_accounts.py
+++ b/tests/integration/test_mcp_accounts.py
@@ -37,6 +37,7 @@ NO_AMOUNTS = (
     "propose_new_category",
     "propose_rule_change",
     "propose_category_change",
+    "propose_finding_status",
 )
 READ_ONLY = {
     "read_only_hint": True,
diff --git a/tests/integration/test_mcp_alias_proposals.py b/tests/integration/test_mcp_alias_proposals.py
index 40f90e8..adb0d8f 100644
--- a/tests/integration/test_mcp_alias_proposals.py
+++ b/tests/integration/test_mcp_alias_proposals.py
@@ -70,6 +70,7 @@ def test_the_agent_proposes_an_alias(card: Settings) -> None:
             "waits_for": None,
             "rule_change": None,
             "category_change": None,
+            "finding": None,
             "reason": "the same shop",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_more.py b/tests/integration/test_mcp_more.py
index 8fbdd78..566d1d1 100644
--- a/tests/integration/test_mcp_more.py
+++ b/tests/integration/test_mcp_more.py
@@ -36,6 +36,7 @@ from finances.mcp_server.server import (
     MONTH_OVER_MONTH_DESCRIPTION,
     PROPOSE_CATEGORY_CHANGE_DESCRIPTION,
     PROPOSE_CATEGORY_DESCRIPTION,
+    PROPOSE_FINDING_STATUS_DESCRIPTION,
     PROPOSE_GROUP_DESCRIPTION,
     PROPOSE_MERCHANT_ALIAS_DESCRIPTION,
     PROPOSE_NEW_CATEGORY_DESCRIPTION,
@@ -171,6 +172,7 @@ def test_each_tool_description_matches_the_table(tmp_settings: Settings) -> None
         "propose_new_category": PROPOSE_NEW_CATEGORY_DESCRIPTION,
         "propose_rule_change": PROPOSE_RULE_CHANGE_DESCRIPTION,
         "propose_category_change": PROPOSE_CATEGORY_CHANGE_DESCRIPTION,
+        "propose_finding_status": PROPOSE_FINDING_STATUS_DESCRIPTION,
         "list_proposals": LIST_PROPOSALS_DESCRIPTION,
         "log_advice": LOG_ADVICE_DESCRIPTION,
         "list_advice": LIST_ADVICE_DESCRIPTION,
diff --git a/tests/integration/test_mcp_new_categories.py b/tests/integration/test_mcp_new_categories.py
index a003bff..b2fa453 100644
--- a/tests/integration/test_mcp_new_categories.py
+++ b/tests/integration/test_mcp_new_categories.py
@@ -69,6 +69,7 @@ def item(kind: str, new: dict, reason: str) -> dict:
             "waits_for": None,
             "rule_change": None,
             "category_change": None,
+            "finding": None,
             "reason": reason,
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_outlook_more.py b/tests/integration/test_mcp_outlook_more.py
index ede5470..b03c955 100644
--- a/tests/integration/test_mcp_outlook_more.py
+++ b/tests/integration/test_mcp_outlook_more.py
@@ -115,6 +115,7 @@ def test_insights_for_a_month_with_no_data(today: Settings) -> None:
         "month": "2024-01",
         "findings": [],
         "merchants": [],
+        "set_aside": [],
     }
 
 
diff --git a/tests/integration/test_mcp_proposals.py b/tests/integration/test_mcp_proposals.py
index 965945c..ab66b70 100644
--- a/tests/integration/test_mcp_proposals.py
+++ b/tests/integration/test_mcp_proposals.py
@@ -33,6 +33,7 @@ FROM_REPOSITORIES = {
     "proposal_out_of_date",
     "propose_category",
     "propose_category_change",
+    "propose_finding_status",
     "propose_group",
     "propose_merchant_alias",
     "propose_new_category",
@@ -114,6 +115,7 @@ def test_a_proposal_and_its_listing(one: Settings) -> None:
         "waits_for": None,
         "rule_change": None,
         "category_change": None,
+        "finding": None,
         "reason": "a cafe",
         "status": "open",
         "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_rule_proposals.py b/tests/integration/test_mcp_rule_proposals.py
index b1a848f..c429693 100644
--- a/tests/integration/test_mcp_rule_proposals.py
+++ b/tests/integration/test_mcp_rule_proposals.py
@@ -72,6 +72,7 @@ def test_the_agent_proposes_a_rule(card: Settings) -> None:
             "waits_for": None,
             "rule_change": None,
             "category_change": None,
+            "finding": None,
             "reason": "a cafe",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_mcp_transfer_proposals.py b/tests/integration/test_mcp_transfer_proposals.py
index af7b453..3e5252f 100644
--- a/tests/integration/test_mcp_transfer_proposals.py
+++ b/tests/integration/test_mcp_transfer_proposals.py
@@ -64,6 +64,7 @@ def test_the_agent_proposes_a_transfer(moved: Settings) -> None:
             "waits_for": None,
             "rule_change": None,
             "category_change": None,
+            "finding": None,
             "reason": "same day, same amount",
             "status": "open",
             "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/integration/test_transfer_proposals_more.py b/tests/integration/test_transfer_proposals_more.py
index 1138113..b7a6f3b 100644
--- a/tests/integration/test_transfer_proposals_more.py
+++ b/tests/integration/test_transfer_proposals_more.py
@@ -41,6 +41,7 @@ PAIR = {
     "waits_for": None,
     "rule_change": None,
     "category_change": None,
+    "finding": None,
     "reason": "interest, not a transfer",
     "status": "open",
     "created_at": "2026-05-25T12:00:00+00:00",
diff --git a/tests/support.py b/tests/support.py
index 640105d..661c07a 100644
--- a/tests/support.py
+++ b/tests/support.py
@@ -221,6 +221,7 @@ MCP_TOOLS = [
     "month_over_month",
     "propose_category",
     "propose_category_change",
+    "propose_finding_status",
     "propose_group",
     "propose_merchant_alias",
     "propose_new_category",
@@ -239,5 +240,6 @@ MCP_WRITERS = (
     "propose_new_category",
     "propose_rule_change",
     "propose_category_change",
+    "propose_finding_status",
     "log_advice",
 )
diff --git a/tests/unit/test_proposal_rules.py b/tests/unit/test_proposal_rules.py
index 6a51472..a9304b1 100644
--- a/tests/unit/test_proposal_rules.py
+++ b/tests/unit/test_proposal_rules.py
@@ -31,6 +31,7 @@ def test_the_lists_and_limits() -> None:
             "rule_delete",
             "category_rename",
             "category_delete",
+            "finding_status",
         ),
     )
     assert (OPEN, ACCEPTED, DECLINED, STATUSES) == (
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index 912d786..cf5eba4 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -95,6 +95,9 @@ HOMES = {
         "reopen_finding",
         "set_finding_status",
     ],
+    "finding_proposals": [
+        "propose_finding_status",
+    ],
     "category_changes": [
         "propose_category_change",
     ],
@@ -202,7 +205,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 138
+    assert len(expected) == 139
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
diff --git a/tests/unit/test_rule_proposal_rules.py b/tests/unit/test_rule_proposal_rules.py
index 72fcf9b..6db5cc0 100644
--- a/tests/unit/test_rule_proposal_rules.py
+++ b/tests/unit/test_rule_proposal_rules.py
@@ -29,6 +29,7 @@ def test_the_kinds() -> None:
         "rule_delete",
         "category_rename",
         "category_delete",
+        "finding_status",
     )
 
 
```

## Given tests

15 tests in two files. Do not change them.

`tests/integration/test_migration_0026.py`

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
    ("finding_type", "VARCHAR(30)", True),
    ("finding_subject", "VARCHAR(100)", True),
    ("finding_month", "DATE", True),
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


def test_0026_follows_0025() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0026")
    assert script.down_revision == "0025"


def test_the_columns_come_and_go_and_the_rows_stay(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = make_config(url)
    command.upgrade(config, "0025")
    engine = get_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO proposals (kind, target_id, value, reason, status, created_at)"
                " VALUES ('category', 1, 'Dining', 'a cafe', 'open', '2026-05-25 12:00:00.000000')"
            )
        )
    engine.dispose()
    command.upgrade(config, "0026")
    found = columns(url)
    assert found[-3:] == ADDED
    orm = [(c.name, str(c.type), c.nullable) for c in ProposalRow.__table__.columns]
    assert orm[: len(found)] == found
    assert reasons(url) == ["a cafe"]
    command.downgrade(config, "0025")
    assert columns(url)[-1] == ("before", "VARCHAR(200)", True)
    assert reasons(url) == ["a cafe"]
    command.upgrade(config, "0026")
    assert columns(url)[-3:] == ADDED
```

`tests/integration/test_mcp_finding_proposals.py`

```python
import anyio
import pytest
from mcp.client import Client

from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.mcp_server.server import build_server
from tests.support import add_findings_data, failed_cleanly, plain_lines, run, table_rows

MAY = ("--month", "2026-05")
HANDLE_SPIKE = {
    "type": "spike",
    "about": "dining",
    "month": "2026-05",
    "status": "handled",
    "reason": "a one-off dinner",
}
IGNORE_INTEREST = {"type": "interest", "month": "2026-05", "status": "ignored", "reason": "known"}
SPIKE_DETAIL = "Dining: $200.00 this month, against $60.00 a month before."
TYPES = (
    "type must be one of: spike, frequent_small, subscription_overlap, price_increase, interest, "
    "fees, over_budget, duplicate, large_first_charge"
)


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def made(arguments: dict) -> dict:
    return call("propose_finding_status", arguments).structured_content["proposal"]


def error(arguments: dict) -> list[str]:
    return [item.text for item in call("propose_finding_status", arguments).content]


def rows() -> list[list[str]]:
    return table_rows(run("review", "list").stdout)[1:]


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    upgrade_to_head()
    add_findings_data()
    return tmp_settings


def test_the_agent_proposes_a_finding_handled(money: Settings) -> None:
    proposal = made(HANDLE_SPIKE)
    assert (
        proposal["kind"],
        proposal["transaction_id"],
        proposal["category"],
        proposal["finding"],
    ) == (
        "finding_status",
        None,
        None,
        {"type": "spike", "about": "Dining", "month": "2026-05", "status": "handled"},
    )
    assert rows() == [
        [
            "1",
            "",
            "",
            "",
            "",
            "spike for Dining in 2026-05",
            "mark handled",
            "a one-off dinner",
            "open",
        ]
    ]
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: spike for Dining in 2026-05 is handled.\n",
    )
    assert table_rows(run("insights", *MAY).stdout)[-1] == [
        "medium",
        "spike",
        "Dining",
        "$140.00",
        SPIKE_DETAIL,
        "handled",
    ]


def test_the_agent_proposes_a_finding_ignored(money: Settings) -> None:
    assert made(IGNORE_INTEREST)["finding"] == {
        "type": "interest",
        "about": "",
        "month": "2026-05",
        "status": "ignored",
    }
    assert rows()[0][5:7] == ["interest in 2026-05", "ignore in every month"]
    accepted = run("review", "accept", "--id", "1")
    assert accepted.stdout == "Accepted proposal 1: interest in every month is ignored.\n"
    assert plain_lines(run("insights", "--month", "2026-06").stdout) == [
        "Insights for 2026-06.",
        "No findings.",
        "Handled or ignored:",
    ]


def test_accepting_records_the_status_in_history(money: Settings) -> None:
    made(HANDLE_SPIKE)
    run("review", "accept", "--id", "1")
    found = table_rows(run("audit").stdout)
    assert [row[1:] for row in found[1:3]] == [
        [
            "person",
            "proposal_accepted",
            "proposal 1",
            "",
            "finding spike for Dining in 2026-05: handled",
        ],
        ["person", "finding_handled", "finding 1", "", "spike for Dining in 2026-05"],
    ]


def test_get_insights_lists_the_set_aside_findings(money: Settings) -> None:
    run("findings", "handle", "--type", "spike", "--about", "Dining", *MAY)
    found = call("get_insights", {"month": "2026-05"}).structured_content
    assert [item["type"] for item in found["findings"]] == [
        "interest",
        "price_increase",
        "frequent_small",
        "subscription_overlap",
    ]
    assert found["set_aside"] == [
        {
            "type": "spike",
            "severity": "medium",
            "subject": "Dining",
            "savings_cents": 14000,
            "detail": SPIKE_DETAIL,
            "status": "handled",
        }
    ]


def test_a_person_setting_the_status_first_puts_it_out_of_date(money: Settings) -> None:
    made(IGNORE_INTEREST)
    run("findings", "handle", "--type", "interest", *MAY)
    assert rows()[0][8] == "out of date"
    assert failed_cleanly(
        run("review", "accept", "--id", "1"),
        "proposal 1 is out of date: a person set this finding's status since",
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({**HANDLE_SPIKE, "about": "Groceries"}, "no such finding: spike for Groceries in 2026-05"),
        (
            {**HANDLE_SPIKE, "type": "nope"},
            TYPES,
        ),
        ({**HANDLE_SPIKE, "month": "2026-13"}, "month must be a year and month, like 2026-05"),
        ({**HANDLE_SPIKE, "status": "done"}, "status must be one of: handled, ignored"),
        ({**HANDLE_SPIKE, "reason": " "}, "a reason must be 1 to 200 characters"),
    ],
)
def test_a_refused_proposal(money: Settings, arguments: dict, message: str) -> None:
    assert error(arguments) == [f"Error executing tool propose_finding_status: {message}"]


def test_a_finding_with_a_status_is_refused(money: Settings) -> None:
    run("findings", "ignore", "--type", "interest", *MAY)
    assert error(IGNORE_INTEREST) == [
        "Error executing tool propose_finding_status: this finding is already ignored"
    ]


def test_one_open_proposal_for_a_finding(money: Settings) -> None:
    made(HANDLE_SPIKE)
    assert error({**HANDLE_SPIKE, "status": "ignored"}) == [
        "Error executing tool propose_finding_status: this finding already has an open proposal"
    ]


def test_a_declined_proposal_is_not_made_again(money: Settings) -> None:
    made(IGNORE_INTEREST)
    run("review", "decline", "--id", "1")
    assert error(IGNORE_INTEREST) == [
        "Error executing tool propose_finding_status: a person declined this proposal already"
    ]
    assert made({**IGNORE_INTEREST, "status": "handled"})["id"] == 2
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_finding_proposals_more.py` (section core, or mcp for the tool cases):

- `status_for` gives what `status_of` gives for the same parts (handled in May asked for June: None);
- a stored proposal has `target_id` 0, `finding_month` the finding's month for an ignored proposal, and a subject longer than 100 characters cut to 100;
- a declined handled proposal for May does not refuse a handled proposal for June of the same finding (a finding seen in both months, as `add_findings_data`'s interest);
- an open handled proposal for May does not refuse a handled proposal for June of the same finding (the interest again): the open check compares the month;
- an ignored proposal from May goes out of date when a person ignores the same finding from June;
- the Review page lists a finding proposal with empty transaction cells and accepts it;
- `propose_finding_status` with no month uses this month (the clock patched, as the other MCP tests patch it).

## Rules for this phase

- The tool only stores proposals: nothing in `mcp_server` calls `set_finding_status` or `reopen_finding`.
- Earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the check: `.venv/bin/python scripts/check.py --first migrations,core,mcp,cli,web`;
- the given test files above, 15 tests; at least N + 15 passed in all;
- `git diff --stat HEAD -- tests` lists only `tests/support.py` and the twelve files of the given diff;
- `git grep -n -e "set_finding_status" -e "reopen_finding" -- src/finances/mcp_server` prints nothing;
- the coverage command: `.venv/bin/python -m coverage report --include="*/finances/domain/proposals.py,*/finances/domain/findings.py,*/finances/db/orm.py,*/finances/db/repositories/findings.py,*/finances/db/repositories/finding_proposals.py,*/finances/db/repositories/proposals.py,*/finances/db/repositories/chains.py,*/finances/analysis/review.py,*/finances/views/review.py,*/finances/mcp_server/tools.py,*/finances/mcp_server/server.py" --fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 45b: the agent proposes a finding's status (YYYY-MM-DD)`.
