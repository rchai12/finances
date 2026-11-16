# Phase 47d: shared proposal reasons and repository UTC time

## Goal

Replace the repeated proposal reason validators and repository UTC clocks with
two shared helpers, preserving refusals, stored values, event order and precision.
The accepted audit-remediation design, section 47d, settles product behavior;
no new owner decision is required.

Architect decisions (2026-11-16): one bounded refactor, two public helpers, nine
given cases, an exact clock-patch migration for thirty earlier test files, and
coder-owned writer/clock matrices. Estimated production diff is well below 300
lines; no migration, dependency, dispatch framework or repository superclass.

## Read first

AGENTS.md, docs/architecture.md, docs/testing.md, docs/phase-conventions.md,
docs/progress.md, docs/audit-remediation-design.md (47d),
src/finances/domain/proposals.py, src/finances/domain/text.py, and the repository
modules listed in Scope. Use the preceding phase's spec as the document pattern.

## Starting state and checked facts

Predecessor 47c is approved and committed at
`69294abde1d9622c5cda52bc314888e11aef3bc7`; progress and independent review agree
on **N = 4426**. **Sections: core,mcp,web,cli.** Newest migration remains
`0026_proposal_findings.py`. Proposal dispatch guards from 47c remain unchanged.

There are nine identical reason-validation sites across six repository files.
Ten public proposal writers reach them (transfer/not-transfer share _propose_pair).
All validate reason before other business validation or DB reads. Existing cleaned
length is inclusive 1–200, and collapse_ws uses split/join Unicode whitespace.

Eight modules define _now: proposals, finding_proposals, new_categories,
rule_changes, category_changes, audit, advice and findings. transfers lazily
imports proposals._now. Together they contain fifteen timestamp call sites.
The repository module cap remains 400 lines; proposals currently has 372 lines.
The db/time.py helper is outside repositories, so its addition changes neither
the repository facade inventory nor test_repositories_split.py pins.

log_advice reads once and creates no audit; dismiss_advice reads once. An ordinary
category acceptance with a changed assignment reads for category_set audit, then
proposal.decided_at, then proposal_accepted audit. A decline reads for decided_at,
then its audit. A new finding status reads for set_at, then its audit. Preserve
these separate reads. ORM conversion restores aware UTC timestamps on read.

The thirty earlier test files below patch old clocks. Equal constant patches can
collapse to one shared patch. Notes fixtures require special handling: two note
creation timestamps remain distinct and later dismissals need a usable clock;
notes_more switches from KEPT to GONE after setup. Existing assertion ASTs remain
identical in the supplied migration. No public output or assertion is relaxed.

### Baseline isolation

Preserve unrelated untracked .vscode/settings.json. The owner must commit this
final spec and guide before coding. Start in a fresh isolated clone of that
planning commit, link the existing venv, exclude its symlink locally, and set
PYTHONPATH to that clone's src for every Python invocation. Record the full
planning SHA and finances.__file__ provenance. Verify spec/guide match HEAD and
status is clean before implementation. Use the procedure in
.agents/skills/phase-architect/references/handoffs.md. Do not commit unrelated
workspace work to satisfy a scope gate.

## Scope

| Path | What changes |
|---|---|
| src/finances/domain/proposals.py | add clean_reason |
| src/finances/db/time.py | new utc_now helper |
| src/finances/db/repositories/proposals.py | shared reason and clock calls |
| src/finances/db/repositories/transfers.py | shared reason and clock calls, remove lazy _now import |
| src/finances/db/repositories/new_categories.py | shared reason and clock calls |
| src/finances/db/repositories/rule_changes.py | shared reason and clock calls |
| src/finances/db/repositories/category_changes.py | shared reason and clock calls |
| src/finances/db/repositories/finding_proposals.py | shared reason and clock calls |
| src/finances/db/repositories/audit.py | shared clock calls |
| src/finances/db/repositories/advice.py | shared clock calls |
| src/finances/db/repositories/findings.py | shared clock calls |
| tests/unit/test_proposal_helpers.py | new: given nine cases |
| tests/unit/test_proposal_helper_callers.py | new: coder delegation and precedence matrix |
| tests/integration/test_repository_time.py | new: coder persistence and clock matrix |
| docs/progress.md | append phase entry |
| tests/e2e/test_cli_audit.py | given clock-patch migration only |
| tests/e2e/test_cli_notes.py | given clock-patch migration only |
| tests/e2e/test_cli_review.py | given clock-patch migration only |
| tests/integration/test_alias_proposals.py | given clock-patch migration only |
| tests/integration/test_audit_events.py | given clock-patch migration only |
| tests/integration/test_audit_more.py | given clock-patch migration only |
| tests/integration/test_audit_trail.py | given clock-patch migration only |
| tests/integration/test_category_changes_more.py | given clock-patch migration only |
| tests/integration/test_chains_more.py | given clock-patch migration only |
| tests/integration/test_mcp_alias_proposals.py | given clock-patch migration only |
| tests/integration/test_mcp_category_changes.py | given clock-patch migration only |
| tests/integration/test_mcp_chains.py | given clock-patch migration only |
| tests/integration/test_mcp_new_categories.py | given clock-patch migration only |
| tests/integration/test_mcp_proposals.py | given clock-patch migration only |
| tests/integration/test_mcp_rule_changes.py | given clock-patch migration only |
| tests/integration/test_mcp_rule_proposals.py | given clock-patch migration only |
| tests/integration/test_mcp_transfer_proposals.py | given clock-patch migration only |
| tests/integration/test_new_category_proposals.py | given clock-patch migration only |
| tests/integration/test_notes_more.py | given clock-patch migration only |
| tests/integration/test_proposals.py | given clock-patch migration only |
| tests/integration/test_rule_changes_more.py | given clock-patch migration only |
| tests/integration/test_rule_proposals.py | given clock-patch migration only |
| tests/integration/test_transfer_proposals.py | given clock-patch migration only |
| tests/integration/test_transfer_proposals_more.py | given clock-patch migration only |
| tests/integration/test_web_chains.py | given clock-patch migration only |
| tests/integration/test_web_history.py | given clock-patch migration only |
| tests/integration/test_web_notes.py | given clock-patch migration only |
| tests/integration/test_web_review.py | given clock-patch migration only |
| tests/integration/test_web_review_more.py | given clock-patch migration only |
| tests/unit/test_proposal_dispatch_matrix.py | given clock-patch migration only |

