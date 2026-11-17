# Phase 47h4: finalize the MCP tool facade

## Goal

Finish the owner's four-stage MCP split: account/balance tools, transaction/work
queues, supported facade and final size gate, preserving every observable behavior.
Owner decision 2026-11-16: four independently reviewed stages. Owner additionally
authorized delivering the reviewed 47h3 files into this workspace before planning
47h4. Architect decisions: accounts.py owns three account tools; queues.py owns
the other eight tools, including coverage and merchant lookup. Enforce the global
MCP cap through a permanent pytest test included by scripts/check.py, with no
facade exception needed. No new product decision is required.

## Read first

AGENTS.md, docs/architecture.md, docs/testing.md, docs/phase-conventions.md,
docs/progress.md, audit-remediation-design section 47h, 47h3 revision 2 spec and
review, all mcp_server modules and the earlier test files in Scope.

## Starting state and baseline delivery

47h3 has an independent PASS at 4761, no findings/deviations, review committed
1dd738f; original revised planning baseline d823d07. **N=4761; Sections: mcp.**
Latest migration 0026_proposal_findings.py. Reports 244 lines, tools 286.
The approved implementation had not been delivered when planning began. At the
owner's direction all nine reviewed paths were compared byte-for-byte to
/tmp/finances-47h3-r2-review and copied from /tmp/finances-47h3-work. They match,
including both period-test migrations; progress was reconciled as noted below. This is predecessor
delivery, not 47h4 implementation. No broad retest of approved bytes was performed.

**Before coding:** commit that exact predecessor delivery, then these planning
docs. Record both full SHAs. New planning HEAD must contain reports.py, updated
period tests, successful 4761 progress and the committed 47h3 PASS. Confirm all
planning docs match HEAD. Use fresh isolated clone of planning HEAD, link existing
venv, locally exclude symlink, set clone/src PYTHONPATH, verify finances.__file__.
Preserve unrelated .vscode/settings.json. Do not start from old 47h2 source or an
uncommitted overlay. The architect's scratch used local clone of 1dd738f plus only
the exact nine reviewed predecessor paths, deliberately recorded baseline delta.

Progress discrepancy: both isolated copies retained historical blocked progress,
despite review describing it as updated. Architect reconciled summary to the
committed independent PASS and preserved failed-run history; no new test run is
claimed. This progress correction must be included in predecessor delivery.

## Scope

| Path | Change |
|---|---|
| src/finances/mcp_server/accounts.py | New: list_accounts, get_balances, get_net_worth |
| src/finances/mcp_server/queues.py | New: list_transactions, list_uncategorized, list_categories, list_rules, list_transfers, list_transfer_suggestions, data_coverage, find_merchants |
| src/finances/mcp_server/tools.py | Imports-only supported facade |
| tests/unit/test_mcp_facade_contract.py | New given fourteen cases, including permanent global size gate |
| tests/unit/test_mcp_facade_behavior.py | New coder behavior tests |
| tests/unit/test_mcp_serialization_behavior.py | Exact given patch |
| tests/unit/test_account_listing_ownership.py | Exact given patch, supersedes 47f given patch locations only |
| tests/integration/test_mcp_account_listing.py | Exact given patch |
| docs/progress.md | Append one phase entry |

## Out of scope

Changes to reports/proposals/helpers/serialization/access/server, repositories,
financial rules, ordering, schemas, descriptions, dependencies, scripts/check.py,
configuration, old tests outside given patch, later 47i or 47j cleanup.

## Dependencies

None new; existing venv. Probe validated with MCP 2.3.0 and pydantic 2.14.1.

## Design

Move complete existing function ASTs unchanged, preserving annotations, defaults,
nested expressions and bodies. Account tools go to accounts, remaining functions
go to queues. Contracts below are transcribed from approved source:

