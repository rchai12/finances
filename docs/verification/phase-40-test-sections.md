# Verify Phase 40: test sections

Spec: `docs/phases/phase-40-test-sections.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder gave `scripts/check.py` eight test sections read from `tests/sections.toml`: a table of each section's counts after a full run's tests, `--first A,B` to test a phase's own sections first and run everything else only once they pass, and `--section NAME` to run one section alone. A section list, a diff to one earlier test, and one test file were given.

These are correct and must not be reported: private helpers inside `check.py`; the JUnit report read with `xml.etree.ElementTree`; the temporary folder of a section run made the same way as the full run's.

## 1. Gates

N is `4028` when Phase 39 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 34 passed, 0 failed, 0 skipped, 0 xfailed; a `Sections:` table after the tests with eight lines, 0 failed on each, whose passed counts add up to the tests step's |
| `.venv/bin/python -m pytest tests/unit/test_sections.py --no-cov` | exactly `34 passed` |
| `.venv/bin/python -m pytest tests/unit/test_check_script.py tests/unit/test_sections.py tests/unit/test_sections_more.py -o addopts="" --import-mode=importlib --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | only `tests/unit/test_check_script.py` |
| `.venv/bin/python scripts/check.py --section scripts` | last line `Section scripts: passed.`, and seconds, not minutes |
| `.venv/bin/python scripts/check.py --first scripts` | last line `All checks passed.`; the summary lists `tests (scripts): passed` before `tests: passed` |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, `docs/testing.md`, `scripts/check.py`, `tests/unit/test_check_script.py`, and as new: `tests/sections.toml`, `tests/unit/test_sections.py`, `tests/unit/test_sections_more.py`. The section list, the given test file, and the test diff equal the spec's; `docs/testing.md` has the spec's line and paragraph.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_the_sections_keep_their_order`, `test_the_first_section_that_matches_wins`, `test_a_file_that_no_section_takes_is_refused`, `test_each_outcome_is_counted_in_its_files_section`, `test_the_table`); the coder's both-children case | pass |
| R2 | gate 2 (`test_the_shipped_sections`, `test_a_file_in_each_shipped_section`, `test_every_shipped_section_takes_a_test_file`) | pass |
| R3 | gate 2 (`test_a_full_run_prints_the_table_after_the_tests`, `test_failing_tests_still_print_the_table`); gate 1; the coder's no-report and real-samples cases | pass |
| R4 | gate 2 (the four section tests and the six first tests); gates 5 and 6; the coder's duplicate-name and real-samples cases | pass |
| R5 | gate 3; the coder's exit-code case | pass |
| R6 | read `check.py` | the sections file read in each run, not at import |
| R7 | gate 4 | only that file |
| R8 | read `docs/testing.md` | the line and the paragraph as given |

## 4. Probe

One by hand, outside the repository's tests: in a scratch clone, add `assert False` to one test in `tests/integration/test_web_menus.py`, run `.venv/bin/python scripts/check.py`, and see the `web` line show `1 failed` with its rerun command while the other seven show 0; run that rerun command and see `Section web: FAILED.`; run `.venv/bin/python scripts/check.py --first web` and see it stop at `tests (web)` without the full run. Then add `import nosuchmodule` at the top of `tests/unit/test_money.py` instead, and see the full run still reach every section, with `core` failed. Delete the clone afterwards.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `section_of`: the last matching section | given `test_the_first_section_that_matches_wins` (`integration/test_web_pages.py`, matched by `web` and `core`) | `web` | `core` |
| 2. `tally`: an empty `classname` skipped | given `test_each_outcome_is_counted_in_its_files_section` (`tests.unit.test_broken`) | core 1 failed | core 0 failed |
| 3. `tally`: the module taken from the last part of `classname` | the same test (`tests.integration.test_web_pages.TestPages`) | web 2 passed | web 1 passed |
| 4. `tally`: an `error` child counted as passed | the same test (`test_c`) | web 2 failed | web 1 failed |
| 5. `section_lines`: the rerun suffix on every line | given `test_the_table` (`migrations`, 0 failed) | no suffix | suffix |
| 6. `main`: the table only when the tests pass | given `test_failing_tests_still_print_the_table` | the `mcp` line with its rerun | no table |
| 7. `main --section`: coverage left on | given `test_a_section_runs_only_its_own_files` | `--no-cov` | missing |
| 8. `main --section`: every test file | the same test (`tests/unit/test_money.py`) | absent | present |
| 9. `steps`: no `--continue-on-collection-errors` | given diff (`test_the_steps_in_order`) | present | missing |
| 10. `main --first`: a failing first stage does not stop the check | given `test_a_failing_first_section_stops_the_check` | one pytest run, `Check failed at: tests (web)` | two runs |
| 11. `main --first`: the first stage's table holds every section | given `test_the_first_sections_pass_then_everything_runs` | the web line, then `== tests` | eight lines |
| 12. `section_files`: only the first name used | given `test_two_sections_first` (`parsers,sync`) | both files | no `test_simplefin.py` |
| 13. `steps`: the first stage measured for coverage | given `test_the_steps_with_sections_first` | `--no-cov` | missing |

## 6. Out of scope

Each must be absent: a moved or renamed test file; markers; changes to `tests/conftest.py`, `pyproject.toml`, or `docs/phase-conventions.md`; a parallel runner; a coverage gate per section.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
