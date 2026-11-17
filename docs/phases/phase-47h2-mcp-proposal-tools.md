# Phase 47h2: extract MCP proposal and advice tools

## Goal

Move proposal/advice adapters into a cohesive module while preserving the supported
`finances.mcp_server.tools` facade and all observable behavior.

Owner decision (2026-11-16): four separately reviewed stages: serialization,
proposal/advice, reports, then accounts/queues and the final size gate. This is
stage two. No additional product decisions are required.

Architect decision: move the shared month parser into `helpers.py` now because
finding-status proposals and reporting both need it. Retain its internal alias
`_month_start` at both consumers; do not create a dependency back to the facade.

## Read first

Read AGENTS.md, architecture, testing, phase-conventions, progress, the 47h1 spec
and review, audit-remediation-design section 47h, and tools.py, serialization.py,
access.py, server.py and test_mcp_serialization_behavior.py.

## Starting state

Phase 47h1 is approved at `1a7056e221f1a390122aa391d2cf86ecd2609cc3`;
implementation `5419497`, 4687 tests, no findings or deviations. **N=4687;
Sections: mcp.** Newest migration: `0026_proposal_findings.py`.
Tools has 716 lines and 31 registered functions; serialization has 153 lines.
Moving 13 existing tools and two private helpers is approximately 210 body lines,
not new product behavior; it follows the owner's approved split.

Finalized planning documents must be committed before implementation. Use a fresh
isolated clone of that planning commit, link the existing .venv, exclude that
symlink locally, set PYTHONPATH to clone/src, and confirm finances.__file__ there.
Preserve original untracked .vscode/settings.json. Record the full planning SHA;
no implementation until planning docs match the committed baseline.

## Scope

| Path | What changes |
|---|---|
| `src/finances/mcp_server/proposals.py` | New: 13 adapters and _as_tool |
| `src/finances/mcp_server/helpers.py` | New: shared month_start |
| `src/finances/mcp_server/tools.py` | Remove moved definitions/imports; explicit public re-exports and helper alias |
| `tests/unit/test_mcp_proposal_tools.py` | New: given 17 cases |
| `tests/unit/test_mcp_proposal_tools_behavior.py` | New: coder behavior/structure cases |
| `tests/unit/test_mcp_serialization_behavior.py` | Exact given patch only |
| `docs/progress.md` | Append one phase entry |

## Out of scope

Reporting/account/queue relocation, final global size gate, server/access or
serializer changes, repository/schema changes, new features, dependency/tooling
changes, other test edits, and financial calculation or ordering changes.

## Dependencies

None new. MCP 2.3.0 and pydantic 2.14.1 were used for the inventory probe.

## Design

`proposals.py` owns these existing contracts verbatim, including annotations and
defaults (the original source is authoritative for annotation spelling):

```python
def propose_category(transaction_id: int, category: str, reason: str) -> dict[str, Any]: ...
def propose_transfer(out_id: int, in_id: int, reason: str) -> dict[str, Any]: ...
def propose_not_transfer(out_id: int, in_id: int, reason: str) -> dict[str, Any]: ...
def propose_rule(example_id: int, pattern: str, category: str, reason: str, match: Literal['contains', 'starts_with', 'equals']='contains', priority: Annotated[int, Field(ge=-1000, le=1000)]=0) -> dict[str, Any]: ...
def propose_merchant_alias(example_id: int, target: str, reason: str) -> dict[str, Any]: ...
def propose_group(name: str, example_id: int, reason: str, kind: Literal['spending', 'transfer', 'income']='spending', sensitive: bool=False) -> dict[str, Any]: ...
def propose_new_category(name: str, group: str, example_id: int, reason: str, tax: bool=False) -> dict[str, Any]: ...
def propose_rule_change(rule_id: int, reason: str, delete: bool=False, pattern: str | None=None, match: Literal['contains', 'starts_with', 'equals'] | None=None, priority: Annotated[int | None, Field(ge=-1000, le=1000)]=None, category: str | None=None) -> dict[str, Any]: ...
def propose_category_change(name: str, reason: str, rename_to: str | None=None, delete: bool=False, move_to: str | None=None) -> dict[str, Any]: ...
def propose_finding_status(type: str, status: str, reason: str, about: str='', month: str='') -> dict[str, Any]: ...
def list_proposals(status: Literal['open', 'accepted', 'declined']='open', limit: Annotated[int, Field(ge=1, le=200)]=50) -> dict[str, Any]: ...
def log_advice(text: str, subject: str='') -> dict[str, Any]: ...
def list_advice(limit: Annotated[int, Field(ge=1, le=200)]=20) -> dict[str, Any]: ...
```

