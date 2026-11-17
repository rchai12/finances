# Phase 47h3: extract MCP reporting tools

## Goal

Move the seven reporting adapters into `finances.mcp_server.reports`, preserving
all public tool behavior and the supported tools facade.

Owner decision (2026-11-16): serialization, proposal/advice, reports, then
accounts/queues and the final size gate, independently reviewed and committed.
This implements the third stage. No new owner choice is required.
Architect decisions: use `reports.py`, move `By` with spending and explicitly
re-export it from tools; use the existing shared month helper. No new helper.

## Read first

AGENTS.md, docs/architecture.md, docs/testing.md, docs/phase-conventions.md,
docs/progress.md, audit-remediation-design section 47h, the 47h2 spec/review,
and mcp_server/tools.py, helpers.py, proposals.py, serialization.py, access.py,
server.py and the four earlier tests in Scope below.

## Starting state

47h2 PASS, zero findings/deviations, 4725 passes, approved commit
`713c9117d8aa5e79fa44e54a61d72aa9485d7bef` (implementation ac9cacc).
**N=4725. Sections: mcp.** Latest migration `0026_proposal_findings.py`.
Tools has 512 lines, proposals 222 and helpers 15. Seven existing adapter bodies
span roughly 230 lines; this is the already authorized reporting extraction,
not seven new capabilities. Public metadata has 31 tools and 11 writers.

Planning documents must be committed before implementation. Record full planning
SHA and confirm spec/guide equal its committed bytes. Use a fresh isolated clone
of that planning commit because unrelated .vscode/settings.json exists in the
original workspace. Link existing .venv, locally exclude its symlink and confirm
finances.__file__ is inside clone/src with explicit PYTHONPATH. Preserve unrelated
work. No dependency installation or feature spike is needed.

## Scope

| Path | What changes |
|---|---|
| `src/finances/mcp_server/reports.py` | New: seven existing reporting functions and By |
| `src/finances/mcp_server/tools.py` | Remove moved definitions/imports; explicit re-exports |
| `tests/unit/test_mcp_report_tools.py` | New: given twelve cases |
| `tests/unit/test_mcp_report_tools_behavior.py` | New: coder tests below |
| `tests/unit/test_mcp_serialization_behavior.py` | Exact given patch |
| `tests/unit/test_mcp_proposal_tools_behavior.py` | Exact given patch |
| `tests/unit/test_period_adapters.py` | Exact correction patch below; supersedes its 47g given bytes |
| `tests/integration/test_period_selection_compatibility.py` | Exact correction patch below |
| `docs/progress.md` | Append phase entry |

## Out of scope

Account/balance/net-worth, transactions, queues, coverage and merchant lookup
moves; final global gate; proposal, shared helper, serializer, access or server
changes; ORM/repositories, new behavior or dependencies, other earlier tests.
No renaming response keys, changing totals, ordering or error messages.

## Dependencies

None new. Inventory probe baseline uses MCP 2.3.0 and pydantic 2.14.1.

## Design

Move these signatures, annotations, defaults and complete function ASTs verbatim
from the approved predecessor to reports.py:

```python
def get_spending(start: date | None=None, end: date | None=None, by: By='category') -> dict[str, Any]: ...
def month_over_month(month: str='', count: Annotated[int, Field(ge=1, le=24)]=6) -> dict[str, Any]: ...
def get_insights(month: str='') -> dict[str, Any]: ...
def get_recurring(income: bool=False, include_inactive: bool=False) -> dict[str, Any]: ...
def get_upcoming(days: Annotated[int, Field(ge=1, le=90)]=30) -> dict[str, Any]: ...
def get_forecast(days: Annotated[int, Field(ge=1, le=90)]=30, account: str='') -> dict[str, Any]: ...
def get_budgets(month: str='') -> dict[str, Any]: ...
```