```python
def list_accounts(include_inactive: bool=False) -> dict[str, Any]: ...
def get_balances() -> dict[str, Any]: ...
def get_net_worth(months: Annotated[int, Field(ge=1, le=60)]=12) -> dict[str, Any]: ...
def list_transactions(text: str='', account: str='', person: str='', category: str='', group: str='', merchant: str='', bank: str='', card: str='', kind: str='', start: date | None=None, end: date | None=None, limit: Annotated[int, Field(ge=1, le=200)]=50, offset: Annotated[int, Field(ge=0, le=5000)]=0) -> dict[str, Any]: ...
def list_uncategorized(limit: Annotated[int, Field(ge=1, le=500)]=50) -> dict[str, Any]: ...
def list_categories() -> dict[str, Any]: ...
def list_rules() -> dict[str, Any]: ...
def list_transfers(limit: Annotated[int, Field(ge=1, le=500)]=100) -> dict[str, Any]: ...
def list_transfer_suggestions() -> dict[str, Any]: ...
def data_coverage() -> dict[str, Any]: ...
def find_merchants(phrase: str, limit: Annotated[int, Field(ge=1, le=20)]=5) -> dict[str, Any]: ...
```

Tools has only its docstring and explicit import re-exports of all 31 tools and
By (`name as name`). No assignments, wrappers, private aliases, compatibility
monkeypatch forwarding, imports of repository/analysis/access/clock or functions.
Existing reports/proposal imports remain supported. All public function objects
are identical to area definitions. By remains the same reports.By object.

Area modules import only their actual dependencies, never tools/server. Keep
reading contexts at the exact current positions; no writing access. Preserve
transaction query limit offset+limit+1, page slicing/next_offset, all filters and
ToolError causes. Preserve transfer reverse-id ordering and total before limit;
suggestions preserve input order. Keep joint-owner formatting, balance signs,
ISO date/null fields, clock counts, configured backup directory and merchant
phrase strip/length precedence. All existing JSON shapes are unchanged.

**Final size gate:** every *.py recursively under src/finances/mcp_server,
including __init__, server, future new files and tools, has <=400 physical lines
using read_text().splitlines(). The given test enforces this on every standard
full check. No imports-only facade exception and no temporary monolith exception
remain after this phase. No arbitrary helper relocation. New modules are small:
roughly 65 account body lines, 170 queue body lines plus imports.

## Requirements

- R1: eleven verbatim function moves, identity exports and imports-only facade.
- R2: preserve all JSON, dates/cents, nulls, filtering, paging and transfer order.
- R3: unchanged read-only boundaries, validation, argument forwarding and errors.
- R4: unchanged 31-tool schema/signature/description/capability and repository inventories.
- R5: permanent global <=400 gate, dependency direction and exact scope/test migrations.

## Given diff to earlier tests

