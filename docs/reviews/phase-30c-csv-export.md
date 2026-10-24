# Review: Phase 30c

- Verdict: PASS
- Passed: 3828
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write", plus `test_year_with_no_year_writes_this_year` so `cli.export` stays at 100%)

## Gates

- `scripts/check.py`: `3828 passed`, `All checks passed.` (N + 17 = 3819; extra 9 from `test_export_views.py` and `test_export_more.py`)
- Given tests: `17 passed`
- Coverage of `domain.money`, `analysis.export`, `views.export`, `export`, `cli.export`: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: only `tests/conftest.py`
- `git grep -n "float(\|urllib\|socket\|http" -- src/finances/export src/finances/views/export.py src/finances/analysis/export.py src/finances/domain/money.py` prints nothing
- Given `test_money_decimal.py`, `test_cli_export.py`, and the `conftest.py` diff match the spec blocks
- `git status --short` lists `docs/progress.md`, the source files of the spec's Scope (five of them new), `tests/conftest.py`, and four new test files

## Requirement checklist

- R1: `test_cents_as_plain_decimal_dollars`; critical coverage of `domain/money.py`
- R2: `test_the_export_folder_setting`; `effective_export_dir` defaults to `data_dir / "exports"`
- R3: `test_transactions`; `test_every_transaction_in_the_range_and_tags_past_500`
- R4: `test_transactions`; `test_the_year`; `test_spending_for_a_month`; `test_a_quoted_description_blanks_a_card_and_two_tags`; `test_year_and_spending_csv_write_money_back`
- R5: `test_another_folder_and_replacing`; `test_write_csv_makes_a_missing_folder_two_levels_deep`; `write_csv` uses `newline=""`
- R6: `test_transactions`; `test_refused`; `test_transactions_with_no_dates_writes_this_year`
- R7: `test_the_year`; `test_refused`
- R8: `test_spending_for_a_month`; `test_refused`; `test_spending_with_no_options_writes_this_month_by_category`
- R9: gate 4 (only `tests/conftest.py`)

## Tests to write

- `transactions_csv` of hand-made lines (quoted description, blanks, card, two tags): `test_a_quoted_description_blanks_a_card_and_two_tags`
- `year_csv` and `spending_csv` with net money back (`-5.00`): `test_year_and_spending_csv_write_money_back`
- 1201 transactions and 600 tagged (the 500-id rule): `test_every_transaction_in_the_range_and_tags_past_500`
- a pending transaction is written with the kind `pending`: `test_a_pending_transaction_is_written_as_pending`
- `write_csv` makes a missing folder two levels deep: `test_write_csv_makes_a_missing_folder_two_levels_deep`
- `fin export transactions` with no dates writes this year's file: `test_transactions_with_no_dates_writes_this_year`
- `fin export spending` with no options writes this month's file by category: `test_spending_with_no_options_writes_this_month_by_category`
- a database that is not migrated: `test_a_database_that_is_not_migrated`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy (not git checkout), with `__pycache__` cleared.

1. `decimal_text` through `float`: `test_cents_as_plain_decimal_dollars[900719925474099301-9007199254740993.01]` failed (`9007199254740994.00` instead of `9007199254740993.01`)
2. `decimal_text` the sign lost under a dollar: `test_cents_as_plain_decimal_dollars[-5--0.05]` failed (`0.05` instead of `-0.05`)
3. `transactions_for_export` whole flows: `test_transactions` failed (one row for transaction 2 instead of two)
4. `transactions_for_export` newest first: `test_transactions` failed (order 3, 2, 2, 1 instead of 1, 2, 2, 3)
5. `transactions_for_export` the search's default limit kept: `test_every_transaction_in_the_range_and_tags_past_500` failed (50 lines instead of 1201)
6. `write_csv` an existing file replaced without `force`: `test_another_folder_and_replacing` failed (written instead of refused)
7. the commands `FIN_EXPORT_DIR` ignored: `test_the_export_folder_setting` failed (`data/exports` instead of the `out` folder)
8. `fin export year` `min=1` on `--year`: `test_refused[args1-year must be from 1 to 9999]` failed (a usage error, exit 2)

## Probe

On a temporary `FIN_DATA_DIR` (never the owner's `data/`): one -$45.00 ACME CLINIC purchase on a card, set to Medical by hand; `fin export year --year 2026`. The file's Medical row had Spent `45.00`, Refunds `0.00`, Net `45.00`, which parse as numbers.

## Out of scope

Absent: export from the web; any report beyond transactions, the year, and spending; filters on the transactions export; other formats or a choice of columns; anything that sends a file.

## Progress log

`docs/progress.md` has the Phase 30c entry in the required form. Deviations: None.