New tests belong to core through the existing fallback; no section config change.
The thirty earlier files may change only by the exact given diff below.

## Out of scope

All other timestamps: ORM defaults, ingest/sync clocks, local calendar
clock.today(), web session/auth/backup clocks. No timestamp caching, batching,
precision truncation, changed audit text, text-limit changes, reason truncation,
new kind, migration, MCP permission, adapter change or unrelated cleanup.

## Dependencies

None new. Use the existing venv and approved local worker dependency.

## Design and requirements

- **R1.** Add pure `clean_reason(reason: str) -> str` to domain/proposals.py.
  Call existing domain.text.collapse_ws; accept cleaned length 1 through
  PROPOSAL_TEXT_LIMIT inclusive. Return the entire cleaned string. Otherwise
  raise exactly `ValueError("a reason must be 1 to 200 characters")` without
  echoing input. No truncation, raw-length check or additional business rule.
- **R2.** Replace all nine local validation copies with that helper. Preserve
  reason-first validation at propose_category, propose_transfer,
  propose_not_transfer, propose_rule, propose_merchant_alias, propose_group,
  propose_new_category, propose_rule_change, propose_category_change and
  propose_finding_status. Keep all surrounding argument checks, dependency reads,
  refusals, stored reasons, proposal shapes and transaction ownership identical.
  Transfer wrappers may continue to delegate to _propose_pair. Imports/aliases
  of clean_reason are coder-owned; avoid shadowing it with a local variable.
- **R3.** Add `utc_now() -> datetime` in db/time.py, returning datetime.now(UTC):
  aware UTC, full existing microsecond precision, fresh read on each call.
  No arguments, caching, clock.today() dependency or database access.
- **R4.** Replace the eight _now definitions and all fifteen call sites through
  the imported module, for example `from finances.db import time as db_time`
  and `db_time.utc_now()`. The sole replacement point for tests is
  `finances.db.time.utc_now`. Do not capture the function with a from-import or
  keep compatibility _now wrappers. Remove transfers' lazy clock import.
  Keep all clock reads at their current event positions. No one-time timestamp
  reused for multiple events, or new read at import time.
- **R5.** Persisted proposal created/accepted/declined, advice created/dismissed,
  finding set_at and audit at all use the shared clock. Event timestamps can
  differ: preserve each read and existing ordering, audit actions, before/after
  values, return shapes and aware UTC conversion. No new commit/rollback.
- **R6.** Apply the exact given earlier-test diff. Every previous assertion,
  expected row/message and test identity stays unchanged. Shared clock test
  migration must not consume note timestamp iterators in setup/dismissal in a
  way that changes the two creation times. Existing domain and repository
  inventories, permission/privacy gates, and all prior phase behavior still pass.

## Given migration

None. No schema or existing migration changes.

## Given diff to earlier tests

Apply this exact diff from the finalized planning baseline. It migrates thirty
files. Repeated equal clock patches become one; notes creation fixtures fall back
to 13:00 for later dismissal calls, and notes_more changes the clock after setup.
No application behavior is supplied here. Do not change prior assertions.

