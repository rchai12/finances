# Review: Phase 29c

- Verdict: PASS
- Passed: 3765
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write", plus CSRF and missing-id branches needed for 100% coverage of the new routes)

## Gates

- `scripts/check.py`: `3765 passed`, `All checks passed.` (N + 10 = 3746; extra 18 from extra tests and 1 from the new `shared` area in `test_web_split.py`)
- Given tests: `10 passed`
- Coverage of `web.routes.shared`, `web.routes.transactions`, `db.repositories`: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: `tests/unit/test_repositories_split.py` and `tests/unit/test_web_split.py` only
- `git grep -n "half_share\|signed_share\|balances(\|SharedExpenseRow\|SettlementRow" -- src/finances/web`: no output
- Given `tests/integration/test_web_shared.py` and `shared.html` match the spec blocks
- `git status --short` lists `docs/progress.md`, the source files and templates of the spec's Scope (two of them new), the two earlier test files, and two new test files

## Requirement checklist

- R1: `test_the_shared_page`; `test_shared_needs_a_migrated_database`
- R2: `test_settling_on_the_page`; `test_a_refused_settlement`; `test_a_blank_date_uses_today_from_the_app`
- R3: `test_deleting_a_settlement`
- R4: `test_get_on_the_new_paths_is_405` (four 405s)
- R5: `test_a_shared_transactions_page`; `test_a_refused_share_keeps_tags_note_and_the_form`
- R6: `test_sharing_and_unsharing_on_a_transactions_page`; `test_a_refused_share`; `test_paid_by_shares_a_joint_purchase`
- R7: `test_sharing_and_unsharing_on_a_transactions_page`; `test_stopping_a_share_that_is_not_there`
- R8: gate 2; `NOTICES` has `Settlement recorded.`, `Settlement deleted.`, `Share saved.`, `Share removed.`
- R9: `test_the_shared_page`
- R10: gate 4 (only the two given-diff files)

## Tests to write

- GET on each of the four new POST paths is 405; `/shared` not migrated: `test_get_on_the_new_paths_is_405`; `test_shared_needs_a_migrated_database`
- a settlement with a blank date uses `_today` replaced after the app is created: `test_a_blank_date_uses_today_from_the_app`
- a refused share keeps tags, note, and the Shared form; stopping a share that is not there: `test_a_refused_share_keeps_tags_note_and_the_form`; `test_stopping_a_share_that_is_not_there`
- a joint purchase with `payer` Sam stored, blank payer the joint message: `test_paid_by_shares_a_joint_purchase`
- a share posted with `share` blank owes half: `test_a_blank_share_owes_half`
- a share on transaction 99 is 404: `test_a_share_on_a_missing_transaction`
- the Shared page with no shares and no settlements: `test_an_empty_shared_page`
- a form without a valid form token: `test_a_form_without_a_valid_token_is_refused`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy (not git checkout), with `__pycache__` cleared.

1. settle `date.today()` for a blank date: `test_a_blank_date_uses_today_from_the_app` failed (`2026-10-23` instead of `2026-07-04`)
2. Shared page `day` not filled with today: `test_the_shared_page` failed (`""` instead of `2026-06-01`)
3. share route a blank `share` read as zero: `test_a_blank_share_owes_half` failed (400, the size refusal)
4. `_transaction_page` `share_form` dropped on a 400: `test_a_refused_share` (`30`) failed (`""` instead of `30`)
5. clear route `unshare_transaction` not called: `test_sharing_and_unsharing_on_a_transactions_page` failed (`Alex owes Sam $4.00.`)

## Probe

On a temporary `FIN_DATA_DIR` (never the owner's `data/`): Sam and Alex; one -$20.00 FOOBAR GROCERY purchase on a card Sam owns; `fin web serve --port 18767`. Sharing on the transaction page printed `Alex owes Sam $10.00.`; recording a $4.00 settlement on Shared left `Alex owes Sam $6.00.`. Shared sits in the menu after People and marks itself current. `FAILURES 0`.

## Out of scope

Absent: shares on the Transactions page or another table; an MCP tool for shares; a filter on the Shared page; editing a settlement or share in place; a change to 29a's rules or 29b's commands.

## Progress log

`docs/progress.md` has the Phase 29c entry in the required form. Deviations: None.
