# Review: Phase 36c

- Verdict: PASS
- Passed: 3298
- Findings: 0
- Approved deviations: none
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `3298 passed`, `All checks passed.` (N + 8 = 3294; extra 4)
- Given tests plus earlier view tests: all passed
- Page and command tests: `437 passed`
- Coverage of simplefin, transfers, backups analysis, views, and sync.links: `Required test coverage of 100% reached`
- `git grep` of db/sqlalchemy/keyring/sync.links in views: no output
- `git diff --stat HEAD -- tests`: the three files of the given diff
- Given files match the spec blocks; no template changes

## Requirement checklist

- R1: `test_the_keychain_state_lives_with_the_links`; `test_status_rows`; `test_waiting_counts_only_links_that_ran`; `test_setup_offers`; `test_mapping_status_asks_the_keychain_once_for_two_mappings_under_one_link`
- R2: `test_transfer_lines_latest_outflow_first_then_highest_pair`; `test_pair_of_each_side_and_a_transaction_in_none`; `test_suggestion_listing_with_nothing_waiting`
- R3: `test_backup_rows_from_files`; `test_backup_files_on_an_empty_list`
- R4: `test_status_rows_from_mappings`
- R5: `test_transfer_lines_sort_and_suggestions`; `test_both_sides_show_their_pairs_line`
- R6: `test_backup_rows_from_files`
- R7: `test_one_change_text`
- R8: page and command tests unchanged
- R9: `test_the_cli_tables_go_through_print_rows`
- R10: `test_no_view_loads_data`; `test_no_view_takes_a_session`
- R11: given earlier-test diffs applied
- R1 to R3 edges: `tests/integration/test_listings_more_36c.py`

## Probe

None. The earlier command and page tests pin every output these views and tables make.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. `views/sync.py` imports `finances.sync.links` again: `test_no_view_loads_data` fails (`sync.py`: `finances.sync.links`).
2. Leave a `_change` in `views/insights.py`: `test_one_change_text` fails (`insights.py`).
3. `transfer_lines` keeps the listing's order: `test_transfer_lines_sort_and_suggestions` fails (pair 1 first).
4. `fin health` builds its table by hand again: `test_the_cli_tables_go_through_print_rows` fails (`health.py`: 1).

## Out of scope

Absent: a template change; a change to output; a change to the three tables built from other cells.