```text
diff --git a/tests/e2e/test_cli_audit.py b/tests/e2e/test_cli_audit.py
index 0c67d31..2a3d390 100644
--- a/tests/e2e/test_cli_audit.py
+++ b/tests/e2e/test_cli_audit.py
@@ -11,7 +11,7 @@ HEADINGS = ["When (UTC)", "Who", "Action", "Record", "Before", "After"]
 @pytest.fixture
 def changed(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     monkeypatch.setattr(
-        "finances.db.repositories.audit._now", lambda: datetime(2026, 5, 25, 14, 3, 59, tzinfo=UTC)
+        "finances.db.time.utc_now", lambda: datetime(2026, 5, 25, 14, 3, 59, tzinfo=UTC)
     )
     assert run("db", "upgrade").exit_code == 0
     assert (
diff --git a/tests/e2e/test_cli_notes.py b/tests/e2e/test_cli_notes.py
index 4b15479..6d69d9e 100644
--- a/tests/e2e/test_cli_notes.py
+++ b/tests/e2e/test_cli_notes.py
@@ -15,7 +15,9 @@ HEADINGS = ["ID", "When (UTC)", "Subject", "Note", "State"]
 def notes(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     """Note 1 (budgets) at 12:00 and note 2 (no subject) at 12:05; no proposals."""
     stamps = iter([datetime(2026, 5, 25, 12, minute, tzinfo=UTC) for minute in (0, 5)])
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: next(stamps))
+    monkeypatch.setattr(
+        "finances.db.time.utc_now", lambda: next(stamps, datetime(2026, 5, 25, 13, 0, tzinfo=UTC))
+    )
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as session:
diff --git a/tests/e2e/test_cli_review.py b/tests/e2e/test_cli_review.py
index 2c1f45a..d466fd0 100644
--- a/tests/e2e/test_cli_review.py
+++ b/tests/e2e/test_cli_review.py
@@ -15,7 +15,7 @@ HEADINGS = ["ID", "Date", "Account", "Description", "Amount", "Now", "Proposed",
 def proposed(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     """Two coffees on a card with the agent's proposals (1 and 2)."""
     monkeypatch.setattr(
-        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
+        "finances.db.time.utc_now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
     )
     assert run("db", "upgrade").exit_code == 0
     engine = get_engine()
diff --git a/tests/integration/test_alias_proposals.py b/tests/integration/test_alias_proposals.py
index c63fb44..43d5769 100644
--- a/tests/integration/test_alias_proposals.py
+++ b/tests/integration/test_alias_proposals.py
@@ -88,7 +88,7 @@ def assigned(session: Session) -> dict[int, str]:
 
 @pytest.fixture
 def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: NOON)
     with session_scope(db_engine) as opened:
         add_card(opened)
         yield opened
@@ -96,7 +96,7 @@ def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Sess
 
 @pytest.fixture
 def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: NOON)
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as opened:
diff --git a/tests/integration/test_audit_events.py b/tests/integration/test_audit_events.py
index b7b9a60..75ff478 100644
--- a/tests/integration/test_audit_events.py
+++ b/tests/integration/test_audit_events.py
@@ -35,7 +35,7 @@ def trail() -> list[tuple]:
 @pytest.fixture
 def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
     """A card added, then a backup FIRST taken; the trail's clock reads NOON."""
-    monkeypatch.setattr("finances.db.repositories.audit._now", lambda: NOON)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: NOON)
     monkeypatch.setattr(
         "finances.web.app._now", lambda: datetime(2026, 10, 17, 9, 0, 0, tzinfo=UTC)
     )
diff --git a/tests/integration/test_audit_more.py b/tests/integration/test_audit_more.py
index ec129f0..3e4942c 100644
--- a/tests/integration/test_audit_more.py
+++ b/tests/integration/test_audit_more.py
@@ -31,7 +31,7 @@ MIDNIGHT = datetime(2026, 5, 25, 0, 0, tzinfo=UTC)
 
 @pytest.fixture
 def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
-    monkeypatch.setattr("finances.db.repositories.audit._now", lambda: NOON)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: NOON)
     with session_scope(db_engine) as opened:
         yield opened
 
@@ -118,7 +118,7 @@ def test_audit_without_a_migrated_database(tmp_settings: Settings) -> None:
 def test_since_keeps_a_change_at_midnight_utc_that_day(
     db_engine: Engine, monkeypatch: pytest.MonkeyPatch
 ) -> None:
-    monkeypatch.setattr("finances.db.repositories.audit._now", lambda: MIDNIGHT)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: MIDNIGHT)
     with session_scope(db_engine) as session:
         create_account(session, "Test Card", "Test Bank", "credit_card")
         assert [item.after for item in list_changes(session, since=date(2026, 5, 25))] == [
diff --git a/tests/integration/test_audit_trail.py b/tests/integration/test_audit_trail.py
index 91f791f..50e99eb 100644
--- a/tests/integration/test_audit_trail.py
+++ b/tests/integration/test_audit_trail.py
@@ -40,7 +40,7 @@ NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
 
 @pytest.fixture
 def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
-    monkeypatch.setattr("finances.db.repositories.audit._now", lambda: NOON)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: NOON)
     with session_scope(db_engine) as opened:
         yield opened
 
@@ -202,7 +202,7 @@ def test_list_changes_newest_first_and_filters(
 ) -> None:
     for day, name in ((24, "Test A"), (25, "Test B"), (25, "Test C")):
         moment = datetime(2026, 5, day, 23, 30, tzinfo=UTC)
-        monkeypatch.setattr("finances.db.repositories.audit._now", lambda moment=moment: moment)
+        monkeypatch.setattr("finances.db.time.utc_now", lambda moment=moment: moment)
         create_account(session, name, "Test Bank", "checking")
     create_person(session, "Pat Example")
     assert [item.after for item in list_changes(session)] == [
diff --git a/tests/integration/test_category_changes_more.py b/tests/integration/test_category_changes_more.py
index 1619f78..c81b6d7 100644
--- a/tests/integration/test_category_changes_more.py
+++ b/tests/integration/test_category_changes_more.py
@@ -39,11 +39,10 @@ RENAME_TEXT = "category Dining: rename to Restaurants"
 @pytest.fixture
 def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     """Rule 1 puts ACME in Dining; transaction 2 is Groceries by hand."""
-    for module in ("proposals", "category_changes", "new_categories", "rule_changes"):
-        monkeypatch.setattr(
-            f"finances.db.repositories.{module}._now",
-            lambda: NOON,
-        )
+    monkeypatch.setattr(
+        "finances.db.time.utc_now",
+        lambda: NOON,
+    )
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as session:
diff --git a/tests/integration/test_chains_more.py b/tests/integration/test_chains_more.py
index 375f2a1..f849a0e 100644
--- a/tests/integration/test_chains_more.py
+++ b/tests/integration/test_chains_more.py
@@ -28,11 +28,10 @@ NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
 
 @pytest.fixture
 def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
-    for module in ("proposals", "new_categories"):
-        monkeypatch.setattr(
-            f"finances.db.repositories.{module}._now",
-            lambda: NOON,
-        )
+    monkeypatch.setattr(
+        "finances.db.time.utc_now",
+        lambda: NOON,
+    )
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as session:
diff --git a/tests/integration/test_mcp_alias_proposals.py b/tests/integration/test_mcp_alias_proposals.py
index adb0d8f..b26e800 100644
--- a/tests/integration/test_mcp_alias_proposals.py
+++ b/tests/integration/test_mcp_alias_proposals.py
@@ -29,7 +29,7 @@ def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     """Two card purchases: 1 cleans to ACME CAFE, 2 to ACME COFFEE; a rule puts ACME COFFEE in
     Dining, so 2 is categorized and 1 is not."""
     monkeypatch.setattr(
-        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
+        "finances.db.time.utc_now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
     )
     upgrade_to_head()
     engine = get_engine()
diff --git a/tests/integration/test_mcp_category_changes.py b/tests/integration/test_mcp_category_changes.py
index 8bcc2c0..3351fa9 100644
--- a/tests/integration/test_mcp_category_changes.py
+++ b/tests/integration/test_mcp_category_changes.py
@@ -44,11 +44,10 @@ def error(name: str, arguments: dict) -> list[str]:
 def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     """Rule 1 puts ACME in Dining, so transaction 1 (ACME COFFEE) is Dining by the rule;
     a person set transaction 2 (FOOBAR GROCERY) to Groceries by hand."""
-    for module in ("proposals", "category_changes"):
-        monkeypatch.setattr(
-            f"finances.db.repositories.{module}._now",
-            lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
-        )
+    monkeypatch.setattr(
+        "finances.db.time.utc_now",
+        lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
+    )
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as session:
diff --git a/tests/integration/test_mcp_chains.py b/tests/integration/test_mcp_chains.py
index a04f51c..4a16ffc 100644
--- a/tests/integration/test_mcp_chains.py
+++ b/tests/integration/test_mcp_chains.py
@@ -38,11 +38,10 @@ def made(name: str, arguments: dict) -> dict:
 @pytest.fixture
 def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     """One card purchase with no category: transaction 1, FOOBAR PET SUPPLY, -$25.99."""
-    for module in ("proposals", "new_categories"):
-        monkeypatch.setattr(
-            f"finances.db.repositories.{module}._now",
-            lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
-        )
+    monkeypatch.setattr(
+        "finances.db.time.utc_now",
+        lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
+    )
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as session:
diff --git a/tests/integration/test_mcp_new_categories.py b/tests/integration/test_mcp_new_categories.py
index b2fa453..e4dd2bc 100644
--- a/tests/integration/test_mcp_new_categories.py
+++ b/tests/integration/test_mcp_new_categories.py
@@ -32,11 +32,10 @@ def error(name: str, arguments: dict) -> list[str]:
 @pytest.fixture
 def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     """One card purchase with no category: transaction 1, FOOBAR PET SUPPLY, -$25.99."""
-    for module in ("proposals", "new_categories"):
-        monkeypatch.setattr(
-            f"finances.db.repositories.{module}._now",
-            lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
-        )
+    monkeypatch.setattr(
+        "finances.db.time.utc_now",
+        lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
+    )
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as session:
diff --git a/tests/integration/test_mcp_proposals.py b/tests/integration/test_mcp_proposals.py
index ab66b70..c96fbae 100644
--- a/tests/integration/test_mcp_proposals.py
+++ b/tests/integration/test_mcp_proposals.py
@@ -56,7 +56,7 @@ def call(name: str, arguments: dict | None = None):
 def one(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     """A card with one coffee and no category."""
     monkeypatch.setattr(
-        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
+        "finances.db.time.utc_now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
     )
     upgrade_to_head()
     engine = get_engine()
diff --git a/tests/integration/test_mcp_rule_changes.py b/tests/integration/test_mcp_rule_changes.py
index be983f2..81b121e 100644
--- a/tests/integration/test_mcp_rule_changes.py
+++ b/tests/integration/test_mcp_rule_changes.py
@@ -40,11 +40,7 @@ def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     """Rule 1 puts ACME in Dining, so transaction 1 (ACME COFFEE) is Dining by the rule;
     a person set transaction 2 (FOOBAR GROCERY) to Groceries by hand."""
     monkeypatch.setattr(
-        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
-    )
-    monkeypatch.setattr(
-        "finances.db.repositories.rule_changes._now",
-        lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
+        "finances.db.time.utc_now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
     )
     upgrade_to_head()
     engine = get_engine()
diff --git a/tests/integration/test_mcp_rule_proposals.py b/tests/integration/test_mcp_rule_proposals.py
index c429693..2862166 100644
--- a/tests/integration/test_mcp_rule_proposals.py
+++ b/tests/integration/test_mcp_rule_proposals.py
@@ -34,7 +34,7 @@ def call(name: str, arguments: dict | None = None):
 def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     """Two card purchases: 1 cleans to ACME COFFEE, 2 to FOOBAR GROCERY. No rules."""
     monkeypatch.setattr(
-        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
+        "finances.db.time.utc_now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
     )
     upgrade_to_head()
     engine = get_engine()
diff --git a/tests/integration/test_mcp_transfer_proposals.py b/tests/integration/test_mcp_transfer_proposals.py
index 3e5252f..ab93383 100644
--- a/tests/integration/test_mcp_transfer_proposals.py
+++ b/tests/integration/test_mcp_transfer_proposals.py
@@ -25,7 +25,7 @@ def call(name: str, arguments: dict | None = None):
 def moved(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     """$20.00 out of checking (1) and into savings (2) the same day."""
     monkeypatch.setattr(
-        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
+        "finances.db.time.utc_now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
     )
     upgrade_to_head()
     engine = get_engine()
diff --git a/tests/integration/test_new_category_proposals.py b/tests/integration/test_new_category_proposals.py
index 39f54b9..0c3d8cc 100644
--- a/tests/integration/test_new_category_proposals.py
+++ b/tests/integration/test_new_category_proposals.py
@@ -35,11 +35,10 @@ NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
 
 @pytest.fixture
 def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
-    for module in ("proposals", "new_categories"):
-        monkeypatch.setattr(
-            f"finances.db.repositories.{module}._now",
-            lambda: NOON,
-        )
+    monkeypatch.setattr(
+        "finances.db.time.utc_now",
+        lambda: NOON,
+    )
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as session:
diff --git a/tests/integration/test_notes_more.py b/tests/integration/test_notes_more.py
index b0890be..72b7373 100644
--- a/tests/integration/test_notes_more.py
+++ b/tests/integration/test_notes_more.py
@@ -38,8 +38,7 @@ def call(name: str, arguments: dict | None = None):
 
 @pytest.fixture
 def home(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: KEPT)
-    monkeypatch.setattr("finances.db.repositories.advice._now", lambda: GONE)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: KEPT)
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as session:
@@ -60,6 +59,7 @@ def home(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
         session.flush()
         propose_category(session, 1, "Coffee & Dessert", "ACME is a coffee shop")
     engine.dispose()
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: GONE)
     return tmp_settings
 
 
diff --git a/tests/integration/test_proposals.py b/tests/integration/test_proposals.py
index e8c3cb6..6a5851c 100644
--- a/tests/integration/test_proposals.py
+++ b/tests/integration/test_proposals.py
@@ -32,7 +32,7 @@ NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
 def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
     """Coffee with no category (1), groceries set by a rule (2), books set by hand (3), and a
     card payment paired as a transfer (4 and 5)."""
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: NOON)
     with session_scope(db_engine) as opened:
         create_account(opened, "Test Card", "Test Bank", "credit_card")
         create_account(opened, "Test Checking", "Test Bank", "checking")
diff --git a/tests/integration/test_rule_changes_more.py b/tests/integration/test_rule_changes_more.py
index c0ccc83..bf6ba7f 100644
--- a/tests/integration/test_rule_changes_more.py
+++ b/tests/integration/test_rule_changes_more.py
@@ -34,8 +34,7 @@ NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
 @pytest.fixture
 def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     """Rule 1 puts ACME in Dining; transaction 2 is Groceries by hand; 3 has no category."""
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
-    monkeypatch.setattr("finances.db.repositories.rule_changes._now", lambda: NOON)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: NOON)
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as session:
diff --git a/tests/integration/test_rule_proposals.py b/tests/integration/test_rule_proposals.py
index 60a81f3..5721ab3 100644
--- a/tests/integration/test_rule_proposals.py
+++ b/tests/integration/test_rule_proposals.py
@@ -75,7 +75,7 @@ def assigned(session: Session) -> dict[int, str]:
 
 @pytest.fixture
 def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: NOON)
     with session_scope(db_engine) as opened:
         add_card(opened)
         yield opened
@@ -83,7 +83,7 @@ def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Sess
 
 @pytest.fixture
 def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: NOON)
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as opened:
diff --git a/tests/integration/test_transfer_proposals.py b/tests/integration/test_transfer_proposals.py
index b1ff586..e05e532 100644
--- a/tests/integration/test_transfer_proposals.py
+++ b/tests/integration/test_transfer_proposals.py
@@ -31,7 +31,7 @@ NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
 def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
     """A move to savings with two possible inflows (1 out; 2 and 3 in), waiting for review; a
     card payment the rules pair (4 and 5); a coffee (6) and money in of another amount (7)."""
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: NOON)
     with session_scope(db_engine) as opened:
         create_account(opened, "Test Checking", "Test Bank", "checking")
         create_account(opened, "Test Savings", "Test Bank", "savings")
diff --git a/tests/integration/test_transfer_proposals_more.py b/tests/integration/test_transfer_proposals_more.py
index b7a6f3b..0941615 100644
--- a/tests/integration/test_transfer_proposals_more.py
+++ b/tests/integration/test_transfer_proposals_more.py
@@ -83,7 +83,7 @@ def add_move(session: Session) -> None:
 
 @pytest.fixture
 def moved(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: NOON)
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as session:
@@ -94,7 +94,7 @@ def moved(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
 
 @pytest.fixture
 def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: NOON)
     with session_scope(db_engine) as opened:
         add_move(opened)
         yield opened
diff --git a/tests/integration/test_web_chains.py b/tests/integration/test_web_chains.py
index 7635469..1107c9a 100644
--- a/tests/integration/test_web_chains.py
+++ b/tests/integration/test_web_chains.py
@@ -24,11 +24,10 @@ WAITING = (
 @pytest.fixture
 def home(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
     """1 a group Pets; 2 a category Dog Food in it, which waits for 1."""
-    for module in ("proposals", "new_categories"):
-        monkeypatch.setattr(
-            f"finances.db.repositories.{module}._now",
-            lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
-        )
+    monkeypatch.setattr(
+        "finances.db.time.utc_now",
+        lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
+    )
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as session:
diff --git a/tests/integration/test_web_history.py b/tests/integration/test_web_history.py
index 67568da..26714ea 100644
--- a/tests/integration/test_web_history.py
+++ b/tests/integration/test_web_history.py
@@ -36,11 +36,11 @@ def changed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
     engine = get_engine()
     with session_scope(engine) as session:
         monkeypatch.setattr(
-            "finances.db.repositories.audit._now", lambda: datetime(2026, 5, 24, 9, 0, tzinfo=UTC)
+            "finances.db.time.utc_now", lambda: datetime(2026, 5, 24, 9, 0, tzinfo=UTC)
         )
         create_account(session, "Test Card", "Test Bank", "credit_card")
         monkeypatch.setattr(
-            "finances.db.repositories.audit._now", lambda: datetime(2026, 5, 25, 14, 3, tzinfo=UTC)
+            "finances.db.time.utc_now", lambda: datetime(2026, 5, 25, 14, 3, tzinfo=UTC)
         )
         create_person(session, "Pat Example")
         create_rule(session, "ACME", "Dining")
diff --git a/tests/integration/test_web_notes.py b/tests/integration/test_web_notes.py
index 9933edb..1b39a46 100644
--- a/tests/integration/test_web_notes.py
+++ b/tests/integration/test_web_notes.py
@@ -23,7 +23,9 @@ def client(tmp_settings: Settings) -> TestClient:
 def home(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
     """Note 1 (budgets) at 12:00 and note 2 (no subject) at 12:05."""
     stamps = iter([datetime(2026, 5, 25, 12, minute, tzinfo=UTC) for minute in (0, 5)])
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: next(stamps))
+    monkeypatch.setattr(
+        "finances.db.time.utc_now", lambda: next(stamps, datetime(2026, 5, 25, 13, 0, tzinfo=UTC))
+    )
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as session:
diff --git a/tests/integration/test_web_review.py b/tests/integration/test_web_review.py
index 5564154..0a68211 100644
--- a/tests/integration/test_web_review.py
+++ b/tests/integration/test_web_review.py
@@ -24,7 +24,7 @@ NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
 
 @pytest.fixture
 def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: NOON)
     found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
     return found
 
diff --git a/tests/integration/test_web_review_more.py b/tests/integration/test_web_review_more.py
index 2febd07..89581b8 100644
--- a/tests/integration/test_web_review_more.py
+++ b/tests/integration/test_web_review_more.py
@@ -108,7 +108,7 @@ def test_the_notes_table_shows_at_most_twenty_newest_first(
 ) -> None:
     times = [datetime(2026, 5, 25, 12, minute, tzinfo=UTC) for minute in range(21)]
     stamps = iter(times)
-    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: next(stamps))
+    monkeypatch.setattr("finances.db.time.utc_now", lambda: next(stamps))
     upgrade_to_head()
     engine = get_engine()
     with session_scope(engine) as session:
diff --git a/tests/unit/test_proposal_dispatch_matrix.py b/tests/unit/test_proposal_dispatch_matrix.py
index 1566312..c44a35a 100644
--- a/tests/unit/test_proposal_dispatch_matrix.py
+++ b/tests/unit/test_proposal_dispatch_matrix.py
@@ -5,6 +5,7 @@ from unittest.mock import Mock, call
 
 import pytest
 
+from finances.db import time as db_time
 from finances.db.repositories import proposals as repo
 from finances.domain import proposals as domain
 from finances.domain.models import CONFIRMED
@@ -88,7 +89,7 @@ def test_acceptance_dispatches_exactly_one_handler(monkeypatch, kind):
     monkeypatch.setattr(repo, "to_proposal", lambda r: domain.Proposal(**vars(r)))
     monkeypatch.setattr(repo, "waits_for", waiting)
     monkeypatch.setattr(repo, "proposal_out_of_date", stale)
-    monkeypatch.setattr(repo, "_now", lambda: NOW)
+    monkeypatch.setattr(db_time, "utc_now", lambda: NOW)
     audit = Mock()
     monkeypatch.setattr(repo, "record_change", audit)
     order = Mock()
```

