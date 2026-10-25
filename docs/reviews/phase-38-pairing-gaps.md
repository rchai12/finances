# Review: Phase 38

- Verdict: PASS
- Passed: 4010
- Findings: 0
- Approved deviations: Phase 20d's extra test patched `finances.web.routes.sync.keyring`; R3 removes that import, so `test_the_sync_page_without_a_listable_keychain` now only asserts GET `/sync` is 200
- For the architect: a later extra test that patches a private import the next phase deletes needs a given diff, or gate 4 (`git diff --stat HEAD -- tests`) and check.py cannot both pass

## Findings

None

Parts that needed a repair: `test_the_sync_page_without_a_listable_keychain` could not patch `sync.keyring` after R3. The assertion that GET `/sync` is 200 stayed.

Built beyond the spec: extra tests for a split with no partner, a missing share id, mapped and seen Unlink forms in sorted order, no Unlink with no links, and a refused link name on the accounts page.

## Gates

- `scripts/check.py`: `4010 passed`, last line `All checks passed.` (N + 7 = 4005)
- Given tests: `7 passed`
- Coverage of `finances.web.routes.sync`, `finances.web.routes.transactions`, `finances.web.routes.shared`, `finances.cli.shared`: `Required test coverage of 100% reached. Total coverage: 100.00%`
- `git diff --stat HEAD -- tests`: `tests/integration/test_web_recheck.py` and, as the approved deviation, `tests/integration/test_web_recheck_more.py`
- `git grep -n -e "passwords" -e "keyring" -- src/finances/web/routes`: no output
- Given `tests/integration/test_pairing_gaps.py` matches the spec block
- Given template `sync_accounts.html` matches the spec diff
- Given diff to `tests/integration/test_web_recheck.py` matches the spec

`git status --short` lists `docs/progress.md`, the four source files and the template of the spec's Scope, `tests/integration/test_web_recheck.py`, two new test files, the extra-test repair, and this review.

## Requirement checklist

- R1: gate 2 (`test_clearing_a_split_on_the_web_pairs_the_transfer`); `test_clearing_a_split_with_no_partner_pairs_nothing`
- R2: gate 2 (`test_unsharing_on_the_web_pairs_the_transfer`, `test_unsharing_in_the_terminal_pairs_the_transfer`); `test_removing_a_missing_share_stores_no_pair`
- R3: gate 2 (`test_unlink_is_offered_for_the_links_the_database_knows`); gate 5; `test_mapped_and_seen_links_both_get_unlink_in_sorted_order`, `test_the_simplefin_page_has_no_unlink_form_with_no_links`
- R4: gate 4 (the given unlink test now records a seen feed account)
- R5: gate 2 (`test_the_accounts_page_offers_unlink_right_after_linking`, `test_the_accounts_page_offers_unlink_when_simplefin_refuses`, `test_no_unlink_for_a_link_that_is_not_set_up`); `test_no_unlink_for_a_refused_link_name`

## Tests to write

- clearing a split whose transaction has no transfer partner: `test_clearing_a_split_with_no_partner_pairs_nothing`
- `fin shared remove --id 99`: `test_removing_a_missing_share_stores_no_pair`
- mapped and seen Unlink forms in sorted order: `test_mapped_and_seen_links_both_get_unlink_in_sorted_order`
- no links at all: `test_the_simplefin_page_has_no_unlink_form_with_no_links`
- refused link name: `test_no_unlink_for_a_refused_link_name`

## Spot checks

Each deciding test failed under the named change. Restored from `/tmp/fin-38-spots/` copies, not `git checkout`. SPOT_FAILURES 0.

| Change | Deciding test | Result |
|---|---|---|
| 1. `remove_split`: no `pair_transfers` | `test_clearing_a_split_on_the_web_pairs_the_transfer` | failed (not paired) |
| 2. `clear_share`: no `pair_transfers` | `test_unsharing_on_the_web_pairs_the_transfer` | failed (not paired) |
| 3. `remove_command`: no `pair_transfers` | `test_unsharing_in_the_terminal_pairs_the_transfer` | failed (not paired) |
| 4. `_sync_page`: `_keychain_links` kept | `test_unlink_is_offered_for_the_links_the_database_knows` | failed |
| 5. `_sync_page`: mapping rows only | the same test | failed |
| 6. `sync_accounts`: `unlinkable` never set | `test_the_accounts_page_offers_unlink_right_after_linking` | failed |
| 7. `sync_accounts`: `unlinkable` only on the 200 page | `test_the_accounts_page_offers_unlink_when_simplefin_refuses` | failed |
| 8. `sync_accounts`: `unlinkable` always true | `test_no_unlink_for_a_link_that_is_not_set_up` | failed |

## Out of scope

Absent: pairing after rules, aliases, or clearing categories; another way of listing Keychain links; a migration storing link names; changes to `fin sync`; any other audit finding.
