# Review: Phase 40

- Verdict: PASS
- Passed: 4069
- Findings: 0
- Approved deviations: None
- For the architect: update `docs/phase-conventions.md` and this skill's guide gates as the spec's last note asked, now that 40 passed

## Findings

None

Parts that needed a repair: none.

Built beyond the spec: extra tests for `run_command`'s exit code, a full run with no JUnit report, forward-slash section paths, the table once under `--real-samples`, `--first web,web` without duplicate files, `--first scripts --real-samples` step order, and a `testcase` with both `failure` and `skipped`.

## Gates

- `scripts/check.py`: `4069 passed`, last line `All checks passed.` (N + 34 = 4062). Sections table after tests, eight lines, 0 failed on each; passed counts 173+66+832+429+130+852+284+1303 = 4069
- Given tests: `34 passed`
- Coverage of `scripts`: `Required test coverage of 100% reached. Total coverage: 100.00%`
- `git diff --stat HEAD -- tests`: only `tests/unit/test_check_script.py`
- `scripts/check.py --section scripts`: last line `Section scripts: passed.` (66 passed in 0.92s)
- `scripts/check.py --first scripts`: last line `All checks passed.`; summary lists `tests (scripts): passed` then `tests: passed`
- Given `tests/sections.toml` matches the spec block
- Given `tests/unit/test_sections.py` matches the spec block
- Given diff to `tests/unit/test_check_script.py` matches the spec
- `docs/testing.md` has the two command lines and the paragraph as given

`git status --short` lists `docs/progress.md`, `docs/testing.md`, `scripts/check.py`, `tests/unit/test_check_script.py`, new `tests/sections.toml`, `tests/unit/test_sections.py`, `tests/unit/test_sections_more.py`, and this review. `.vscode/` is local editor config and is not part of the phase.

## Requirement checklist

- R1: gate 2 (`test_the_sections_keep_their_order`, `test_the_first_section_that_matches_wins`, `test_a_file_that_no_section_takes_is_refused`, `test_each_outcome_is_counted_in_its_files_section`, `test_the_table`); `test_a_case_with_failure_and_skipped_counts_as_failed`
- R2: gate 2 (`test_the_shipped_sections`, `test_a_file_in_each_shipped_section`, `test_every_shipped_section_takes_a_test_file`)
- R3: gate 2 (`test_a_full_run_prints_the_table_after_the_tests`, `test_failing_tests_still_print_the_table`); gate 1; `test_a_full_run_without_a_junit_report_prints_no_table`, `test_real_samples_print_the_table_once_after_tests`
- R4: gate 2 (four section tests and six first tests); gates 5 and 6; `test_first_with_a_name_twice_runs_the_files_once`, `test_first_with_real_samples_keeps_the_later_steps`
- R5: gate 3; `test_run_command_returns_the_exit_code`
- R6: `SECTIONS_FILE.read_text` in `section_files`, `_print_table`, and `_section_names` (called from `main`), not at import
- R7: gate 4
- R8: `docs/testing.md` Commands block and the paragraph after it

## Tests to write

- `run_command` exit 3: `test_run_command_returns_the_exit_code`
- full run with no JUnit report: `test_a_full_run_without_a_junit_report_prints_no_table`
- forward slashes: `test_section_file_names_use_forward_slashes`
- `--real-samples` table once after tests: `test_real_samples_print_the_table_once_after_tests`
- `--first web,web` files once: `test_first_with_a_name_twice_runs_the_files_once`
- `--first scripts --real-samples` steps: `test_first_with_real_samples_keeps_the_later_steps`
- failure and skipped child counts as failed: `test_a_case_with_failure_and_skipped_counts_as_failed`

## Spot checks

Each deciding test failed under the named change. Restored from `/tmp/fin-40-spots/check.py`, not `git checkout`. SPOT_FAILURES 0.

| Change | Deciding test | Result |
|---|---|---|
| 1. `section_of`: last matching section | `test_the_first_section_that_matches_wins` | failed |
| 2. `tally`: empty `classname` skipped | `test_each_outcome_is_counted_in_its_files_section` | failed |
| 3. `tally`: module from last part of `classname` | the same test | failed |
| 4. `tally`: `error` child counted as passed | the same test | failed |
| 5. `section_lines`: rerun suffix on every line | `test_the_table` | failed |
| 6. `main`: table only when tests pass | `test_failing_tests_still_print_the_table` | failed |
| 7. `main --section`: coverage left on | `test_a_section_runs_only_its_own_files` | failed |
| 8. `main --section`: every test file | the same test | failed |
| 9. `steps`: no `--continue-on-collection-errors` | `test_the_steps_in_order` | failed |
| 10. `main --first`: failing first stage does not stop | `test_a_failing_first_section_stops_the_check` | failed |
| 11. `main --first`: first table holds every section | `test_the_first_sections_pass_then_everything_runs` | failed |
| 12. `section_files`: only the first name used | `test_two_sections_first` | failed |
| 13. `steps`: first stage measured for coverage | `test_the_steps_with_sections_first` | failed |

## Out of scope

Absent: a moved or renamed test file; markers; changes to `tests/conftest.py`, `pyproject.toml`, or `docs/phase-conventions.md`; a parallel runner; a coverage gate per section.

## Probe

Scratch copy at `/tmp/fin-40-probe` (deleted afterwards). A failing web test showed `web` with `1 failed` and its rerun command, the other seven with 0 failed; `--section web` ended `Section web: FAILED.`; `--first web` stopped at `tests (web)` with `tests: not run`. A collection error in `tests/unit/test_money.py` still printed all eight section lines, with `core` failed. Lint in that copy refused a bare `assert False` (B011) and an unused `import nosuchmodule` (F401), so the probe used `assert 1 == 0` and `import nosuchmodule  # noqa: F401` to reach the tests step.
