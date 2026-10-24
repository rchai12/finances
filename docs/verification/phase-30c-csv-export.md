# Verify Phase 30c: CSV export from the terminal

Spec: `docs/phases/phase-30c-csv-export.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added CSV export: `decimal_text` in the critical `domain/money.py`, an export folder setting, `transactions_for_export`, three CSV writers in the views, a small `export` package that writes a file, and `fin export transactions | year | spending`. A diff to `tests/conftest.py` and two test files were given.

These are correct and must not be reported: `transactions_for_export` reading through `search_transactions` with a large limit or in pages; tags and notes loaded in chunks of up to 500 ids or with one query each over the whole table; the CSVs built with `csv.writer` over `io.StringIO`.

## 1. Gates

N is `3802` when Phase 30b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.` (its critical coverage step includes `domain/money.py`); at least N + 17 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_money_decimal.py tests/e2e/test_cli_export.py --no-cov` | exactly `17 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.money --cov=finances.analysis.export --cov=finances.views.export --cov=finances.export --cov=finances.cli.export --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | only `tests/conftest.py` |

This search must print nothing:

- `git grep -n "float(\|urllib\|socket\|http" -- src/finances/export src/finances/views/export.py src/finances/analysis/export.py src/finances/domain/money.py`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope (five of them new), `tests/conftest.py`, and four new test files.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_money_decimal.py`); gate 1's critical coverage step | pass |
| R2 | gate 2 (`test_the_export_folder_setting`); read `config.py` | passes; the default is `data_dir / "exports"` |
| R3 | gate 2 (`test_transactions`); the coder's 1201 and 600 cases | pass |
| R4 | gate 2; the coder's view tests | pass |
| R5 | gate 2 (`test_another_folder_and_replacing`); the coder's missing-folder case; read `write_csv` | pass; `newline=""` |
| R6 | gate 2 (`test_transactions`, `test_refused`); the coder's default-dates case | pass |
| R7 | gate 2 (`test_the_year`, `test_refused`) | pass |
| R8 | gate 2 (`test_spending_for_a_month`, `test_refused`); the coder's default case | pass |
| R9 | gate 4 | only that file |

## 4. Probe

None. Look once in the terminal: on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with a few purchases, `fin export year`, open the file in a spreadsheet, and see the amounts read as numbers.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `decimal_text`: through `float` | given `900719925474099301` | `9007199254740993.01` | a different last digit |
| 2. `decimal_text`: the sign lost under a dollar | given `-5` | `-0.05` | `0.05` |
| 3. `transactions_for_export`: whole flows | given `test_transactions` (the split) | two rows for transaction 2 | one `Split` row |
| 4. `transactions_for_export`: newest first | given `test_transactions` | 1, 2, 2, 3 | 3, 2, 2, 1 |
| 5. `transactions_for_export`: the search's default limit kept | coder: 1201 transactions | 1201 lines | 50 |
| 6. `write_csv`: an existing file replaced without `force` | given `test_another_folder_and_replacing` | refused | written |
| 7. the commands: `FIN_EXPORT_DIR` ignored | given `test_the_export_folder_setting` | the `out` folder | `data/exports` |
| 8. `fin export year`: `min=1` on `--year` | given `test_refused` (`0`) | `year must be from 1 to 9999`, exit 1 | a usage error, exit 2 |

## 6. Out of scope

Each must be absent: export from the web; any report beyond the three; filters on the transactions export; other formats or a choice of columns; anything that sends a file.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
