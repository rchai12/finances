# Review: Phase 16g

- Verdict: PASS
- Passed: 2763
- Findings: 0
- Approved deviations: None
- For the architect: a given upload test that sends a Windows path does not reach the route with folders intact under TestClient; pin `_upload_name` (or an equivalent) in a coder test when the spot check is "stored name keeps folders".

## Findings

None

Parts that needed a repair: spot check 1 had no failing test until `test_upload_name_drops_folders` was added (TestClient strips `C:\...` and `import_statement` uses `Path.name` on Unix paths).

Built beyond the spec: none.

## Gates

- `scripts/check.py`: `2763 passed`, `All checks passed.` (N + 23 = 2751; 12 more are the coder's)
- Given tests: `23 passed`
- Earlier bulk and import: `tests/integration/test_web_accounts_and_bulk.py tests/e2e/test_cli_import.py`, all passed
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- All three searches: no output
- Scope: `git status --short` lists the guide's 11 paths, plus this review
- Given files: `layout.html`, `statements.html`, and the three given test files match the spec's blocks

## Requirement checklist

- R1: bulk route (`app.py:840`) reads `await request.form(max_fields=1100)`; given bulk-limit tests pass.
- R2: `statement_gaps` (`periods.py:33`) joins overlapping or touching periods; given unit tests pass.
- R3: `statement_gap_lines` (`analysis/statements.py:19`); `test_statement_gap_lines_orders_accounts_and_includes_inactive`.
- R4, R5: `statement_rows` / `gap_rows` / `import_rows` (`views/statements.py`); given page tests and `test_import_rows_for_each_status`.
- R6 to R8: given web statement tests; upload reads `file.file.read(UPLOAD_LIMIT + 1)`, no disk write (`test_an_upload_writes_no_file_under_data`); after `imported`, categorize and pair_transfers run in their own session.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the named tests run, and the file restored.

1. The stored name keeps the folders the browser sent: `test_upload_name_drops_folders` fails (added after the given upload test did not catch it).
2. The rules do not run after an upload: `test_upload_a_statement` fails.
3. A dry run writes the statement: `test_a_dry_run_writes_nothing` fails.
4. Two back-to-back statements are reported as a gap of no days: `test_statement_gaps[back-to-back]` fails.
5. The bulk route reads its form with the framework's default limit again: both cases of `test_a_page_of_1000_rows_reaches_the_app` fail.

## Out of scope

Absent: keeping the uploaded file; several files at once; a change to `ingest/` or `fin import`; JavaScript.
