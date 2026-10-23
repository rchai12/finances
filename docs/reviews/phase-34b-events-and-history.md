# Review: Phase 34b

- Verdict: PASS
- Passed: 3349
- Findings: 0
- Approved deviations: none
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `3349 passed`, `All checks passed.` (N + 21 = 3344; extra 5 from extra tests and one new split-area parametrize case)
- Given tests: `21 passed`
- Earlier audit, split, backup, and nav tests: `81 passed`
- Coverage of domain.audit, backup_records, repositories, views.audit, history, backups, and cli.backup: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: the three files of the given diff
- `git diff --stat HEAD -- src/finances/db/backup.py`: nothing
- Given template and tests match the spec blocks; both diffs applied

## Requirement checklist

- R1: `test_the_lists`
- R2: `test_a_statement_import_is_recorded_as_the_system`; `test_a_real_statement_import_through_fin_import_records_one_statement_imported`
- R3: `test_nothing_is_noted_on_a_database_that_is_not_migrated`; `test_deleting_a_backup_on_the_web`; `test_a_restore_keeps_the_restored_history_and_adds_one_row`
- R4: `test_deleting_a_backup_on_the_web`; `test_a_restore_keeps_the_restored_history_and_adds_one_row`; `test_restoring_in_the_terminal`; `test_a_refused_delete_of_an_unknown_name_records_nothing`
- R5: `test_each_kind_links_to_its_page`
- R6: `test_the_history_newest_first_with_links`; `test_one_action_and_one_day`; `test_refused_filters`; `test_a_database_that_is_not_migrated`
- R7: `test_the_history_newest_first_with_links`; `test_the_history_menu_link_is_current_only_on_its_page`
- R8: `test_the_lists`; `test_an_unknown_action`; `test_the_same_routes_as_before_the_split`
- R2, R4 edges: `tests/integration/test_history_more.py`

## Probe

None. The spot checks.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. Record the restore before `restore_backup`: `test_a_restore_keeps_the_restored_history_and_adds_one_row` fails (no `backup_restored` in the restored database).
2. `note_backup_restored` skips the revision check: `test_restoring_a_backup_from_before_the_trail_records_nothing` fails (`no such table: audit_log`).
3. Record imports as `person`: `test_a_statement_import_is_recorded_as_the_system` fails (`person` not `system`).
4. `/history` accepts any action text: `test_refused_filters[action=nope-...]` fails (200 not 400).
5. `change_link` sends a rule to its own page: `test_each_kind_links_to_its_page[rule-2-/categories]` fails (`/categories/rules/2`).

## Out of scope

Absent: a change to `db/backup.py`; sync or feed events; an `agent` who; a way to edit or delete rows.
