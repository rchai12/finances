# Verify Phase 47g: shared reporting period selection

Spec: docs/phases/phase-47g-reporting-period-selection.md. Read AGENTS.md and
phase-conventions. Independently verify; write only
`docs/reviews/phase-47g-reporting-period-selection.md`.

## Baseline

Confirm 47f approved at 666e035 with 4583 passes. Final spec/guide must be committed
and match HEAD; expected implementation/progress exist. Missing implementation is
a baseline blocker. Inspect status/diff before report; use isolated planning clone
and verify finances import provenance. Preserve unrelated editor settings; compare
reviewed bytes to delivered bytes before transporting verdict.

## 1. Gates

Run the four spec acceptance steps exactly, starting
`.venv/bin/python scripts/check.py --first core,cli,web,mcp --workers 4`.
Require at least 4602 full-suite passes plus coder cases, clean section table,
All checks passed. and critical gates. Immediately run specified coverage: all
three modules and TOTAL 100% with no missing branches/lines. Then nineteen given
passes and scope/byte equality. Resolve localhost sandbox limits through execution
permission, retain actual outcomes, never weaken tests. No real samples.

## 2. Scope

Only twelve listed Scope paths plus this report. No existing test/configuration,
critical module, migration, permission, option/schema or clock change. Domain's
existing functions stay unchanged. Unrelated budget/account/month-over-month/search
parsing stays outside scope. Existing private aliases are intentional compatibility
seams; shared report/export adapters are imported directly by export callers.

## 3. Requirements

| Id | Deciding evidence |
|---|---|
| R1 | Frozen result fields, typed error code/message; domain pure with explicit today. |
| R2 | Given conflict-first plus coder eight-combination preflight matrix; no date parsing before structural errors. |
| R3 | Six given select cases and three error cases; month_range reuse, inclusive/reversed preservation, leap/year transitions. |
| R4 | Two given first-day cases, malformed/empty error coverage and actual shared delegation. |
| R5 | Three CLI given refusals, public report/export matrix, exact Error text/newline/exit and Typer parsing precedence; old aliases work. |
| R6 | Four web given guards, public report/export status/form/CSV matrix; completeness before _day and from before to, empty month defaults. |
| R7 | Given MCP ToolError guard, public spending/month-start matrix, schemas/read-only preserved, no month argument. |
| R8 | Complete synthetic endpoint-row parity, controlled local dates, existing full suite; no normalization or reordered report validation. |

Every Tests to write bullet needs a concrete named case. Characterization guards
alone cannot prove new sharing: inspect bodies and delegation spies. Public tests
must exercise actual report/export adapters and persisted synthetic data.

## 4. Probe

None. Literal domain results, adapter guards and public boundary/parity matrix
provide independent evidence. No new search gate; inspect source directly.

## 5. Scratch-only spot checks

Run each mutation in a separate disposable copy with confirmed import provenance;
never change reviewed source. Given prefixes are tests/unit/test_period_selection.py::
and tests/unit/test_period_adapters.py:: respectively.

| Mutation | Given test | Correct | Broken |
|---|---|---|---|
| select_period: reverse supplied reversed endpoints | test_select_period[reversed-deferred] | Jan 3 then Jan 2 | Jan 2 then Jan 3 |
| validate_selection: incomplete before conflict | test_selection_errors[conflict-first] | code conflict | code incomplete |
| CLI adapter: normalize empty month to None | test_cli_period_refusals[empty] | Exit 1 with exact month message | default result |
| web adapter: _day before shared preflight | test_web_period_refusals[incomplete-before-date] | give both from and to | from date error |
| domain default: assume February has 28 days | test_select_period[leap-default] | Feb 29 | Feb 28 |

Trace through final call path; each decides a distinct rule. A guard that blocks a
mutation for an unrelated reason is not proof. Do not implement a reference feature.

## 6. Variations and verdict

Internal helpers/aliases and error translation tables are coder choices. Unused
explicit-today placeholders are allowed when preserving no real clock read on
explicit input. Domain error codes, public signatures, adapter text and precedence
are fixed. No new universal reversed-range refusal or whitespace stripping.

Use standard report header/findings, fresh gate table/Sections/final ten lines,
requirement/test mapping, scope and spot results. Distinguish baseline/environment,
spec/test and implementation failures. On FAIL send requirement, observation and
required result; no repair, commit, push or future-phase work.
