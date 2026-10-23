# Verify Phase 34b: the system's events, and the History page

Spec: `docs/phases/phase-34b-events-and-history.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder recorded statement imports, backup deletions, and restores in the audit trail, and added a read-only History page. A template, a menu diff, two test files, and a diff to three earlier tests were given; no migration.

These are correct and must not be reported: the History rows built with `zip`; `note_backup_*` sharing one private helper; the restore route reading the name from `path.name` or from the form (they are equal after `find_backup`).

## 1. Gates

N is `3323` when Phase 34a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 21 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_audit_events.py tests/integration/test_web_history.py --no-cov` | exactly `21 passed` |
| `.venv/bin/python -m pytest tests/unit/test_audit_rules.py tests/e2e/test_cli_audit.py tests/unit/test_web_split.py tests/integration/test_web_backups.py tests/e2e/test_cli_backup.py tests/integration/test_web_nav_sync.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.audit --cov=finances.db.backup_records --cov=finances.db.repositories --cov=finances.views.audit --cov=finances.web.routes.history --cov=finances.web.routes.backups --cov=finances.cli.backup --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | the three files of the given diff |
| `git diff --stat HEAD -- src/finances/db/backup.py` | nothing |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope, `layout.html`, the three earlier test files, and the new `db/backup_records.py`, `web/routes/history.py`, `templates/history.html`, and three test files. The template and both diffs equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R8 | gates 1 to 6 | pass |
| R2, R4 (edges) | the coder's `tests/integration/test_history_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. Record the restore before `restore_backup` (in the database it replaces) | `test_a_restore_keeps_the_restored_history_and_adds_one_row` | account_added, backup_restored | no backup_restored row in the restored database |
| 2. `note_backup_restored` skips the revision check | `test_restoring_a_backup_from_before_the_trail_records_nothing` | `False`, `restored-old` | an error (no table) |
| 3. Record imports as `person` | `test_a_statement_import_is_recorded_as_the_system` | `system` | `person` |
| 4. `/history` accepts any action text | `test_refused_filters[action=nope-...]` | 400 | 200 |
| 5. `change_link` sends a rule to its own page | `test_each_kind_links_to_its_page[rule-2-/categories]` | `/categories` | `/categories/rules/2` |

## 6. Out of scope

Each must be absent: a change to `db/backup.py`; sync or feed events; an `agent` who; a way to edit or delete rows.
