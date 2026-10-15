# Review: Phase 24b

- Verdict: PASS
- Passed: 2652
- Findings: 0
- Approved deviations: one assertion in the given `tests/integration/test_web_backups.py` (`test_only_backups_in_the_folder_can_be_deleted`) compares `NOT_A_BACKUP.format(name).strip()`, approved by the owner: for the empty name the expected paragraph was `" is not a backup in the folder"`, and `tests/support.Page` strips paragraph text, so that case failed with any code.
- For the architect: a given test expecting a paragraph, cell, or summary that begins or ends with a space cannot pass, since `Page` strips them; expect the stripped text, or avoid empty values in messages that start with the value.

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2652 passed`, `All checks passed.`, no critical-coverage gaps (N + 35 = 2646; 6 more are the coder's)
- Given tests: `35 passed` (after the approved one-line change)
- Phase 24's tests: `tests/integration/test_backup.py tests/e2e/test_cli_backup.py`, 18 passed, unchanged
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- All three searches: no output
- Scope: `git status --short` lists exactly the guide's 11 paths, plus this review
- Given files: `layout.html`, `backups.html`, `backup_confirm.html`, and `docs/backups.md` are identical to the spec's blocks; `tests/integration/test_web_backups.py` differs only in the approved line

## Requirement checklist

- R1: `list_set_asides` (`db/backup.py:67`) shares `_named` with `list_backups`; `taken_at` (line 72) reads the stamp from either name, in UTC. Tests: `test_a_missing_folder_has_no_set_aside_copies`, `test_taken_at_reads_both_kinds_of_name`, and the given page tests.
- R2: `find_backup` (line 77) checks the name against both patterns with `fullmatch` (line 80) before `is_file`; `delete_backup` (line 88) deletes only what it returns. Tests: `test_a_folder_with_a_backup_name_is_not_a_backup` and the given delete and restore refusals.
- R3: the coverage command and `check.py`'s critical step show `db/backup.py` fully covered.
- R4: `size_text` (`views/format.py:29`) uses integer arithmetic; the given `test_size_text` (8 cases) and page tests pass.
- R5 to R8: the given tests pass. `POST /backups/run` (`web/app.py:1102`) uses `refused` (503 on an old database); the delete and restore routes use `forged` (origin and token only). The restore route checks the name, then the backup, then the typed name, then restores.
- R9: `_now` (line 233) is module level; the routes read it at call time, so the given tests' replacements apply.
- R10: `_RESTORE_GATE` (line 178) is a `threading.Lock`; `_engine` (line 213) acquires and releases it before opening an engine; the restore route holds it only around `restore_backup` (line 1165). Test: `test_requests_wait_while_a_restore_runs` (a request in another thread stays unfinished for 0.2 seconds while the gate is held, then answers 200).
- R8 (GET unreadable): `test_opening_an_unreadable_backup_shows_the_backups_page`.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the backup tests of Phases 24 and 24b run, and the file restored.

1. `find_backup` accepts any file in the folder: `test_only_backups_in_the_folder_can_be_deleted` (`notes.txt`, `../finances.db`, the upper-case name) and `test_only_backups_in_the_folder_can_be_restored` (`notes.txt`, `../finances.db`) fail.
2. The typed name is compared ignoring case and spaces: `test_restore_needs_the_name_typed_exactly` (the upper-case name and the leading space) fails.
3. `POST /backups/restore` checks the schema: `test_an_older_backup_asks_for_an_upgrade` fails (its second restore answers 503).
4. Restore skips setting the current database aside: four given 24b restore tests and three Phase 24 tests fail, among them `test_restore_after_typing_the_name` and `test_a_restore_can_be_undone`.
5. `size_text` rounds megabytes down: `test_size_text[1625293-1.6 MB]` fails.

## Out of scope

Absent: a download or upload route (search 3); a way to change the folder or `keep` on the web; `fin db upgrade` from the web; JavaScript (search 2).
