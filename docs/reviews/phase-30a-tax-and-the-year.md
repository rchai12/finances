# Review: Phase 30a

- Verdict: PASS
- Passed: 3782
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None

Parts that needed a repair: `git grep is_tax` in `cli/categories.py` (the tax command read `found.is_tax`); the printed line now follows `--off`

Built beyond the spec: none (the extra tests are the spec's "Tests to write", plus `test_the_year_command_refuses_an_out_of_range_year` for 100% of `year_command`'s `fail` path)

## Gates

- `scripts/check.py`: `3782 passed`, `All checks passed.` (N + 9 = 3774; extra 8 from `test_year_report.py`)
- Given tests: `9 passed`
- Spending and migration chain: `22 passed`
- Coverage of `analysis.yearend`, `views.yearend`, `views.spending`, `db.repositories`, `cli.reports`, `cli.categories`: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: the four files of the given diff
- `git grep -n "batch_alter_table" -- src/finances/db/migrations/versions/0021_tax_categories.py`: no output
- `git grep -n "is_tax" -- src/finances/cli src/finances/views`: no output
- Given `0021_tax_categories.py`, `test_migration_0021.py`, and `test_cli_year.py` match the spec blocks
- `git status --short` lists `docs/progress.md`, the source files of the spec's Scope (two of them new), the four earlier test files, the new migration, and three new test files

## Requirement checklist

- R1: `test_the_flag_and_the_seeded_tax_categories`; `test_down_and_up_again_with_rows_that_point_at_categories`; `test_a_new_category_is_not_tax_relevant`
- R2: `test_marking_a_category`; `test_marking_refused`; `test_setting_the_flag_records_once`
- R3: `test_a_year`; `test_a_year_with_nothing`; `test_year_report_refuses_a_year_outside_the_range`
- R4: `test_cli_spending.py`; `spending_rows` calls `line_rows`; `spending_summary` calls `summary_lines`
- R5: `test_a_year`; `test_this_year_by_default`; `test_fin_year_with_no_tax_relevant_category`
- R6: `test_marking_a_category`; `test_marking_refused`
- R7: gate 5 (only the four given-diff files)

## Tests to write

- a category made by `create_category` is not tax-relevant; seeded three are: `test_a_new_category_is_not_tax_relevant`
- `set_tax_relevant` records `category_tax_set` with before `not tax` and after `tax`, and setting it again records nothing: `test_setting_the_flag_records_once`
- a tax category renamed keeps its flag: `test_a_renamed_tax_category_keeps_its_flag`
- `year_report(session, 0)` and `year_report(session, 10000)` refused: `test_year_report_refuses_a_year_outside_the_range`
- a transfer between two accounts in the year is not in any line: `test_a_transfer_is_not_in_any_line`
- `fin year` with every flag turned off prints `No tax-relevant categories.`: `test_fin_year_with_no_tax_relevant_category`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy (not git checkout), with `__pycache__` cleared.

1. `year_report` `parts=False`: `test_a_year` failed (Health `$120.00` / count 2 instead of Medical `$130.00` / count 3)
2. year ends on 30 December: `test_a_year` failed (`2026-12-30` instead of `2026-12-31`)
3. year starts a day early: `test_a_year` failed (`2025-12-31` instead of `2026-01-01`)
4. tax lines only where there was spending: `test_a_year` failed (no `Taxes` `$0.00` row)
5. tax lines by amount: `test_a_year` failed (Medical first instead of Gifts & Donations)
6. `fin year` `date.today()` for the default: `test_this_year_by_default` failed (`Year 2026` instead of `Year 2024`)
7. `set_tax_relevant` a group accepted: `test_marking_refused[Health-...]` failed (`Result okay` instead of the group refusal)
8. the migration rebuilt in batch mode: `test_down_and_up_again_with_rows_that_point_at_categories` failed (`FOREIGN KEY constraint failed`)

## Probe

On a temporary `FIN_DATA_DIR` (never the owner's `data/`): one -$45.00 ACME CLINIC purchase on a card, set to Medical by hand. `fin year --year 2026` showed Medical `$45.00` in the Tax-relevant table (with Gifts & Donations and Taxes at `$0.00`).

## Out of scope

Absent: the year or the flag on the web; CSV export; the flag in `fin categories list`, the Categories page, or `list_categories`; a tax flag on a group; income by category; a year other than a calendar year or a comparison of years.

## Progress log

`docs/progress.md` has the Phase 30a entry in the required form. Deviations: None.