## Given tests

Nine collected cases, unchanged in `tests/unit/test_proposal_helpers.py`.
In a fresh clone of the predecessor, names-only NotImplementedError stubs allowed
collection: seven reason cases and the clock case failed at those missing
helpers; the audit case failed because it still used its private clock. No
reference implementation was made. The given file and all migrated earlier
files pass lint and formatting. The diff preserves all assertion ASTs.

```python
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from finances.db import time as db_time
from finances.db.repositories import audit
from finances.domain.proposals import clean_reason


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        pytest.param("a", "a", id="one"),
        pytest.param(" \tACME\n  reason\u00a0 here \r", "ACME reason here", id="collapse"),
        pytest.param(
            "x" * 200,
            (
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            ),
            id="limit",
        ),
        pytest.param(
            " \n" + "x" * 200 + "\t ",
            (
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            ),
            id="cleaned-limit",
        ),
    ],
)
def test_clean_reason_accepts_cleaned_text(reason, expected):
    assert clean_reason(reason) == expected


@pytest.mark.parametrize("reason", ["", " \n\t\u00a0", "x" * 201], ids=["empty", "blank", "long"])
def test_clean_reason_refuses_without_echo(reason):
    with pytest.raises(ValueError, match="^a reason must be 1 to 200 characters$"):
        clean_reason(reason)


def test_utc_now_reads_aware_utc_each_time(monkeypatch):
    first = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    second = datetime(2026, 1, 2, 3, 4, 6, 654321, tzinfo=UTC)
    source = Mock()
    source.now.side_effect = [first, second]
    monkeypatch.setattr(db_time, "datetime", source)
    assert db_time.utc_now() is first
    assert db_time.utc_now() is second
    assert source.now.call_args_list == [((UTC,), {}), ((UTC,), {})]


def test_audit_reads_shared_clock_per_event(monkeypatch):
    first = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    second = datetime(2026, 1, 2, 3, 4, 6, 654321, tzinfo=UTC)
    clock = Mock(side_effect=[first, second])
    monkeypatch.setattr(db_time, "utc_now", clock)
    monkeypatch.setattr(audit, "to_change", lambda row: row)
    session = Mock()
    one = audit.record_change(
        session, action="category_added", kind="category", record_id=1, after="Synthetic leaf"
    )
    two = audit.record_change(
        session, action="category_added", kind="category", record_id=2, after="Synthetic other"
    )
    assert one.at is first
    assert two.at is second
    assert (one.after, two.after) == ("Synthetic leaf", "Synthetic other")
    assert clock.call_count == 2
```

