# Verify Phase 30a: tax categories and the year's totals

Spec: `docs/phases/phase-30a-tax-and-the-year.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a tax flag on categories (a given migration, the field, a repository function with an audit row, `fin categories tax`) and the year's totals (`year_report`, two small helpers taken out of the spending views, `year_heading`, `fin year`). A migration, a diff to four earlier tests, and two test files were given.

These are correct and must not be reported: `year_report` finding the tax categories with `list_categories` or a small query; `fin year` printing each section through one private helper; `--off` written as a Typer flag with any default name, as long as the option is `--off`.

## 1. Gates

N is `3765` when Phase 29c was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 9 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_migration_0021.py tests/e2e/test_cli_year.py --no-cov` | exactly `9 passed` |
| `.venv/bin/python -m pytest tests/e2e/test_cli_spending.py tests/integration/test_migration_chain.py --no-cov` | all passed (`fin spending` unchanged; the models match the migrations) |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis.yearend --cov=finances.views.yearend --cov=finances.views.spending --cov=finances.db.repositories --cov=finances.cli.reports --cov=finances.cli.categories --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | the four files of the given diff |
| `git grep -n "batch_alter_table" -- src/finances/db/migrations/versions/0021_tax_categories.py` | no output |

This search must print nothing:

- `git grep -n "is_tax" -- src/finances/cli src/finances/views`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope (two of them new), the four earlier test files, the new migration, and three new test files. The migration and the diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_migration_0021.py`); gate 3 (the chain test); the coder's `create_category` case | pass |
| R2 | gate 2 (`test_marking_a_category`, `test_marking_refused`); the coder's audit cases | pass |
| R3 | gate 2 (`test_a_year`, `test_a_year_with_nothing`); the coder's year-range case | pass |
| R4 | gate 3 (`fin spending`); read `spending_rows` and `spending_summary` | both call the new helpers |
| R5 | gate 2 (`test_a_year`, `test_this_year_by_default`); the coder's no-tax case | pass |
| R6 | gate 2 (`test_marking_a_category`, `test_marking_refused`) | pass |
| R7 | gate 5 | only the four files |

## 4. Probe

None. Look once in the terminal: on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with a few purchases in one year, set one to Medical by hand, and see it in `fin year`'s Tax-relevant table.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `year_report`: whole flows | given `test_a_year` (the split purchase) | `Medical` `$130.00`, `Groceries` `$20.00` | a `Split` line |
| 2. `year_report`: the year ends on 30 December | given `test_a_year` (`BAZ CHARITY` on 2026-12-31) | Gifts & Donations, count 2 | count 1 |
| 3. `year_report`: the year starts a day early | given `test_a_year` (Medical on 2025-12-31) | Medical `$130.00` | `$229.99` |
| 4. `year_report`: tax lines only where there was spending | given `test_a_year` | a `Taxes` `$0.00` row | no `Taxes` row |
| 5. `year_report`: tax lines by amount | given `test_a_year` | Gifts & Donations, Medical, Taxes | Medical first |
| 6. `fin year`: `date.today()` for the default | given `test_this_year_by_default` (2024) | `Year 2024` | `Year 2026` |
| 7. `set_tax_relevant`: a group accepted | given `test_marking_refused` (`Health`) | refused | `Health is tax-relevant.` |
| 8. the migration rebuilt in batch mode | given `test_down_and_up_again_with_rows_that_point_at_categories` | passes | `FOREIGN KEY constraint failed` |

## 6. Out of scope

Each must be absent: anything on the web; CSV export; the flag in `fin categories list`, the Categories page, or the `list_categories` tool; a flag on a group; income by category; another kind of year or a comparison.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
