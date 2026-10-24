# Review: Phase 29b

- Verdict: PASS
- Passed: 3736
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write")

## Gates

- `scripts/check.py`: `3736 passed`, `All checks passed.` (N + 14 = 3727; extra 9 from extra tests)
- Given tests: `14 passed`
- Coverage of `cli.shared` and `views.shared`: `Required test coverage of 100% reached` (`cli.shared` 83/8, `views.shared` 30/2)
- `git diff --stat HEAD -- tests`: no output
- `git grep -n "half_share\|signed_share\|balances(\|SharedExpenseRow\|SettlementRow" -- src/finances/cli src/finances/views`: no output
- Given `tests/e2e/test_cli_shared.py` matches the spec block
- `git status --short` lists `docs/progress.md`, `src/finances/cli/main.py`, the two new modules, and three new test files

## Requirement checklist

- R1: `test_refused`; every command in `cli/shared.py` calls `require_current_schema()` first
- R2: given tests; `test_share_text_of_zero_names_the_debtor`; `test_share_text_of_a_negative_share_names_the_payer`; `test_owed_text`; `test_settlement_text`; `test_share_rows_every_field`; `test_settlement_rows_every_field`
- R3: `test_sharing`; `test_refused`; `test_paid_by_shares_a_joint_purchase`; `test_a_pending_purchase_cannot_be_shared`
- R4: `test_unsharing`
- R5: `test_sharing` (list rows)
- R6: `test_sharing`; `test_settling`; `test_unsharing`
- R7: `test_settling`; `test_a_settlement_today`
- R8: `test_settling` (settlements table)
- R9: `test_settling`; `test_refused`

## Tests to write

- `share_text` of a share owing 0: `test_share_text_of_zero_names_the_debtor`
- `share_text` of -200 names the payer owing $2.00: `test_share_text_of_a_negative_share_names_the_payer`
- `owed_text`, `settlement_text`, `share_rows`, `settlement_rows` of hand-made values: `test_owed_text`; `test_settlement_text`; `test_share_rows_every_field`; `test_settlement_rows_every_field`
- `add --paid-by Sam` on a joint purchase: `test_paid_by_shares_a_joint_purchase`
- `add` on a pending purchase: `test_a_pending_purchase_cannot_be_shared`
- a database that is not migrated: `test_list_needs_a_migrated_database`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy (not git checkout), with `__pycache__` cleared.

1. `share_text` no flip for a negative share: `test_sharing` failed (`Alex owes Sam -$2.00.`)
2. `add` `--share` blank read as zero: `test_sharing` failed (exit 1, the size refusal)
3. `settle` `date.today()` instead of `clock.today()`: `test_a_settlement_today` failed (`2026-10-23` instead of `2026-06-01`)
4. `owed` shares only, settlements left out: `test_settling` failed (`Alex owes Sam $10.00.`)
5. `add` `--paid-by` not passed: `test_paid_by_shares_a_joint_purchase` failed (exit 1; the test holds `--paid-by Sam`)
6. `share_rows` the owed size, not signed: `test_sharing` failed (`$2.00` instead of `-$2.00`)

## Probe

On a temporary `FIN_DATA_DIR` (never the owner's `data/`): Sam and Alex; one -$20.00 FOOBAR GROCERY purchase on a card Sam owns; `fin shared add --id 1 --with Alex` printed `Alex owes Sam $10.00.`; `fin shared settle --from Alex --to Sam --amount 4.00` printed a $4.00 settlement; `fin shared owed` printed `Alex owes Sam $6.00.`. `FAILURES 0`.

## Out of scope

Absent: any page or form; an MCP tool for shares; a share's date or description in `fin shared list`; filters; a change to 29a's repository or rules.

## Progress log

`docs/progress.md` has the Phase 29b entry in the required form. Deviations: None.
