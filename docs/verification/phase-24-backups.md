# Verify Phase 24: backups

Spec: `docs/phases/phase-24-backups.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added `fin backup run`, `list`, and `restore` over SQLite's own backup, two settings, a critical module `db/backup.py`, and given scripts and docs. Two test files and a change to `tests/conftest.py` were given; no migration.

These are correct and must not be reported: `shutil` or `Path.rename` for the final rename; `re` for backup names; a helper that opens SQLite read-only.

## 1. Gates

N is `2578` when Phase 16e was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 18 passed, 0 failed, 0 skipped, 0 xfailed; the critical coverage step lists `db/backup.py` |
| `.venv/bin/python -m pytest tests/integration/test_backup.py tests/e2e/test_cli_backup.py --no-cov` | exactly `18 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.db.backup --cov=finances.cli.backup --cov=finances.config --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(import sqlite3|from sqlite3)" -- src` | only lines in `src/finances/db/backup.py` |
| `git grep -n --untracked -E "log(ger)?\.(info|warning|error|critical)" -- src/finances/db/backup.py src/finances/cli/backup.py` | no output |
| `ls -l scripts/install-backup-schedule.sh scripts/uninstall-backup-schedule.sh` | both executable |
| `bash -n scripts/install-backup-schedule.sh && bash -n scripts/uninstall-backup-schedule.sh` | no output |

Do not run the scripts: they install a `launchd` job for the real user.

## 2. Scope paths

```
 M docs/progress.md
 M scripts/critical_modules.txt
 M src/finances/cli/main.py
 M src/finances/config.py
 M tests/conftest.py
?? docs/backups.md
?? scripts/install-backup-schedule.sh
?? scripts/uninstall-backup-schedule.sh
?? src/finances/cli/backup.py
?? src/finances/db/backup.py
?? tests/e2e/test_cli_backup.py
?? tests/integration/test_backup.py
?? tests/integration/test_backup_more.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R2, R4, R5, R7 to R9 | gate 2 | passes |
| R1, R3, R4 (failed check), R5 (set-aside clash) | the coder's `tests/integration/test_backup_more.py` | each item of the spec's "Tests to write" has a test |
| R3 | read `check_backup` | read-only URI open; never creates the file |
| R4 | read `make_backup` | `.partial`, then check, then rename, then prune; prune touches only backup names |
| R6 | gates 4 and 5 | as expected |
| given files | compare with the spec's blocks; `git diff HEAD -- tests/conftest.py` | identical; exactly the spec's diff |

## 4. Probe

None: the given tests make, prune, check, and restore real database files. Use the spot checks instead.

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. Pruning deletes every file in the folder beyond `keep`, not only backup names.
2. `check_backup` opens read-write (a missing file would be created).
3. Restore writes the backup in before setting the old database aside.
4. `backup_name` uses local time.
5. The new copy is given its final name before it is checked.

## 6. Out of scope

Each must be absent: network code; encryption or compression; a web page; a change to `fin doctor`.