Move account mock dependencies to accounts in two earlier files (including
47f's given file), leaving facade calls and full response assertions unchanged.
Move queue mock dependencies to queues in serialization behavior; aggregate
unchanged AST hashes across accounts/queues; registration ownership now recognizes
reports/accounts/queues. Other earlier tests stay unchanged, including period tests
and proposal/report helper pins. Search covered all tests, not just MCP filenames.
This explicitly supersedes only old given import/patch locations, never behavior.
Patch added/removed lines must match; hunk headers/context formatting may vary.

```text
--- a/tests/unit/test_mcp_serialization_behavior.py
+++ b/tests/unit/test_mcp_serialization_behavior.py
@@ -10,7 +10,7 @@
 from finances.analysis.search import FoundTransaction
 from finances.domain.models import DataSource, Transaction
 from finances.domain.spending import Flow
-from finances.mcp_server import helpers, proposals, reports, tools
+from finances.mcp_server import accounts, helpers, proposals, queues, reports, tools
 from finances.mcp_server import serialization as ser
 from tests.unit.test_mcp_serialization import CASES, proposal

@@ -219,16 +219,16 @@
     session = Mock()
     item = proposal("category")
     marker = {"synthetic": "marker"}
-    monkeypatch.setattr(tools, "reading", lambda: nullcontext(session))
+    monkeypatch.setattr(queues, "reading", lambda: nullcontext(session))
     monkeypatch.setattr(proposals, "reading", lambda: nullcontext(session))
     monkeypatch.setattr(proposals, "load_proposals", Mock(return_value=[item]))
     serializer = Mock(return_value=marker)
     monkeypatch.setattr(ser, "proposal_item", serializer)
     assert tools.list_proposals() == {"proposals": [marker]}
     serializer.assert_called_once_with(session, item)
-    monkeypatch.setattr(tools, "account_names", Mock(return_value={2: "Test Card"}))
-    monkeypatch.setattr(tools, "load_uncategorized", Mock(return_value=[transaction()]))
-    monkeypatch.setattr(tools, "count_uncategorized", Mock(return_value=1))
+    monkeypatch.setattr(queues, "account_names", Mock(return_value={2: "Test Card"}))
+    monkeypatch.setattr(queues, "load_uncategorized", Mock(return_value=[transaction()]))
+    monkeypatch.setattr(queues, "count_uncategorized", Mock(return_value=1))
     brief = Mock(return_value=marker)
     monkeypatch.setattr(ser, "brief", brief)
     assert tools.list_uncategorized() == {
@@ -254,7 +254,14 @@

     assert all(
         fn is getattr(tools, fn.__name__)
-        and fn.__module__ == (reports.__name__ if hasattr(reports, fn.__name__) else tools.__name__)
+        and fn.__module__
+        == (
+            reports.__name__
+            if hasattr(reports, fn.__name__)
+            else accounts.__name__
+            if hasattr(accounts, fn.__name__)
+            else queues.__name__
+        )
         for fn, _ in _TOOLS
     )

@@ -265,10 +272,10 @@
     session = Mock()
     names = {2: "Test Card"}
     marker = {"synthetic": "moved"}
-    monkeypatch.setattr(tools, "reading", lambda: nullcontext(session))
-    monkeypatch.setattr(tools, "account_names", Mock(return_value=names))
+    monkeypatch.setattr(queues, "reading", lambda: nullcontext(session))
+    monkeypatch.setattr(queues, "account_names", Mock(return_value=names))
     found = object()
-    monkeypatch.setattr(tools, "search_transactions", Mock(return_value=[found]))
+    monkeypatch.setattr(queues, "search_transactions", Mock(return_value=[found]))
     tx = Mock(return_value=marker)
     monkeypatch.setattr(ser, "transaction_item", tx)
     assert tools.list_transactions() == {"transactions": [marker], "next_offset": None}
@@ -276,7 +283,7 @@
     named = Mock(return_value=marker)
     monkeypatch.setattr(ser, "named", named)
     monkeypatch.setattr(
-        tools,
+        queues,
         "list_transfer_pairs",
         Mock(return_value=[NS(id=3, status="auto", out_transaction_id=7, in_transaction_id=8)]),
     )
@@ -288,7 +295,7 @@

     assert named.call_args_list == [call(session, 7, names), call(session, 8, names)]
     named.reset_mock()
-    monkeypatch.setattr(tools, "transfer_suggestions", Mock(return_value=[(7, 8)]))
+    monkeypatch.setattr(queues, "transfer_suggestions", Mock(return_value=[(7, 8)]))
     assert tools.list_transfer_suggestions() == {"suggestions": [{"out": marker, "in": marker}]}
     assert named.call_args_list == [call(session, 7, names), call(session, 8, names)]
     iso = Mock(return_value="moved-date")
@@ -303,7 +310,7 @@
         drift_date=None,
     )
     monkeypatch.setattr(
-        tools,
+        queues,
         "coverage_report",
         Mock(
             return_value=NS(
@@ -383,7 +390,7 @@
     import hashlib

     nodes = []
-    for module in (tools, proposals, helpers, reports):
+    for module in (tools, proposals, helpers, reports, accounts, queues):
         tree = ast.parse(Path(module.__file__).read_text())
         for node in tree.body:
             if isinstance(node, ast.FunctionDef):
--- a/tests/unit/test_account_listing_ownership.py
+++ b/tests/unit/test_account_listing_ownership.py
@@ -8,7 +8,7 @@
 from finances.analysis import listings
 from finances.analysis.people import Attribution
 from finances.domain.models import Account, AccountType
-from finances.mcp_server import tools
+from finances.mcp_server import accounts, tools

 CARD = Account(
     1,
@@ -65,7 +65,7 @@
 @pytest.mark.parametrize("include_inactive", [False, True], ids=["active", "all"])
 def test_mcp_serializes_shared_listing_only(monkeypatch, include_inactive):
     session = Mock()
-    monkeypatch.setattr(tools, "reading", lambda: nullcontext(session))
+    monkeypatch.setattr(accounts, "reading", lambda: nullcontext(session))
     rows = [
         SimpleNamespace(account=CARD, owner=owner, joint=joint)
         for owner, joint in [
@@ -76,11 +76,11 @@
         ]
     ]
     loader = Mock(return_value=rows)
-    monkeypatch.setattr(tools, "account_listing", loader, raising=False)
+    monkeypatch.setattr(accounts, "account_listing", loader, raising=False)
     direct = []
     for name in ("list_people", "list_account_owners", "load_accounts"):
         spy = Mock(return_value=[])
-        monkeypatch.setattr(tools, name, spy, raising=False)
+        monkeypatch.setattr(accounts, name, spy, raising=False)
         direct.append(spy)
     assert tools.list_accounts(include_inactive) == {
         "accounts": [
--- a/tests/integration/test_mcp_account_listing.py
+++ b/tests/integration/test_mcp_account_listing.py
@@ -18,7 +18,7 @@
     set_account_active,
     set_account_owner,
 )
-from finances.mcp_server import tools
+from finances.mcp_server import accounts, tools
 from finances.mcp_server.server import build_server
 from finances.views.accounts import AccountRow, account_rows
 from finances.web.app import create_app
@@ -190,8 +190,8 @@
         return []

     loader = Mock(side_effect=load)
-    monkeypatch.setattr(tools, "reading", reading)
-    monkeypatch.setattr(tools, "account_listing", loader)
+    monkeypatch.setattr(accounts, "reading", reading)
+    monkeypatch.setattr(accounts, "account_listing", loader)
     assert tools.list_accounts() == {"accounts": []}
     loader.assert_called_once_with(session, include_inactive=False)
     assert events == ["enter", "exit"] and session.mock_calls == []
```

## Given tests

Fourteen cases, copy unchanged into tests/unit/test_mcp_facade_contract.py:

```python
import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from finances.mcp_server import tools


@pytest.mark.parametrize(
    "area,name",
    [
        ("accounts", "list_accounts"),
        ("accounts", "get_balances"),
        ("accounts", "get_net_worth"),
        ("queues", "list_transactions"),
        ("queues", "list_uncategorized"),
        ("queues", "list_categories"),
        ("queues", "list_rules"),
        ("queues", "list_transfers"),
        ("queues", "list_transfer_suggestions"),
        ("queues", "data_coverage"),
        ("queues", "find_merchants"),
    ],
)
def test_facade_identity(area, name):
    import importlib

    module = importlib.import_module("finances.mcp_server." + area)
    assert getattr(tools, name) is getattr(module, name)
    assert getattr(tools, name).__module__ == module.__name__


def test_all_mcp_sources_fit():
    folder = Path(tools.__file__).parent
    paths = list(folder.rglob("*.py"))
    assert paths
    assert not [
        (str(p.relative_to(folder)), len(p.read_text().splitlines()))
        for p in paths
        if len(p.read_text().splitlines()) > 400
    ]


def test_facade_contains_only_docstring_and_imports():
    tree = ast.parse(Path(tools.__file__).read_text())
    assert tree.body
    assert all(
        isinstance(n, (ast.Import, ast.ImportFrom))
        or (
            i == 0
            and isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
        )
        for i, n in enumerate(tree.body)
    )


def test_transfer_order_and_limit(monkeypatch):
    from finances.mcp_server import queues

    session = Mock()
    pairs = [
        SimpleNamespace(
            id=i, status="confirmed", out_transaction_id=i * 2, in_transaction_id=i * 2 + 1
        )
        for i in [1, 3, 2]
    ]
    monkeypatch.setattr(queues, "reading", lambda: nullcontext(session))
    monkeypatch.setattr(queues, "account_names", Mock(return_value={}))
    monkeypatch.setattr(queues, "list_transfer_pairs", Mock(return_value=pairs))
    named = Mock(side_effect=lambda s, i, names: {"id": i})
    monkeypatch.setattr(queues.serialization, "named", named)
    assert tools.list_transfers(2) == {
        "total": 3,
        "pairs": [
            {"pair": 3, "status": "confirmed", "out": {"id": 6}, "in": {"id": 7}},
            {"pair": 2, "status": "confirmed", "out": {"id": 4}, "in": {"id": 5}},
        ],
    }
    assert [c.args[1] for c in named.call_args_list] == [6, 7, 4, 5]
    assert session.mock_calls == []
```

Fresh fail47h4 on the documented predecessor overlay: thirteen intended failures
(missing area modules or facade bodies), one passing size guard. Transfer's full
literal expected order/total/limit passes against the original tool via temporary
import substitution. Size guard rejects planted401 lines and permits400; planted file removed.
No reference feature implementation, source stubs or full
suite run. Given files and migrated tests lint/format; given patch applies.

## Tests to write

In tests/unit/test_mcp_facade_behavior.py (existing mcp pattern):

- Complete literal balance JSON: dated and missing-date accounts, negative card
  balance, all totals and without_balance; net-worth two ordered points using
  fixed today, months=3 and exact analysis/session/date call.
- Transactions: every nondefault query filter, offset=2/limit=2 with five results,
  then exactly four results, checking whole rows and next_offset 4 versus None;
  reversed dates fail before reading; analysis ValueError preserves ToolError
  message/cause and LookupError propagates. Assert query contents/call arguments.
- Categories include groups and children and preserve flags/group resolution;
  rules include different priorities in loader order with exact category names.
  Uncategorized limit=3 preserves total and merchant cleaning. Synthetic literals.
- Coverage with span versus None, audited intervals, gaps, mapped flag, drift
  and null/date/timestamp values, accountless problem and named problem; pin full
  JSON and exact backup-dir/session/today forwarding. No real data or paths.
- Merchant blank whitespace refuses first, padded phrase strips before lookup,
  101-character original input refuses, boundary100 succeeds; limit=7 forwards;
  whole match dictionaries. Suggestions preserve supplied pair order and same
  session/names; no sorting or writes.
- Reading context exits normally and on exceptions; no writing/flush/commit
  by adapters. Existing account ownership test assertions remain authoritative.
- By and all other facade exports retain identity; module source contains no
  reverse/dynamic imports. Permanent cap guard sees a planted 401-line synthetic
  file in a temporary copied directory (never production); 400 is permitted.
  Existing hash pin verifies all moved and unaffected functions unchanged.

R1/R5: given identity/facade/cap and AST pin; R2: literal outputs, paging/order;
R3: deciding errors/contexts/calls; R4: probe, public integration and inventories.
Coverage means assertions on behavior, not executing branches without checks.

## Rules for this phase

Synthetic offline data only, integer cents, stdio MCP, no real DB/Keychain/
statements/aggregator or network. MCP writes remain proposal/advice-only, unchanged
in their existing module. No dependencies/migrations/coverage exemptions. Do not
modify old tests beyond exact patch. Coder/verifier do not commit or push.

## Acceptance

Sequentially with isolated clone PYTHONPATH:

1. `.venv/bin/python scripts/check.py --first mcp --workers 4`: final All checks
   passed.; all sections zero failed/skipped, no xfails/warnings summary, overall
   and critical gates pass; at least **4775** passes (4761+14), plus coder cases.
   Core runs in full suite and retains migrated ownership tests. Resource-driven
   serial override may be recorded, never omit full gates.
2. Immediately `.venv/bin/python -m coverage report --include="*/finances/mcp_server/accounts.py,*/finances/mcp_server/queues.py" --fail-under=100`:
   both modules and TOTAL 100%, zero missing lines/branches/partials.
3. `.venv/bin/python -m pytest tests/unit/test_mcp_facade_contract.py --no-cov`:
   exactly fourteen passed, including permanent recursive global cap gate.
4. Independent guide inventory probe: both ok lines, FAILURES 0.
5. Exactly nine Scope paths; given bytes and patch match; unchanged source
   byte comparison (server/access/helpers/proposals/reports/serialization);
   all original AST hashes retained; facade imports-only; no reverse/dynamic
   dependencies. No unlisted old tests, source or settings edited.

## Report

Standard phase-conventions entry headed
`## Phase 47h4: finalize the MCP tool facade (YYYY-MM-DD)`; N4761, given14,
full predecessor/planning SHAs, isolation/provenance, permanent gate and sizes,
requirement/test mapping, Sections table and final ten check lines. Record no
remaining temporary size exception. Separate predecessor delivery from this phase.
