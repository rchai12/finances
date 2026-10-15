# Verify Phase 24b: backups on the web

Spec: `docs/phases/phase-24b-backups-on-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a Backups page with back up now, delete, and restore (each delete and restore after a confirmation page), four functions in the critical module `db/backup.py`, `size_text`, a restore gate, and `_now`. Three templates, the backups guide, and one test file were given; no migration.

These are correct and must not be reported: a private helper in `app.py` for the Backups page; a second form-check helper that skips the database check; `Decimal` or integer arithmetic in `size_text`.

## 1. Gates

N is `2611` when Phase 24 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 35 passed, 0 failed, 0 skipped, 0 xfailed; no critical-coverage gaps |
| `.venv/bin/python -m pytest tests/integration/test_web_backups.py --no-cov` | exactly `35 passed` |
| `.venv/bin/python -m pytest tests/integration/test_backup.py tests/e2e/test_cli_backup.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.db.backup --cov=finances.views --cov=finances.web --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|\.unlink\(|before-restore|finances-\[" -- src/finances/web` | no output |
| `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static` | no output |
| `git grep -n --untracked -E "FileResponse|UploadFile|Content-Disposition|attachment" -- src/finances/web` | no output |

## 2. Scope paths

```
 M docs/backups.md
 M docs/progress.md
 M src/finances/db/backup.py
 M src/finances/views/format.py
 M src/finances/web/app.py
 M src/finances/web/templates/layout.html
?? src/finances/views/backups.py
?? src/finances/web/templates/backup_confirm.html
?? src/finances/web/templates/backups.html
?? tests/integration/test_backups_page_more.py
?? tests/integration/test_web_backups.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R2, R4 to R9 | gate 2 | passes |
| R1, R10, R8 (GET unreadable) | the coder's `tests/integration/test_backups_page_more.py` | each item of the spec's "Tests to write" has a test |
| R2 | read `find_backup` | the name is checked against both patterns with `fullmatch` before any file-system call |
| R10 | read `_engine` and the restore route | the gate is held only around `restore_backup`; `_engine` waits on it |

## 4. Probe

None: the given tests restore and delete real files through the real routes. Use the spot checks instead.

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. `find_backup` accepts any file in the folder.
2. The typed name is compared ignoring case or spaces.
3. `POST /backups/restore` checks the database schema (an older backup then cannot be followed by another restore).
4. Restore skips setting the current database aside.
5. `size_text` rounds megabytes down.

## 6. Out of scope

Each must be absent: a download or upload route; a way to change the folder or `keep` on the web; `fin db upgrade` from the web; JavaScript.
