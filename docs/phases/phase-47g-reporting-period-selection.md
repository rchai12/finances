# Phase 47g: shared reporting period selection

## Goal

Share month-versus-range rules without changing CLI, web or MCP behavior. The
accepted remediation design section 47g settles behavior; no new owner decision
is required. Architect decisions (2026-11-16): five small public domain units,
two thin shared adapters, existing caller wrappers, nineteen given cases and a
coder-owned compatibility matrix. Estimated production diff below 300 lines;
no split is needed for this bounded set of callers.

## Read first

AGENTS.md, docs/architecture.md, docs/testing.md, docs/phase-conventions.md,
docs/progress.md, docs/audit-remediation-design.md (47g), domain/periods.py and
domain/spending.py under src/finances; CLI reports/export, web routes reports/export,
web/helpers.py and mcp_server/tools.py under the same package. Read existing
report/export/month/MCP tests before editing.

## Starting state and checked facts

47f is approved and committed at `666e035a66e2bbf311c016ddb72e5dbd5e962968`.
N = **4583** from progress and PASS review. **Sections: core,cli,web,mcp.**
Migration remains 0026_proposal_findings.py. domain/periods.py already exists;
preserve its coverage/calendar functions. No touched module is critical.

CLI _range treats month is not None as supplied (including empty string). Web
_spending_range treats empty strings as absent. Both check conflicting selection,
then incomplete endpoints, before parsing month. Web checks completeness before
_day validates from, then to. CLI datetimes are parsed by Typer first. Reversed
ranges pass selection and are refused by the existing report validator.

Captured predecessor behavior using synthetic arguments and controlled 2024-02-15:

| Input | CLI stderr/exit | Web adapter |
|---|---|---|
| no selection | Feb 1–29 | Feb 1–29 |
| empty month | Error: month must be a year and month, like 2026-05; exit 1 | Feb 1–29 |
| bad month plus one endpoint | Error: give --month, or --from and --to, not both; exit 1 | give a month, or from and to, not both |
| one endpoint | Error: give both --from and --to; exit 1 | give both from and to |
| bad from, empty to | Typer handles date input | give both from and to |
| bad from, valid to | Typer handles date input | from must be a date as YYYY-MM-DD |