Move their complete ASTs without changes, including nested work functions,
validation order, repository argument passing, context-manager boundaries and
serialization calls. Move `_as_tool(work: Callable[[], dict[str, Any]]) ->
dict[str, Any]` unchanged into proposals. It translates ValueError and
CategoryExistsError to ToolError(str(error)) from None; other exceptions escape.
Do not catch exceptions more broadly or introduce wrapper functions.

Move the existing `_month_start(month: str) -> date` into helpers as
`month_start(month: str) -> date`. Only the definition name changes; preserve the
body and conditional clock read. Both tools and proposals import it as
`_month_start`. Helper module imports only clock, domain periods, date, ToolError;
no facade, registration, session, configuration or persistence dependency.

Tools explicitly re-exports all 13 functions using `name as name` imports. These
must be the same function objects, not wrappers. Remove moved definitions,
_as_tool and unused imports. Other 18 public tool bodies stay byte-equivalent in
AST, including annotations. Server registration/descriptions stay unchanged.
`find_finding` remains in proposals; `insights_report` remains in tools.
Serialization and access remain leaf dependencies. No area module imports tools
or server, and no dynamic export/dispatch or compatibility patch machinery.

Repository imports move with their consumers; the package-wide repository import
inventory and writer capability inventory remain exactly unchanged. All ten
proposal writers and log_advice use writing; list_proposals/list_advice use
reading. Finding-status validation still happens inside writing; retain all
current error messages, JSON shapes, paging caps, clocks and ordering.

New source modules are at most 400 lines each. Tools may temporarily exceed 400
but must be at most its present 716 lines, under the approved exception ending
at 47h4. No arbitrary code relocation to meet limits.

## Requirements

- **R1.** Move all 13 tools and _as_tool with unchanged ASTs; retain identity through facade.
- **R2.** Share month_start with only its definition renamed; preserve clock/error behavior.
- **R3.** Preserve complete public metadata, capability and repository inventories and unchanged read-tool bodies.
- **R4.** Preserve proposal/advice responses, repository calls, error translation and access/transaction boundaries.
- **R5.** Apply only the given earlier-test patch, keeping its assertions and AST hashes; respect module layering and size limits.

## Given diff to earlier tests

