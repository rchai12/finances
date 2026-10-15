# Review: Phase 13c

- Verdict: PASS
- Passed: 2533
- Findings: 0
- Approved deviations: None
- For the architect: (1) Spot check 2 (the page lists inactive recurring charges) failed no given test, since the given data has no stopped series; the coder added `tests/integration/test_web_insights_more.py` for it. (2) Only `test_a_month` was failing-first for R1; `test_a_yearly_plan_charged_before_the_window_still_overlaps` passed before the fix, because the April window (January to April) already holds the yearly charge of 8 January. A March 2026 report, or a yearly charge in December 2025, would make it fail first.

## Findings

None after the repair. The first pass had one:

`R4 | tests/integration/test_web_insights.py | expected a test failing when inactive recurring charges are listed | found none (spot check 2 passed all 9 given tests)`

Parts that needed a repair: R4's "active only" had no test; `tests/integration/test_web_insights_more.py` adds `test_only_active_recurring_charges_are_listed`, which fails under spot check 2.

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2533 passed`, `All checks passed.` (N + 9 = 2532; 1 more is the coder's)
- Given tests: `9 passed`
- Phase 13b's given tests: `21 passed`, unchanged
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Both searches: no output
- Scope: `git status --short` lists exactly the guide's paths, plus `tests/integration/test_web_insights_more.py` (listed in the report) and this review
- Given files: `tests/support.py`, `layout.html`, `insights.html`, and `tests/integration/test_web_insights.py` are identical to the spec's blocks; `docs/testing.md` gains exactly the given rule 8

## Requirement checklist

- R1, R3 to R5: the given tests pass. `test_a_month` failed on the overlap row before the fix (QUUX CLOUD missing) and passes after.
- R1: `git diff HEAD -- src/finances/analysis/insights.py` changes one line: the category map reads `load_flows(session, date.min, last)` instead of the four loaded months.
- R2: `insights_command` prints `insights_heading(report)`; Phase 13b's given tests pass unchanged.
- R6: `GET /insights` opens one `_reading()` session (none when the month is refused); no `@api.post` added; no sums or sorting.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the tests run, and the code restored.

1. The category map uses only the four months again: `test_a_month` fails.
2. The page lists inactive recurring charges: no given test fails (the finding above); after the repair `test_only_active_recurring_charges_are_listed` fails.
3. A bad month answers `200`: all three cases of `test_a_month_that_is_not_one` fail.
4. The month field loses what was typed after a refusal: all three cases of `test_a_month_that_is_not_one` fail.
5. The Insights entry is missing from the menu on other pages: `test_the_menu_has_insights` fails.

## Out of scope

Absent: JavaScript; a `POST` route; changes to existing tests; any other change to findings or recurring charges.
