# Review: Phase 37

- Verdict: PASS
- Passed: 3998
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None

Parts that needed a repair: coverage of `parse_amount` `ValueError` branches that the amount patterns cannot hit. Those `try`/`except` blocks were removed so the module stays at 100% without dead paths.

Built beyond the spec: extra tests for detect without `Beginning balance on`, a statement with no `Your ` product line, a `0.00` check skipped, a total label with no money then a later total, and an unknown month on the period end.

## Gates

- `scripts/check.py`: `3998 passed`, last line `All checks passed.` (N + 26 = 3978)
- Given tests: `26 passed`
- Coverage of `finances.ingest.parsers.boa_deposit`: `Required test coverage of 100% reached. Total coverage: 100.00%`
- `git diff --stat HEAD -- tests`: no output
- `git diff --stat HEAD -- src`: only `src/finances/ingest/parsers/__init__.py`
- Given `tests/unit/test_boa_deposit_parser.py` matches the spec block
- Fixtures match the spec blocks with each `----- page break -----` line as one form feed; the form-feed check printed `[]`

`git status --short` lists `docs/progress.md`, `src/finances/ingest/parsers/__init__.py`, and as new: `src/finances/ingest/parsers/boa_deposit.py`, `tests/fixtures/statements/boa_deposit/`, `tests/unit/test_boa_deposit_parser.py`, `tests/unit/test_boa_deposit_parser_more.py`.

## Requirement checklist

- R1: gate 2 (`test_the_parser_is_registered_once_under_its_name`)
- R2: gate 2 (`test_detects_its_own_fixtures`, `test_does_not_detect_another_statement`)
- R3: gate 2 (`test_checking_header_balances_and_totals`, `test_savings`, `test_year_end`); `test_a_savings_product_after_the_account_line_stays_checking`
- R4: gate 2 (the same three); `test_an_overdrawn_beginning_balance_is_negative`
- R5: gate 2 (`test_checking_lines`, `test_the_page_breaks_do_not_matter`); `test_a_summary_checks_line_does_not_open_the_checks_section`
- R6: gate 2 (`test_checking_lines`); `test_a_reversal_without_a_minus_is_positive`, `test_a_zero_amount_row_is_skipped`
- R7: gate 2 (`test_checking_lines`, `test_year_end`); `test_an_impossible_purchase_day_and_checkcard_later_have_no_purchase_date`
- R8: gate 2 (`test_checking_lines`); `test_a_star_before_the_check_number_is_stripped`
- R9: gate 2 (`test_checking_header_balances_and_totals`, `test_a_missing_part_is_refused`, `test_an_impossible_row_date_is_refused`); `tests/unit/test_parser_fuzz.py` in gate 1

## Tests to write

- a beginning balance printed `-$25.00` (overdrawn) gives `-2500`: `test_an_overdrawn_beginning_balance_is_negative`
- a row in `Other subtractions` printed without a minus (a reversal) is positive: `test_a_reversal_without_a_minus_is_positive`
- a row with amount `0.00` is skipped: `test_a_zero_amount_row_is_skipped`
- a period with `September 31` and one with an unknown month name are refused with `boa_deposit: statement period not found`: `test_a_bad_period_date_is_refused`
- an account-number line with only three digits is refused with `boa_deposit: account number not found`: `test_three_account_digits_are_refused`
- a check line with `*1045` reads check `1045`; a check with an impossible date is refused with `boa_deposit: invalid date`: `test_a_star_before_the_check_number_is_stripped`, `test_an_impossible_check_date_is_refused`
- `CHECKCARD 1340` keeps `transaction_date` None; `CHECKCARD` later in the text keeps it None: `test_an_impossible_purchase_day_and_checkcard_later_have_no_purchase_date`
- a product line `Your Savings Plus` after the account-number line does not make a checking statement savings: `test_a_savings_product_after_the_account_line_stays_checking`
- `Total ATM and debit card subtractions` alone gives that total as `WITHDRAWALS`: `test_the_atm_total_alone_is_withdrawals`
- a summary line `Checks  -350.00` does not open the checks section: `test_a_summary_checks_line_does_not_open_the_checks_section`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy under `/tmp/fin-37-spots/` (not git checkout), with `__pycache__` cleared. `SPOT_FAILURES 0`.

1. account type `Savings` anywhere on the first page: `test_checking_header_balances_and_totals` failed
2. `WITHDRAWALS` total only one of the two labels: `test_checking_header_balances_and_totals` failed
3. checks one per line (`fullmatch`): `test_checking_lines` failed
4. checks no `*` after the number: `test_checking_lines` failed
5. wrapped lines appended to the description: `test_checking_lines` failed
6. `account_last4` from the first group: `test_checking_header_balances_and_totals` failed
7. purchase date in the posted row's year: `test_year_end` failed

## Probe

None. The fuzz test already feeds every registered parser damaged copies of every fixture.

## Out of scope

Absent: changes to another parser, `describe_layout.py`, `check_real_samples.py`, or the import service; a `card_last4` or cardholder on these rows; a CSV profile.

## Progress log

`docs/progress.md` has the Phase 37 entry in the required form. Deviations are None.