Move `By = Literal["category", "group", "merchant", "person", "account", "bank", "card"]`
unchanged. Tools explicitly imports each function and By using `name as name`;
all are identical objects, never wrappers. Move dependencies with their consumers;
remove unused facade imports, including its `_month_start` alias. Reports imports
`month_start as _month_start` from helpers; proposals' alias remains unchanged.
No compatibility alias for a private facade patch point. Reports imports neither
tools nor server and contains no writes, configuration access or dynamic exports.

All seven bodies are unchanged, including clock timing, select_period/date.min,
month_range's last-day selection, exception chaining, reading scope and response
construction. Reports returns plain data and keeps all cents integers. In
particular spending spent_cents means purchases, refunds_cents is money back,
net_cents is net spending; summary purchases adds refunds back to net. Recurring
charges negate amounts/previous values; income keeps them positive. Filtering
inactive series and keeping null previous_cents are preserved.

Server registration/descriptions, every generated input/output schema and
annotation, and all other function bodies stay unchanged. Existing explicit
proposal facade re-exports remain. New reports.py <=400 lines, tools <=512 under
the existing interim exception; remaining source modules stay byte-identical.
Global cap and final facade conversion are reserved for 47h4 even if tools now
fits 400. Do not arbitrarily move code to meet a cap.

## Requirements

- **R1.** Seven verbatim moves, By identity and explicit supported facade exports.
- **R2.** Preserve JSON, integer cents, signs, filtering, order and null handling.
- **R3.** Preserve argument forwarding, validation/errors, clocks and read-only contexts.
- **R4.** Preserve complete metadata/capability/repository inventories and unaffected bodies.
- **R5.** Only listed files/earlier-test patch change; dependency direction and caps hold.

## Given diff to earlier tests

This updates the two known location pins: aggregate unchanged function hashes
across reports too; registration read-tool ownership now uses reports for its
seven functions, retaining facade object identity; shared helper identity is
checked at reports instead of the now-unused private facade alias. No hashes,
JSON assertions or behavior pins change. No other test edits are authorized.
Raw diff hunk labels/context blank markers may vary; added/removed source lines
must match. Apply the following patch:

```text
--- a/tests/unit/test_mcp_serialization_behavior.py
+++ b/tests/unit/test_mcp_serialization_behavior.py
@@ -10,7 +10,7 @@
 from finances.analysis.search import FoundTransaction
 from finances.domain.models import DataSource, Transaction
 from finances.domain.spending import Flow
-from finances.mcp_server import helpers, proposals, tools
+from finances.mcp_server import helpers, proposals, reports, tools
 from finances.mcp_server import serialization as ser
 from tests.unit.test_mcp_serialization import CASES, proposal

@@ -252,7 +252,11 @@
     assert "mcp_server.tools" not in serialization and "mcp_server.server" not in serialization
     from finances.mcp_server.server import _TOOLS

-    assert all(fn.__module__ == tools.__name__ for fn, _ in _TOOLS)
+    assert all(
+        fn is getattr(tools, fn.__name__)
+        and fn.__module__ == (reports.__name__ if hasattr(reports, fn.__name__) else tools.__name__)
+        for fn, _ in _TOOLS
+    )


 def test_read_tool_helper_markers(monkeypatch):
@@ -379,7 +383,7 @@
     import hashlib

     nodes = []
-    for module in (tools, proposals, helpers):
+    for module in (tools, proposals, helpers, reports):
         tree = ast.parse(Path(module.__file__).read_text())
         for node in tree.body:
             if isinstance(node, ast.FunctionDef):
--- a/tests/unit/test_mcp_proposal_tools_behavior.py
+++ b/tests/unit/test_mcp_proposal_tools_behavior.py
@@ -9,7 +9,7 @@
 from mcp.server.mcpserver.exceptions import ToolError

 from finances.db.repositories.categories import CategoryExistsError
-from finances.mcp_server import helpers, proposals, tools
+from finances.mcp_server import helpers, proposals, reports, tools


 @pytest.fixture
@@ -208,7 +208,7 @@
     with pytest.raises(ToolError, match="^month must be a year and month, like 2026-05$"):
         helpers.month_start("2026-13")
     assert clock.call_count == 1
-    assert tools._month_start is proposals._month_start is helpers.month_start
+    assert reports._month_start is proposals._month_start is helpers.month_start


 @pytest.mark.parametrize("error", [ValueError("finding not found"), LookupError("synthetic")])
```

