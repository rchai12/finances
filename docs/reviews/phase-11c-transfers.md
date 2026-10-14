# Review: Phase 11c

- Verdict: PASS
- Passed: 2311
- Findings: 0
- Approved deviations: the given `tests/e2e/test_cli_transfers.py` and its spec block changed `"2026-05-0{}"` to `"2026-05-0{1}"` in the In date cell, approved by the owner
- For the architect: a given test built expected rows with `str.format` and a bare `{}` that repeated the first argument; run given tests against a reference build, or use numbered fields, before issuing them

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2311 passed`, `All checks passed.`
- Given tests: `41 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Both searches: no output
- Scope: `git status --short` lists the guide's paths, plus `docs/phases/phase-11c-transfers.md` (the approved fix) and this review
- Given files: the migration and the three test files are identical to the spec's blocks
- R21: `git diff HEAD -- src/finances/web/app.py` adds only the `pair_transfers` import and its call after `categorize` in `POST /sync/run`

## Probe

```
pair: one clear pair, pending and rejected rows left alone ok
delete: a paired and a rejected feed transaction go with their rows ok
delete: the other side stays ok
FAILURES 0
```

## Spot checks

Each change was made in the code, the tests run, and the code restored.

1. `clear_pairs` checks only the out side: `test_only_pairs_with_one_choice_on_each_side_are_clear` fails.
2. `unpair_transfer` records no rejection: `test_an_unpaired_transfer_is_not_paired_again` and `test_unpairing_records_a_rejection` fail.
3. "already in a transfer" checked before the accounts: three cases of `test_a_refused_command` fail.
4. `reject_transfer` leaves the pair: `test_rejecting_a_transfer_removes_it` and `test_rejecting_removes_only_that_pair` fail.
5. `list_uncategorized` lists paired transactions: `test_find_pairs_the_clear_ones_and_leaves_the_rest` fails.

Also, Sync now without `pair_transfers`: `test_sync_now_pairs_a_clear_transfer_the_feed_brought` fails.

## Out of scope

Absent: transfer templates, routes, and links on the web; any change to spending totals; pairing that sets or clears a category.