## Tests to write

`tests/unit/test_proposal_helper_callers.py` (core):

- R2: complete ten-public-writer delegation matrix. Patch clean_reason at its
  actual lookup binding to raise a distinct ValueError subclass sentinel. Pass
  a reason containing tabs/newlines and deliberately invalid target/other fields.
  Assert original reason received exactly once, sentinel identity propagated,
  and zero session/query/clock/write calls. This detects retained inline copies
  even if their ordinary outputs are identical. Include both transfer wrappers.
- R2: invalid cleaned reason plus invalid target/category/rule/status inputs
  returns the constant reason refusal before those other validations for every
  writer. Cover both edit/delete and rename/delete forms. No DB query or mutation
  before refusal. At least one valid-reason case per family still reaches its
  existing next refusal; assert the exact historical error, not the sentinel.
- R1/R2: a helper returning a distinct normalized marker on otherwise valid
  synthetic cases is stored verbatim, proving callers use its returned value;
  this may share the integration creation matrix instead of duplicating fixtures.

`tests/integration/test_repository_time.py` (core, migrated db_engine):

- R2/R4/R5: valid proposal creation matrix reaching all nine creation sites:
  category, transfer and not-transfer, rule, alias, group, new_category,
  rule_change, category_change, finding_status (ten public rows). Cover edit and
  delete options in rule/category changes. Reset the controlled shared clock
  after fixture/setup writes. Each proposal created_at is the exact controlled
  aware timestamp with microseconds, and reason is the cleaned value. Include
  helper-marker cases at all nine sites; patch the helper at its lookup binding.
  Use valid synthetic bases per proposal kind; no schema bypass here.
