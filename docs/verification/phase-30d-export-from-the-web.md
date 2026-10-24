# Verify Phase 30d: export from the web

Spec: `docs/phases/phase-30d-export-from-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added an `export` router with three GET downloads over 30c's CSVs, `export_lines` so the Transactions page's download holds what its filters choose, and three Download links in given templates. A template diff, a diff to one earlier test, and one test file were given.

These are correct and must not be reported: the router importing the pages' private readers (`_search_query`, `_spending_range`) rather than copying them; a private helper that builds the CSV response; `export_lines` replacing the query's limit with `dataclasses.replace`.

## 1. Gates

N is `3828` when Phase 30c was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 10 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_export.py tests/e2e/test_cli_export.py --no-cov` | all passed: exactly 10 in the first file, and 30c's file unchanged |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis.export --cov=finances.web.routes.export --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | only `tests/unit/test_web_split.py` |
| `git grep -n "write_csv\|write_text\|open(" -- src/finances/web/routes/export.py` | no output |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files and templates of the spec's Scope (one of them new), `tests/unit/test_web_split.py`, and two new test files. The templates and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (30c's `test_cli_export.py`); the coder's same-bytes case; read `transactions_for_export` | pass; it returns `export_lines` |
| R2 | gate 2 (`test_transactions_by_dates`, `test_transactions_as_the_filters_choose`, `test_a_download_that_is_refused`) | pass |
| R3 | gate 2 (`test_the_year`, `test_a_download_that_is_refused`); the coder's today case | pass |
| R4 | gate 2 (`test_spending`, `test_a_download_that_is_refused`); the coder's no-options case | pass |
| R5 | gate 2 (`test_each_page_links_to_its_download`) | passes |
| R6 | gate 2 (`test_a_download_writes_nothing`); gate 5 | pass |
| R7 | gate 4 | only that file |

## 4. Probe

None. Look once in a browser: `fin web` on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with a few purchases, filter the Transactions page by a category, press Download these as CSV, and open the file: only that category's rows, every one of them.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `GET /export/transactions`: the filters left out (dates only) | given `test_transactions_as_the_filters_choose` (`category=Groceries`) | one row | five (every transaction and part) |
| 2. `export_lines`: the query's limit used | given `test_transactions_as_the_filters_choose` (`limit=1`) | five rows | one |
| 3. the downloads: no `Content-Disposition` | given `test_the_year` | `attachment; filename="year-2026.csv"` | absent |
| 4. `GET /export/transactions`: dates in the name when only one is given | coder: `?from=2026-05-02` alone | `transactions.csv` | a name with an empty date |
| 5. `GET /export/year`: `date.today()` for a blank year | coder: `_today` replaced after the app is created | that year | the machine's year |
| 6. `GET /export/transactions`: an unknown account exported as no rows | given `test_a_download_that_is_refused` (`account=Nope`) | 400 | 200 |

## 6. Out of scope

Each must be absent: a file written to the export folder from the web; other reports; a choice of columns or format; filters on `fin export transactions`; any change to the CSVs.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
