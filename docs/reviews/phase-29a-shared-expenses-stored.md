# Review: Phase 29a

- Verdict: PASS
- Passed: 3713
- Findings: 0
- Approved deviations: None
- For the architect: four uncommitted 28g status lines sit in `docs/roadmap.md`, the architect skill, and the 29a spec and guide; they are not this phase's work

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write")

## Gates

- `scripts/check.py`: `3713 passed`, `All checks passed.` (N + 25 = 3703; extra 10 from extra tests and the new HOMES area)
- Given tests: `25 passed`
- Coverage of `domain.shared` from `tests/unit/test_shared.py`: `Required test coverage of 100% reached`
- Coverage of `domain.shared`, `domain.audit`, `db.repositories`, `analysis.shared`: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: the four files of the given diff
- `git grep -n "domain/shared.py" -- scripts/critical_modules.txt docs/testing.md`: one line in each
- `git grep -n "SharedExpenseRow\|SettlementRow" -- src/finances/analysis src/finances/categorize src/finances/cli src/finances/web`: no output
- Given tests match the spec blocks; migration `0020` matches the spec

## Requirement checklist

- R1: `test_0020_follows_0019`; `test_the_tables_and_their_row_classes`; `test_down_and_up_again`; `tests/integration/test_migration_chain.py`
- R2: given `test_shared.py`; critical list in `scripts/critical_modules.txt` and `docs/testing.md` (added in Phase 29a)
- R3: `test_the_lists`; `test_an_unknown_action`
- R4: `test_sharing_uses_the_owner_and_replaces`; `test_the_cardholder_comes_before_the_owner`; `test_a_joint_purchase_needs_who_paid`; `test_share_transaction_refusals_store_nothing`; `share_transaction` refuses in the spec's order, payer from `person_for`
- R5: `test_unshare_removes_the_share`
- R6: `test_settlements_and_their_refusals`
- R7: `test_a_shared_transaction_is_never_a_transfer`; `_check_transfer` refuses a shared transaction after the existing checks
- R8: `test_feed_delete_and_amount_change_look_after_a_share`; share cleared only when the amount changes, `who` `system`
- R9: `test_owed_report_after_a_share_and_a_settlement` (`[Owed("Alex", "Sam", 600)]`)
- R10: `git diff --stat HEAD -- tests` lists only the four files

## Tests to write

- `share_transaction(1, "alex")` half rounded down, replace with `size_cents=1200`: `test_sharing_uses_the_owner_and_replaces`
- cardholder before owner: `test_the_cardholder_comes_before_the_owner`
- joint needs who paid, named payer stored: `test_a_joint_purchase_needs_who_paid`
- each R4 refusal, pending before debtor: `test_share_transaction_refusals_store_nothing`
- unshare and not shared: `test_unshare_removes_the_share`
- settlements, audit, R6 refusals: `test_settlements_and_their_refusals`
- 5 shared, `pair_transfers` pairs nothing: `test_a_shared_transaction_is_never_a_transfer`
- feed delete and amount change: `test_feed_delete_and_amount_change_look_after_a_share`
- `owed_report` after share and $4.00 settlement: `test_owed_report_after_a_share_and_a_settlement`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy (not git checkout), with `__pycache__` cleared.

1. `half_share` round up: `test_half_a_share[-2001-1000]` failed (1001)
2. `signed_share` no sign for money in: `test_a_share_of_a_size[2000-500--500]` failed (500)
3. `signed_share` the whole amount refused: `test_a_share_of_a_size[-2000-2000-2000]` failed (SIZE)
4. `balances` a settlement adds: `test_a_settlement_pays_it_down[700-owed2]` failed (`Owed("Alex", "Sam", 1200)`)
5. `balances` sorted by creditor first: swapping to `(creditor, debtor)` still passed on this triple (same order); `reverse=True` failed
6. `share_transaction` the owner before the cardholder: `test_the_cardholder_comes_before_the_owner` failed (Sam as payer, cannot owe themselves)
7. `share_transaction` a joint payer let through: `test_a_joint_purchase_needs_who_paid` failed (error, not the joint message)
8. `share_transaction` people checked before pending: `test_share_transaction_refusals_store_nothing` failed (`person not found`)
9. `list_transfer_movements` keep shared transactions: `test_a_shared_transaction_is_never_a_transfer` failed (`_check_transfer` then refused the pair)
10. `update_feed_transaction` clear on every update: `test_feed_delete_and_amount_change_look_after_a_share` failed (share cleared on the same amount)

## Probe

None: nothing in this phase reaches a command or a page. Read `share_transaction`, `_check_transfer`, and `update_feed_transaction` against R4, R7, and R8.

## Out of scope

Absent: any command, page, or MCP tool for shares; more than two people on one share; percentages; a settlement linked to a transfer or edited in place; sharing a pending transaction or a transfer.

## Progress log

`docs/progress.md` has the Phase 29a entry in the required form. Deviations: None.