## Spec correction (2026-11-16)

Revision 2 corrects an architect omission in planning commit 327f62a. The initial
spec removed tools._month_start but omitted four tests calling it in two files
outside Scope. The coder correctly stopped after full acceptance reported
4757 passed, four failed; MCP's 332 passing cases alone were insufficient.
This is a specification/scope defect, not evidence to restore a private facade
alias or change implementation behavior. Preserve the existing isolated work.

This revision authorizes the two added Scope paths and only the patch below.
It supersedes the old Phase 47g given file's import/call locations, leaving every
assertion, input, error message, clock refusal and delegation count unchanged.
The canonical helpers.month_start is already the implementation used by reports
and proposals; public MCP caller tests continue covering their adapters.
N remains 4725, given count 12, minimum 4737 plus coder cases. No new tests.

The four migrated cases passed both against approved 47h2 and against a disposable
copy of the delivered 47h3 source. Both files lint/format cleanly. This targeted
validation is not full acceptance or an independent implementation approval.
No product/design decision or new dependency is involved.

Commit revised planning docs before resuming. The coder may preserve its existing
/tmp/finances-47h3-work delivery by comparing the committed old baseline to the
new planning commit and applying only planning-document changes plus this exact
test patch. Record both SHAs and confirm spec/guide match revised committed bytes;
do not reset or overwrite implementation/progress. Original editor settings and
original blocked progress remain preserved. Apply this correction patch once,
in addition to the original two-file patch:

```text
--- a/tests/unit/test_period_adapters.py
+++ b/tests/unit/test_period_adapters.py
@@ -5,7 +5,7 @@
 from typer.exceptions import Exit

 from finances.cli import reports as cli
-from finances.mcp_server import tools
+from finances.mcp_server import helpers
 from finances.web.routes import reports as web


@@ -50,5 +50,5 @@

 def test_mcp_bad_month_keeps_tool_error():
     with pytest.raises(ToolError) as stopped:
-        tools._month_start("bad")
+        helpers.month_start("bad")
     assert str(stopped.value) == "month must be a year and month, like 2026-05"
--- a/tests/integration/test_period_selection_compatibility.py
+++ b/tests/integration/test_period_selection_compatibility.py
@@ -16,7 +16,7 @@
 from finances.db.orm import TransactionRow
 from finances.db.repositories import create_account, set_category_by_hand
 from finances.domain import periods
-from finances.mcp_server import tools
+from finances.mcp_server import helpers
 from finances.mcp_server.server import build_server
 from finances.web import app as web_app
 from finances.web import periods as web
@@ -77,7 +77,7 @@
     assert web.spending_range(dict(month="", start="", end="")) == expected
     assert cli.first_day(None) == expected[0]
     assert web.first_day("") == expected[0]
-    assert tools._month_start("") == expected[0]
+    assert helpers.month_start("") == expected[0]
     assert spy.call_count == 5


@@ -99,7 +99,7 @@
     assert (
         cli.first_day("2024-02")
         == web.first_day("2024-02")
-        == tools._month_start("2024-02")
+        == helpers.month_start("2024-02")
         == date(2024, 2, 1)
     )
     with pytest.raises(ValueError, match="from must be a date"):
```

**Rerun gates:** all five Acceptance steps are live again, starting from
scripts/check.py --first mcp --workers 4, followed immediately by coverage,
given-only tests, probe and complete nine-path scope/patch checks. The added
period files run in core as well as MCP tests in mcp; selected-first still runs
the whole suite. Reuse no failed-run acceptance result or coverage. Independent
verifier runs every gate fresh against revision 2 and the same delivery bytes.
Update the existing progress entry after success, retaining the stop/correction
history; do not append a duplicate phase heading.

## Given tests

Twelve cases in `tests/unit/test_mcp_report_tools.py`, copied unchanged:

```python
from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from finances.mcp_server import tools


@pytest.mark.parametrize(
    "name",
    [
        "get_spending",
        "month_over_month",
        "get_insights",
        "get_recurring",
        "get_upcoming",
        "get_forecast",
        "get_budgets",
    ],
)
def test_facade_identity(name):
    from finances.mcp_server import reports

    assert getattr(tools, name) is getattr(reports, name)
    assert getattr(tools, name).__module__ == reports.__name__


def test_spending_json(monkeypatch):
    from finances.mcp_server import reports

    session = Mock()
    report = NS(
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        by="merchant",
        lines=[NS(label="ACME", purchases_cents=700, refunds_cents=900, spent_cents=-200, count=2)],
        summary=NS(
            spent_cents=-200,
            refunds_cents=900,
            income_cents=1100,
            transfers=3,
            unsorted_in_cents=400,
            unsorted_in_count=1,
        ),
    )
    load = Mock(return_value=report)
    monkeypatch.setattr(reports, "reading", lambda: nullcontext(session))
    monkeypatch.setattr(reports, "spending_report", load)
    assert tools.get_spending(date(2026, 1, 1), date(2026, 1, 31), "merchant") == {
        "start": "2026-01-01",
        "end": "2026-01-31",
        "by": "merchant",
        "lines": [
            {
                "label": "ACME",
                "spent_cents": 700,
                "refunds_cents": 900,
                "net_cents": -200,
                "count": 2,
            }
        ],
        "summary": {
            "spent_cents": 700,
            "refunds_cents": 900,
            "net_cents": -200,
            "income_cents": 1100,
            "transfers": 3,
            "unsorted_in_cents": 400,
            "unsorted_in_count": 1,
        },
    }
    load.assert_called_once_with(session, date(2026, 1, 1), date(2026, 1, 31), "merchant")
    assert session.mock_calls == []


@pytest.mark.parametrize("income", [False, True], ids=["charges", "income"])
@pytest.mark.parametrize("include_inactive", [False, True], ids=["active", "all"])
def test_recurring_json(monkeypatch, income, include_inactive):
    from finances.mcp_server import reports

    session = Mock()
    row = NS(
        merchant="ACME",
        cadence="month",
        amount_cents=300,
        monthly_cents=300,
        count=2,
        first_day=date(2026, 1, 1),
        last_day=date(2026, 2, 1),
        next_day=date(2026, 3, 1),
        active=False,
        previous_cents=200,
    )
    charges = Mock(return_value=[row])
    incoming = Mock(return_value=[row])
    clock = Mock(return_value=date(2026, 2, 2))
    monkeypatch.setattr(reports, "reading", lambda: nullcontext(session))
    monkeypatch.setattr(reports, "recurring_charges", charges)
    monkeypatch.setattr(reports, "recurring_income", incoming)
    monkeypatch.setattr(reports.clock, "today", clock)
    expected = {
        False: {
            "merchant": "ACME",
            "cadence": "month",
            "amount_cents": -300,
            "monthly_cents": -300,
            "count": 2,
            "first_day": "2026-01-01",
            "last_day": "2026-02-01",
            "next_day": "2026-03-01",
            "active": False,
            "previous_cents": -200,
        },
        True: {
            "merchant": "ACME",
            "cadence": "month",
            "amount_cents": 300,
            "monthly_cents": 300,
            "count": 2,
            "first_day": "2026-01-01",
            "last_day": "2026-02-01",
            "next_day": "2026-03-01",
            "active": False,
            "previous_cents": 200,
        },
    }
    assert tools.get_recurring(income, include_inactive) == {
        "as_of": "2026-02-02",
        "income": income,
        "series": [expected[income]] if include_inactive else [],
    }
    selected, unused = (incoming, charges) if income else (charges, incoming)
    selected.assert_called_once_with(session, date(2026, 2, 2))
    unused.assert_not_called()
    clock.assert_called_once_with()
    assert session.mock_calls == []
```