47h1 introduced facade patch points and a whole-file AST pin. Moving implementations
necessarily moves those patch points. This patch changes only the module patched
for moved dependencies, adds reading contexts for mixed tests, and collects the
same AST hashes across their new owning files (normalizing month_start's name).
No hash, expected dictionary or public read-tool assertion changes. The existing
_TOOLS module assertion remains valid because it covers the 18 unmoved read tools.
Apply this exact patch; no other earlier test edits.

```text
--- a/tests/unit/test_mcp_serialization_behavior.py
+++ b/tests/unit/test_mcp_serialization_behavior.py
@@ -10,8 +10,8 @@
 from finances.analysis.search import FoundTransaction
 from finances.domain.models import DataSource, Transaction
 from finances.domain.spending import Flow
+from finances.mcp_server import helpers, proposals, tools
 from finances.mcp_server import serialization as ser
-from finances.mcp_server import tools
 from tests.unit.test_mcp_serialization import CASES, proposal


@@ -205,9 +205,9 @@
     session = Mock()
     item = proposal("category")
     marker = {"synthetic": "marker"}
-    monkeypatch.setattr(tools, "writing", lambda: nullcontext(session))
-    monkeypatch.setattr(tools, seam, Mock(return_value=item))
-    monkeypatch.setattr(tools, "find_finding", Mock(return_value=object()))
+    monkeypatch.setattr(proposals, "writing", lambda: nullcontext(session))
+    monkeypatch.setattr(proposals, seam, Mock(return_value=item))
+    monkeypatch.setattr(proposals, "find_finding", Mock(return_value=object()))
     serializer = Mock(return_value=marker)
     monkeypatch.setattr(ser, "proposal_item", serializer)
     assert getattr(tools, name)(*args) == {"proposal": marker}
@@ -220,7 +220,8 @@
     item = proposal("category")
     marker = {"synthetic": "marker"}
     monkeypatch.setattr(tools, "reading", lambda: nullcontext(session))
-    monkeypatch.setattr(tools, "load_proposals", Mock(return_value=[item]))
+    monkeypatch.setattr(proposals, "reading", lambda: nullcontext(session))
+    monkeypatch.setattr(proposals, "load_proposals", Mock(return_value=[item]))
     serializer = Mock(return_value=marker)
     monkeypatch.setattr(ser, "proposal_item", serializer)
     assert tools.list_proposals() == {"proposals": [marker]}
@@ -320,9 +321,10 @@
         text="Synthetic note",
         dismissed_at=None,
     )
-    monkeypatch.setattr(tools, "writing", lambda: nullcontext(session))
-    monkeypatch.setattr(tools, "keep_advice", Mock(return_value=item))
-    monkeypatch.setattr(tools, "load_advice", Mock(return_value=[item]))
+    monkeypatch.setattr(proposals, "writing", lambda: nullcontext(session))
+    monkeypatch.setattr(proposals, "keep_advice", Mock(return_value=item))
+    monkeypatch.setattr(proposals, "reading", lambda: nullcontext(session))
+    monkeypatch.setattr(proposals, "load_advice", Mock(return_value=[item]))
     expected = {
         "id": 1,
         "created_at": "2026-01-02T00:00:00+00:00",
@@ -376,10 +378,17 @@
 def test_tool_bodies_match_planning_baseline():
     import hashlib

-    tree = ast.parse(Path(tools.__file__).read_text())
+    nodes = []
+    for module in (tools, proposals, helpers):
+        tree = ast.parse(Path(module.__file__).read_text())
+        for node in tree.body:
+            if isinstance(node, ast.FunctionDef):
+                if module is helpers and node.name == "month_start":
+                    node.name = "_month_start"
+                nodes.append(node)
     actual = {
         node.name: hashlib.sha256(ast.dump(node).encode()).hexdigest()
-        for node in tree.body
+        for node in nodes
         if isinstance(node, ast.FunctionDef)
     }
     assert actual == BASELINE_ASTS
```

## Given tests

17 cases in one file, unchanged:
`tests/unit/test_mcp_proposal_tools.py`.

```python
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from finances.mcp_server import tools


@pytest.mark.parametrize(
    "name",
    [
        "propose_category",
        "propose_transfer",
        "propose_not_transfer",
        "propose_rule",
        "propose_merchant_alias",
        "propose_group",
        "propose_new_category",
        "propose_rule_change",
        "propose_category_change",
        "propose_finding_status",
        "list_proposals",
        "log_advice",
        "list_advice",
    ],
)
def test_facade_identity(name):
    from finances.mcp_server import proposals

    assert getattr(tools, name) is getattr(proposals, name)
    assert getattr(tools, name).__module__ == proposals.__name__


@pytest.mark.parametrize("kind", ["value", "category", "unexpected"])
def test_error_translation(kind):
    from finances.db.repositories.categories import CategoryExistsError
    from finances.mcp_server import proposals

    errors = {
        "value": ValueError("synthetic refusal"),
        "category": CategoryExistsError("synthetic refusal"),
        "unexpected": LookupError("synthetic refusal"),
    }
    work = Mock(side_effect=errors[kind])
    expected = LookupError if kind == "unexpected" else ToolError
    with pytest.raises(expected, match="^synthetic refusal$") as caught:
        proposals._as_tool(work)
    if kind != "unexpected":
        assert caught.value.__suppress_context__ is True
    work.assert_called_once_with()


def test_advice_json(monkeypatch):
    from finances.mcp_server import proposals

    session = Mock()
    row = SimpleNamespace(
        id=7,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        subject="Synthetic",
        text="Synthetic note",
        dismissed_at=None,
    )
    store = Mock(return_value=row)
    monkeypatch.setattr(proposals, "writing", lambda: nullcontext(session))
    monkeypatch.setattr(proposals, "keep_advice", store)
    assert tools.log_advice("Synthetic note", "Synthetic") == {
        "advice": {
            "id": 7,
            "created_at": "2026-01-02T00:00:00+00:00",
            "subject": "Synthetic",
            "text": "Synthetic note",
            "dismissed_at": None,
        }
    }
    store.assert_called_once_with(session, "Synthetic note", "Synthetic")
    assert session.mock_calls == []
```

Validation: fresh fail47h2b at approved predecessor, linked venv and clone import
path: 17 collected cases fail solely for missing proposals module. Four behavior
cases run separately against original tools pass (two refusal types, unexpected
exception and complete advice JSON). No feature implementation or source stubs.

## Tests to write

In `tests/unit/test_mcp_proposal_tools_behavior.py` (mcp section already matches):

- Check all ten proposal adapters pass positional/keyword arguments unchanged
  (nondefault match/priority, group kind/sensitive, tax, rename/delete/move_to and
  optional rule edits), serialize the returned row with the same session, and
  return its marker under proposal. Assert repository call arguments, not just
  output. Existing 47h1 wiring tests remain complementary evidence.
- Check list_proposals accepted/declined status and nondefault limit=3, ordered
  rows and complete envelopes; list_advice limit=3 with both null and aware
  dismissed timestamps; log_advice with default and explicit subjects.
- Check context events and raised exceptions: success exits writing normally;
  repository ValueError/CategoryExistsError reaches context exit before ToolError;
  LookupError escapes unchanged; read lists never enter writing. No commit/flush
  or ledger write added by adapters. Retain public in-memory MCP integration tests.
- Check month_start explicit 2026-02 never reads clock; empty input reads fixed
  2026-01-15 once and returns 2026-01-01; malformed 2026-13 raises original ToolError.
  Finding-status lookup receives selected first day, type and about before store;
  missing finding/error aborts storage. Reports still use shared helper alias.
- Check module sizes, facade identity, source dependency direction and unchanged
  ASTs using the given earlier-test pin. Read helper source to rule out dynamic
  imports/cycles. Keep serialization.py, access.py and server.py bytes unchanged.

These cases cover R1/R5 structural, R2 month behavior, R3 integration/inventory,
and R4 arguments/output/exception/context behavior. Achieve full line/branch
coverage of both new modules with meaningful assertions.

## Rules for this phase

All project privacy/layering rules apply: synthetic offline data, stdio MCP,
integer cents, proposal/advice-only writes, person acceptance required. No live
DB, Keychain, real statements or aggregator. No network calls or new dependencies.
No new coverage exemptions. No commit or push by coder/verifier.

## Acceptance

Run sequentially in isolated checkout:

1. `.venv/bin/python scripts/check.py --first mcp --workers 4`: all sections zero
   failures/skips/xfails, no warnings summary; at least **4704** passes (4687+17)
   plus coder cases, critical and overall gates pass, final `All checks passed.`
2. Immediately `.venv/bin/python -m coverage report --include="*/finances/mcp_server/proposals.py,*/finances/mcp_server/helpers.py" --fail-under=100`:
   both modules and TOTAL 100%, zero missing lines/branches.
3. `.venv/bin/python -m pytest tests/unit/test_mcp_proposal_tools.py --no-cov`:
   exactly 17 passed.
4. Guide's independent inventory probe: both ok lines and `FAILURES 0`.
5. Scope and given bytes match; earlier-test diff exactly given patch, no other
   old test changes; AST pin passes. Compare server/access/serialization against
   planning baseline: no differences. Check new source line caps and no area
   module imports facade/server by source/AST inspection, including untracked files.

If machine resources require serial execution record why; retain full gates.

## Report

Use phase-conventions format headed
`## Phase 47h2: extract MCP proposal and advice tools (YYYY-MM-DD)`.
Record 4687 baseline, 17 given, coder count, full planning SHA, isolation/import
provenance and temporary size exception. Supply requirement-to-test evidence,
Sections table and last ten check lines; report deviations honestly.