- R5: create an unassigned purchase and category proposal before installing a
  strict three-value clock iterator. Accept it with a changed assignment. Expect
  category_set audit at t1, decided_at at t2, proposal_accepted audit at t3;
  assert exactly three reads and literal before/after audit texts. Read fresh
  session state so naive SQLite storage cannot hide conversion problems.
- R5: an open proposal declined after setup consumes exactly two distinct clock
  values: decided_at then proposal_declined audit. Assert stored values and text.
- R4/R5: log_advice then dismiss_advice use two separate values (one each),
  with no new audit records. Assert created/dismissed timestamps in returned and
  freshly loaded data; refusal of repeated dismissal makes no additional read.
- R4/R5: direct new finding status consumes two values: set_at then its audit;
  assert exact action/text and no timestamp reuse. Also accept a finding-status
  proposal after setup: status set_at, finding audit, proposal decided_at,
  proposal acceptance audit consume four consecutive values in that order.
- R4: inventory covers every module named in Starting state plus transfers.
  Check no private _now compatibility definitions or captured utc_now imports
  remain in those files. Source inspection can complement the runtime matrix;
  do not replace persisted event assertions with source shape alone.

Use literal timestamps/expected audit strings, controlled clocks after setup and
strict call counts. The creation matrix plus advice, audit, decline, acceptance
and finding cases must account for all fifteen timestamp sites. No real data.