Validation: fresh fail47h3 at 713c911, linked venv and explicit clone/src imports;
twelve collected tests fail for the missing reports module. Five behavior cases
were independently run against original tools via temporary import substitution,
all pass. Literal spending case has refunds exceeding purchases; four recurring
cases distinguish sign, source selection and inactive filtering. No production
source, reference implementation or source stubs were authored. The given patch
applies to predecessor and lint/format checks pass.

## Tests to write

In `tests/unit/test_mcp_report_tools_behavior.py`, matched by existing mcp section:

- Full literal JSON for each remaining report: month-over-month with two ordered
  months and uncovered accounts; insights with one finding (empty subject), one
  merchant and one closed finding; upcoming with a bill and income; forecast
  with a real step and no_balance entry; budgets with group and category rows.
  Use synthetic report dataclasses or SimpleNamespace and assert exact calls
  with the same session and supplied arguments, not just returned markers.
- Spending: default period using fixed 2026-02-15 and exactly one clock call;
  explicit bounds read no clock; one-sided bounds reject before opening reading;
  reversed bounds retain existing select_period behavior; analysis ValueError
  retains original ToolError message/cause; all seven By choices forward unchanged.
- Month-over-month explicit 2026-02 forwards 2026-02-28/count=3 without clock;
  empty month forwards fixed today; malformed month raises existing ToolError
  before reading. Insights and budgets use shared first day, with default and
  explicit months; preserve budgets' additional today read rather than caching it.
- Recurring: active row retained by default, previous_cents=None remains null,
  income versus charges sources and empty result. Upcoming days=7 and forecast
  days=7/account="Test Card" forward; blank account becomes None; ValueError
  forecast error is translated with original cause, LookupError propagates.
- Read contexts close on success/error; serializers perform no session writes;
  reports never opens writing, and real public MCP read-only tests still pass.
- Structural tests: By identity through facade, report helper alias equals
  helpers.month_start, module caps, no facade/server/dynamic import dependency,
  unchanged function ASTs. Existing exact AST pin supplies broad move evidence.

R1/R5 map to identity/structure/AST tests; R2 to whole JSON and branch inputs;
R3 to argument/error/clock/context cases; R4 to inventory probe, existing public
integration and unchanged-source comparison. Cover every new-module line and
branch with behavior assertions; no coverage exemptions or dead helper code.

## Rules for this phase

Project privacy and layering apply: synthetic offline tests, stdio MCP, money as
integer cents, no live data/Keychain/aggregator or network access. Reading stays
read-only; no ledger or proposal writes are added. No dependencies, migration,
configuration or test-section change. Earlier tests change only by given patch.
Coder and verifier do not commit or push.

## Acceptance

Run sequentially in isolated planning checkout with its PYTHONPATH:

1. `.venv/bin/python scripts/check.py --first mcp --workers 4`: final
   `All checks passed.`, all sections zero failed/skipped, no xfails or warnings
   summary, critical/overall gates pass; at least **4737** full-suite passes
   (4725+12), plus coder cases. Record a resource-driven serial override if needed.
2. Immediately `.venv/bin/python -m coverage report --include="*/finances/mcp_server/reports.py" --fail-under=100`:
   module and TOTAL 100%, no missing lines/branches/partial branches.
3. `.venv/bin/python -m pytest tests/unit/test_mcp_report_tools.py --no-cov`:
   exactly twelve passed.
4. Guide probe, saved outside repository: both ok lines and `FAILURES 0`.
5. Scope/given bytes and given patch match; compare all unchanged source against
   planning SHA including server/access/helpers/proposals/serialization. Original
   function AST hashes pass with unchanged values; reports <=400 and tools <=512;
   inspect source/AST for reverse imports and dynamic wrappers including new files.

## Report

Use standard progress format, headed
`## Phase 47h3: extract MCP reporting tools (YYYY-MM-DD)`, baseline 4725 and given
12. Include full planning SHA, isolation/provenance, requirement/test mapping,
Sections table, check's last ten lines and other acceptance outputs. Record
interim size exception and no final gate yet. Honest deviations/follow-ups only.
