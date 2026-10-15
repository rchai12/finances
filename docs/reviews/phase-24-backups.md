# Review: Phase 24

- Verdict: PASS
- Passed: 2611
- Findings: 0
- Approved deviations: `db/backup.py` added to `CRITICAL` in `tests/unit/test_check_script.py` and to the critical-module list in `docs/testing.md` (both outside Scope; approved by the owner, since adding it to `scripts/critical_modules.txt` alone fails `test_the_shipped_list` and three other tests that read that list).
- For the architect: (1) A phase that adds a critical module needs `tests/unit/test_check_script.py` and `docs/testing.md` in its Scope; this spec listed only `scripts/critical_modules.txt`. (2) Spot check 2 (read-write open) failed no given test while the not-a-file guard stays, since a read-write open of a whole file leaves nothing behind; the coder added a test with a leftover `-wal` file, which a read-write open merges and deletes. (3) Spot check 4 (local time) fails the given tests only when the machine's time zone is not UTC; it does here.

## Findings

None after the repair. The first pass had one:

`R3 | tests/integration/test_backup.py | expected a test failing when check_backup opens read-write | found none (spot check 2 with the not-a-file guard kept passed all 32 tests)`

Parts that needed a repair: R3's read-only open had no test; `tests/integration/test_backup_more.py` adds `test_a_check_changes_none_of_the_files_it_reads`, which fails under spot check 2. It compares the database and its `-wal` file byte for byte and leaves out `-shm`, which SQLite's readers update even when read-only.

Built beyond the spec: `restore_backup` refuses a URL that is not a database file with the spec's `backups need a database file` (the message table names the case; R5 does not place it).

## Gates

- `scripts/check.py`: `2611 passed`, `All checks passed.` (N + 18 = 2596; 15 more are the coder's). The critical coverage step reads `scripts/critical_modules.txt`, which lists `db/backup.py`, and prints only gaps; it printed none.
- Given tests: `18 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%` (`db/backup.py`, `cli/backup.py`, `config.py` each 100% of lines and branches)
- `sqlite3` search: only `src/finances/db/backup.py:8`
- Logging search: no output
- Scripts: both `-rwxr-xr-x`; `bash -n` prints nothing for both. Not run.
- Scope: `git status --short` lists the guide's 13 paths, plus `tests/unit/test_check_script.py` and `docs/testing.md` (the approved deviation) and this review
- Given files: both scripts, `docs/backups.md`, `tests/integration/test_backup.py`, and `tests/e2e/test_cli_backup.py` are identical to the spec's blocks; `git diff HEAD -- tests/conftest.py` is the spec's diff (applied with `git apply`)

## Requirement checklist

- R1: `test_the_backup_folder_defaults_to_the_data_folder`, `test_the_backup_settings_come_from_the_environment`, and the given `test_the_folder_and_how_many_to_keep_come_from_settings`.
- R2: given `test_backup_names_use_utc`, `test_only_the_newest_are_kept`; `test_a_missing_folder_has_no_backups`.
- R3: `check_backup` (`db/backup.py:69`) refuses a non-file before opening, then opens with `file:...?mode=ro` (line 75). Tests: given `test_a_file_that_is_not_a_backup`; `test_damage_found_by_the_integrity_check`, `test_damage_that_stops_sqlite_reading`, `test_an_empty_alembic_version`, `test_a_check_leaves_nothing_beside_the_backup`, `test_a_check_changes_none_of_the_files_it_reads`.
- R4: `make_backup` (line 110) checks the URL, then `keep`, then makes the folder, refuses a name already there, copies to `.partial`, checks it, renames (line 125), and prunes only `list_backups` names. Tests: given `test_a_backup_is_a_checked_copy`, `test_only_the_newest_are_kept`, `test_two_backups_in_one_second`, `test_refused_backups`; `test_a_new_copy_that_fails_its_check`.
- R5: `restore_backup` (line 133) checks the backup, sets the live file aside, then copies the backup in. Tests: the three given restore tests; `test_a_set_aside_name_that_already_exists`, `test_a_restore_needs_a_database_file`.
- R6: the `sqlite3` and logging searches.
- R7 to R9: the given `test_cli_backup.py`; `test_restoring_an_older_backup_asks_for_an_upgrade`, `test_the_command_refuses_a_keep_below_one`, `test_the_command_refuses_a_restore_without_a_database_file`.
- R10: the given files are identical and executable.

## Probe

None, as the guide says.

## Spot checks

Each change was made in `db/backup.py`, the three backup test files run, and the file restored.

1. Pruning deletes every file beyond `keep`: `test_only_the_newest_are_kept` fails.
2. `check_backup` opens read-write: with the not-a-file guard removed too, `test_a_file_that_is_not_a_backup` fails (`missing.db` is created). With the guard kept, no given test failed (the finding above); after the repair `test_a_check_changes_none_of_the_files_it_reads` fails.
3. Restore writes the backup in before setting the old database aside: `test_restore_puts_the_backup_back_and_keeps_what_it_replaced`, `test_restore_onto_a_new_machine_and_an_older_backup`, and `test_restoring_an_older_backup_asks_for_an_upgrade` fail.
4. `backup_name` uses local time (`astimezone()`): `test_backup_names_use_utc` and eight other tests fail on this machine (UTC-5).
5. The new copy gets its final name before the check: `test_a_new_copy_that_fails_its_check` fails.

## Out of scope

Absent: network code; encryption or compression; a web page; a change to `fin doctor`.