MCP _month_start accepts empty string as default and translates malformed month
to ToolError with existing month_range text. get_spending has typed endpoints,
no month argument, and incomplete endpoints yield ToolError("give both start and
end, or neither"). Existing schema guards run at their current positions.

Nineteen given cases collected in isolated predecessor clone: eleven fail for
missing domain APIs, eight characterization guards pass after checking the actual
Typer Exit type. Lint/format pass. No feature or reference implementation built.

### Baseline isolation

Owner commits finalized planning docs before coding. Preserve unrelated untracked
.vscode/settings.json. Use a fresh isolated clone of that planning commit, link
and locally exclude existing venv symlink, set PYTHONPATH to clone/src on every
Python command, verify finances.__file__ provenance, record full baseline SHA and
confirm spec/guide match HEAD with clean starting status. Follow
.agents/skills/phase-architect/references/handoffs.md.

## Scope

| Path | What changes |
|---|---|
| src/finances/domain/periods.py | five units below; existing functions unchanged |
| src/finances/cli/periods.py | new shared report/export adapter |
| src/finances/cli/reports.py | delegate range/first-day selection |
| src/finances/cli/export.py | import shared adapter directly |
| src/finances/web/periods.py | new shared spending/first-day adapter |
| src/finances/web/routes/reports.py | import shared adapters |
| src/finances/web/routes/export.py | import shared spending adapter directly |
| src/finances/mcp_server/tools.py | get_spending and _month_start selection only |
| tests/unit/test_period_selection.py | new: given eleven cases |
| tests/unit/test_period_adapters.py | new: given eight guards |
| tests/integration/test_period_selection_compatibility.py | new: coder matrix |
| docs/progress.md | append phase entry |

New tests fall in core; first-run sections include every affected boundary. No
section configuration change, earlier-test diff, migration or dependency.

## Out of scope

Budget/account-page period parsing, transaction search, months-report end-month
selection, local clocks, money/report validation, other private cross-route
helpers, tools splitting, schemas/options/messages, and other audit parts. Preserve
CLI findings' existing _first_day import compatibility rather than sweeping it
into cleanup. YEAR_REFUSED remains imported as before by export.

## Design and requirements

- **R1.** In domain/periods add frozen `Period(start: date, end: date)` and
  `PeriodError(ValueError)` with constructor `(code, message)` and `code` typed
  Literal["conflict", "incomplete", "month"]. str(error) is exactly message.
  No CLI/HTTP/MCP/clock imports or option labels in domain.
- **R2.** Add `validate_selection(*, month_present: bool, start_present: bool,
  end_present: bool) -> None`. First conflict (month and either endpoint) raises
  PeriodError("conflict", "month cannot accompany endpoints"); then unequal
  endpoint presence raises PeriodError("incomplete", "both endpoints are required").
  Otherwise return None. This preflight lets web preserve parse-error precedence
  without copying selection rules.
- **R3.** Add `select_period(*, today: date, month: str | None = None,
  start: date | None = None, end: date | None = None) -> Period`. Use R2 with
  presence defined by is not None. Month supplied: reuse month_range; translate
  its ValueError to PeriodError("month", str(error)). Full range: return inclusive
  endpoints unchanged, even reversed. No selection: month_bounds(today). No clock
  reads or new date validation.
- **R4.** Add `first_day(month: str | None, *, today: date) -> date`, using shared
  selection and returning its start. Empty string is a supplied malformed month
  in domain. No duplicated month parsing.
- **R5.** CLI periods.py exposes `spending_range(month: str | None,
  start: datetime | None, end: datetime | None) -> tuple[date,date]` and
  `first_day(month: str | None) -> date`. Convert datetimes to dates. Translate
  conflict/incomplete to existing CLI texts above through fail(); month error uses
  its existing message. Preserve CLI empty-month refusal. Use clock.today() for
  defaults only; explicit selections must not require a real calendar read (an
  unused today placeholder is permitted). Reports re-exports these as _range and
  _first_day for existing seams/imports; export imports spending_range directly.
- **R6.** Web periods.py exposes `spending_range(form: dict[str,str]) ->
  tuple[date,date]` and `first_day(text: str) -> date`. Shared R2 preflight on bool
  strings precedes _day(start,"from"), then _day(end,"to"). Normalize empty
  month/endpoints to None after presence checks. Translate conflict/incomplete to
  exact existing web ValueError texts above; retain _day/month errors verbatim.
  Default calendar source remains web.app._today. Reports imports aliases
  _spending_range/_month_start; export imports shared spending_range directly.
  Preserve existing page/export error status, form values and text.
- **R7.** MCP get_spending selects with month absent and typed dates; incomplete
  maps to its exact ToolError above, and reversed dates still reach spending_report
  validation. _month_start uses domain first_day with month or None and preserves
  ToolError translation/default clock.today. No month parameter on get_spending,
  no schema/permission/other-tool behavior change. Keep month_range for the
  unrelated month_over_month path; do not sweep it into this refactor.
- **R8.** Existing report validation order, defaults, error types/text/exit/status,
  selected rows and report/export parity remain identical. Preserve all existing
  period helpers, tests and caller patch seams. Shared adapters contain input/error
  translation only; common structural/calendar logic lives in domain. No new
  parsing, range reversal, silent normalization or rule changes.

## Given tests

Nineteen cases; copy both unchanged. Eleven are missing-API failures on predecessor,
eight already-passing boundary guards. No names-only implementation is supplied.

`tests/unit/test_period_selection.py`

```python
from datetime import date

import pytest

from finances.domain import periods


@pytest.mark.parametrize(
    ("month", "start", "end", "expected"),
    [
        (None, None, None, (date(2024, 2, 1), date(2024, 2, 29))),
        ("2025-02", None, None, (date(2025, 2, 1), date(2025, 2, 28))),
        ("2025-12", None, None, (date(2025, 12, 1), date(2025, 12, 31))),
        ("2026-01", None, None, (date(2026, 1, 1), date(2026, 1, 31))),
        (None, date(2025, 1, 2), date(2025, 1, 3), (date(2025, 1, 2), date(2025, 1, 3))),
        (None, date(2025, 1, 3), date(2025, 1, 2), (date(2025, 1, 3), date(2025, 1, 2))),
    ],
    ids=["leap-default", "month", "december", "january", "range", "reversed-deferred"],
)
def test_select_period(month, start, end, expected):
    result = periods.select_period(month=month, start=start, end=end, today=date(2024, 2, 15))
    assert (result.start, result.end) == expected


@pytest.mark.parametrize(
    ("month", "start", "code", "message"),
    [
        ("bad", date(2024, 1, 1), "conflict", "month cannot accompany endpoints"),
        (None, date(2024, 1, 1), "incomplete", "both endpoints are required"),
        ("", None, "month", "month must be a year and month, like 2026-05"),
    ],
    ids=["conflict-first", "incomplete", "empty-is-month"],
)
def test_selection_errors(month, start, code, message):
    with pytest.raises(periods.PeriodError) as stopped:
        periods.select_period(month=month, start=start, end=None, today=date(2024, 2, 15))
    assert stopped.value.code == code
    assert str(stopped.value) == message


@pytest.mark.parametrize("month", [None, "2024-02"], ids=["default", "explicit"])
def test_first_day(month):
    assert periods.first_day(month, today=date(2024, 2, 15)) == date(2024, 2, 1)
```

`tests/unit/test_period_adapters.py`

```python
from datetime import date, datetime

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from typer.exceptions import Exit

from finances.cli import reports as cli
from finances.mcp_server import tools
from finances.web.routes import reports as web


@pytest.mark.parametrize(
    ("month", "start", "message"),
    [
        ("", None, "Error: month must be a year and month, like 2026-05\n"),
        ("bad", datetime(2024, 1, 1), "Error: give --month, or --from and --to, not both\n"),
        (None, datetime(2024, 1, 1), "Error: give both --from and --to\n"),
    ],
    ids=["empty", "conflict", "incomplete"],
)
def test_cli_period_refusals(month, start, message, capsys):
    with pytest.raises(Exit) as stopped:
        cli._range(month, start, None)
    assert stopped.value.exit_code == 1
    assert capsys.readouterr().err == message


@pytest.mark.parametrize(
    ("month", "start", "end", "message"),
    [
        ("bad", "bad", "", "give a month, or from and to, not both"),
        ("", "bad", "", "give both from and to"),
        ("", "bad", "2024-02-01", "from must be a date as YYYY-MM-DD"),
    ],
    ids=["conflict", "incomplete-before-date", "bad-day"],
)
def test_web_period_refusals(month, start, end, message):
    with pytest.raises(ValueError) as stopped:
        web._spending_range({"month": month, "start": start, "end": end})
    assert str(stopped.value) == message


def test_web_empty_month_defaults(monkeypatch):
    monkeypatch.setattr(web.web_app, "_today", lambda: date(2024, 2, 15))
    assert web._spending_range({"month": "", "start": "", "end": ""}) == (
        date(2024, 2, 1),
        date(2024, 2, 29),
    )


def test_mcp_bad_month_keeps_tool_error():
    with pytest.raises(ToolError) as stopped:
        tools._month_start("bad")
    assert str(stopped.value) == "month must be a year and month, like 2026-05"
```

## Tests to write

`tests/integration/test_period_selection_compatibility.py` (core):

- R2/R3: all eight presence combinations for preflight; conflict wins over incomplete
  and malformed month. Both partial endpoint directions, malformed/invalid numeric
  months and first-day errors. Assert exact code/text, immutable Period, and no
  clock/frontend imports. Verify valid explicit range and reversed unchanged.
- R5/R6/R7: spies prove all scoped adapters delegate to shared domain selection;
  web preflight runs before malformed date parsing, from before to. A controlled
  local date changes defaults across a December/January boundary; explicit inputs
  do not read calendar clocks. Keep CLI empty versus web/MCP empty distinction.
- R8: public CLI spending/export spending and web reports/export spending matrix
  for defaults, valid month/range, leap February, conflict, partial range, malformed
  month/day and reversed range. Synthetic DB transactions immediately before, on
  each endpoint and after it establish inclusive selection and identical report/
  exported rows and dates. Pin exact CLI stderr/exit, web status/form text and CSV
  error/download behavior from existing boundary tests; do not invent uniform
  status codes where reports/export differ. Preserve schema-not-migrated precedence.
- R7/R8: actual in-memory MCP get_spending and at least one _month_start caller
  cover default/explicit/invalid/incomplete/reversed input, ToolError and unchanged
  schemas; reuse existing tests/support helpers and schema pins. Verify no new
  month parameter and read-only session behavior. Other month-start callers reuse
  the unchanged wrapper and full existing suite must pass.

No relaxed assertions, removed tests, real data, network, new fixtures or packages.

## Acceptance

Sequentially from isolated checkout, preserve actual output and exit codes:

1. `.venv/bin/python scripts/check.py --first core,cli,web,mcp --workers 4`:
   All checks passed.; at least **4602** full-suite passes (4583+19 plus coder
   cases), every section zero failures/skips, no xfails or warnings summary.
   Serial override needs recorded resource reason; one coverage job per checkout.
2. Immediately `.venv/bin/python -m coverage report --include="*/finances/domain/periods.py,*/finances/cli/periods.py,*/finances/web/periods.py" --fail-under=100`:
   each listed file and TOTAL 100%, no missing lines/branches. Existing critical
   and configured overall thresholds remain mandatory.
3. `.venv/bin/python -m pytest tests/unit/test_period_selection.py tests/unit/test_period_adapters.py --no-cov`:
   exactly nineteen passed.
4. Status/diff HEAD only Scope paths plus authorized verifier report; given bytes
   identical, all existing tests unchanged. No search gate or independent probe.

## Report

Use phase-conventions format headed Phase 47g: shared reporting period selection.
Record actual N/final/given counts, new domain/adapter contracts, boundary matrix
and parity evidence, full planning baseline/import provenance. No commit/push.
