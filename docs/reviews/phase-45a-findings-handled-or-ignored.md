# Review: Phase 45a

- Verdict: PASS
- Passed: 4268
- Findings: 0
- Approved deviations: `FindingStatusRow.subject` uses `String(NAME_LIMIT)` so the ORM source has no `String(100)` literal; the four given test files contain 38 tests; extra tests for stored month, reopen-month, list order, a cut subject, dashboard and `get_insights`, empty form month, History who, unknown type, a bad form month, and a forged token
- For the architect: The History page's `change_link` has no entry for kind `finding` (same gap as `proposal`, `alias`, `settlement`). CLI audit lists the rows. Given tests are 38, not 37.

## Findings

None

Parts that needed a repair: `FindingStatusRow.subject` used `String(NAME_LIMIT)` after `test_the_orm_names_its_widths_by_constant` failed on a `String(100)` literal; forged-form extra tests covered `refused()` on both POST routes so the include coverage report reached 100%.

Built beyond the spec: extra tests for a forged form token, an unknown type on `reopen_finding`, and a bad month on the form.

## Gates

- `scripts/check.py --first migrations,core,cli,web`: last line `All checks passed.`; summary lists `tests (migrations,core,cli,web): passed` then `tests: passed`; 4268 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table; first stage 2881 passed
- Given tests: `38 passed` (the four given files as written; the guide said 37)
- Coverage include report: `TOTAL 1033 0 124 0 100%`
- `git diff --stat HEAD -- tests`: `tests/support.py` and the five files of the given diff, no other
- `git grep -n "^from finances\.\(db\|analysis\|views\|cli\|web\)" -- src/finances/domain/findings.py`: no output

`git status --short` lists the spec's Scope paths, `docs/progress.md`, `docs/reviews/phase-45a-findings-handled-or-ignored.md`, and local `.vscode/` (not part of the phase). The given test files and the six-file test diff match the spec.

## Requirement checklist

- R1: gate 2 (`test_migration_0025.py`)
- R2: gate 2 (`test_finding_rules.py`); gate 5
- R3: gate 1 (`test_audit_rules.py`, `test_cli_audit.py`)
- R4: gate 2 (`test_history_records_each_change`, the refusals); gate 1 (`test_repositories_split.py`); `test_ignored_stores_no_month_and_handled_stores_the_month`, `test_reopening_june_leaves_a_may_handled_status`, `test_list_finding_statuses_is_ordered_by_id`, `test_a_subject_longer_than_100_is_cut`
- R5: gate 2 (`test_handling_a_finding_moves_it_below`, `test_a_refusal`); `test_the_dashboard_leaves_out_a_handled_finding`, `test_get_insights_lists_only_open_findings`
- R6: gate 2 (the `Handled or ignored` rows)
- R7: gate 2 (`test_cli_findings.py`)
- R8: gate 2 (`test_web_findings.py`); gate 1 (`test_web_insights.py`, `test_web_split.py`); `test_an_empty_month_on_the_form_uses_this_month`
- R9: gate 4; only those files

## Tests to write

- `set_finding_status` stores month None for ignored and the finding's month for handled, and refuses `done`: `test_ignored_stores_no_month_and_handled_stores_the_month`
- `reopen_finding` with June leaves a handled status of May in place: `test_reopening_june_leaves_a_may_handled_status`
- `list_finding_statuses` is ordered by id: `test_list_finding_statuses_is_ordered_by_id`
- a subject longer than 100 characters is cut to 100: `test_a_subject_longer_than_100_is_cut`
- the dashboard's top findings leave out a handled finding: `test_the_dashboard_leaves_out_a_handled_finding`
- `get_insights` for May, with the spike handled, lists four findings: `test_get_insights_lists_only_open_findings`
- `POST /findings/status` with an empty month uses this month: `test_an_empty_month_on_the_form_uses_this_month`
- History through the web: who is `person`: `test_history_through_the_web_is_a_person`

## Spot checks

Each deciding test failed under the named change. Restored from `/tmp/fin-45a-spots/copies/`, not `git checkout`. SPOT_FAILURES 0.

| Change | Deciding test | Result |
|---|---|---|
| 1. `status_of`: the first matching status wins | `test_the_status_of_a_finding` (handled May, then ignored) | failed |
| 2. `status_of`: handled matched in any month | `test_handled_holds_for_that_month_only` (June) | failed |
| 3. `set_finding_status`: an ignored status stored with its month | `test_ignored_stores_no_month_and_handled_stores_the_month` | failed |
| 4. `find_finding`: subject compared exactly | `test_handling_a_finding_moves_it_below` (`dining`) | failed |
| 5. `reopen_finding`: only the month's handled row removed | `test_reopening_a_finding` (ignored in May, reopened from June) | failed |
| 6. `split_findings`: the closed list in the statuses' order | `test_splitting_keeps_the_order` | failed |
| 7. `insights_report`: `findings` still holds every finding | `test_handling_a_finding_moves_it_below` | failed |
| 8. `set_finding_status`: no check for a status already set | `test_a_finding_with_a_status_is_refused` (ignore, then handle) | failed |
| 9. no History record on reopen | `test_history_records_each_change` | failed |
| 10. the redirect's month from the form instead of the finding | `test_an_empty_month_on_the_form_uses_this_month` | failed |

## Out of scope

Absent: a change to `mcp_server`; buttons on the dashboard; `fin findings list`; a status on a merchant stat or a recurring charge.

## Probe

None.