## Rules for this phase

Synthetic data and integer cents only; no network/Keychain/real samples. Domain
imports stay within domain; UTC helper belongs to db, not the repository facade.
Only listed source changes and the given prior-test diff are authorized. No
critical module is modified and no artificial critical-list expansion is needed.

## Acceptance

Run sequentially from the isolated committed-baseline checkout:

1. `.venv/bin/python scripts/check.py --first core,mcp,web,cli --workers 4`
   ends `All checks passed.`; at least **4435** full-suite passes (4426+9,
   plus coder cases), every section zero failures/skips, no xfails or warnings
   summary. A documented serial override is permitted for machine contention.
2. Immediately `.venv/bin/python -m coverage report --include="*/finances/domain/proposals.py,*/finances/db/time.py" --fail-under=100`:
   exit 0, each file and TOTAL at 100%, no missing lines or branches. This narrow
   helper target does not change the configured full-suite/critical gates.
3. `.venv/bin/python -m pytest tests/unit/test_proposal_helpers.py --no-cov`:
   exactly nine passed.
4. Inspect `git status --short --untracked-files=all`, `git diff HEAD` and
   `git diff HEAD -- tests`. Only Scope paths; earlier files equal the given
   diff and given new file equals its block. No test removals, renames, relaxed
   assertions or changes to fixtures outside that diff. Verifier additionally
   writes its authorized review. No new search command or independent probe.

## Report

Use phase-conventions.md, headed Phase 47d: shared proposal reasons and repository
UTC time. Record two public helper names, actual total, migration of thirty
clock-patched files, call-site coverage, baseline/import provenance, and any
blockers. Do not commit or push.
