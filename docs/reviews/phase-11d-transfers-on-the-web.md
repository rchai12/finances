# Review: Phase 11d

- Verdict: PASS
- Passed: 2342
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2342 passed`, `All checks passed.`
- Given tests: `23 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Both searches: no output
- Scope: `git status --short` lists exactly the guide's paths, plus this review
- Given files: the three templates and `tests/integration/test_web_transfers.py` are identical to the spec's blocks
- R2: `transfer_lines` and `transfer_of` both build their lines with the private `_line` in `views/transfers.py`

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the tests run, and the code restored.

1. Unpair with `back` returns to `/transfers`: `test_unpair_on_a_transaction_page_returns_to_it` fails.
2. Confirm stores the pair as `auto`: `test_confirm_a_transfer` fails.
3. A refused unpair with `back` answers the transaction's page: `test_a_refused_form[/transfers/unpair-fields8-transfer not found]` fails.
4. `transfer_of` finds only the out side: `test_a_paired_transaction_shows_its_transfer`, `test_both_sides_show_their_pairs_line[4]`, and `test_the_in_side_of_the_other_pair` fail.
5. An empty line for a transaction in no pair: `test_a_paired_transaction_shows_its_transfer`, `test_unpair_on_a_transaction_page_returns_to_it`, and both cases of `test_no_line_without_a_pair` fail.

## Out of scope

Absent: changes to `cli/`, `categorize/`, or `domain/`; JavaScript; a transfer count in the menu.
