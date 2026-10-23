# Verify Phase 34a: the audit trail, and every change a person makes

Spec: `docs/phases/phase-34a-audit-trail.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added the `audit_log` table (a given migration), `domain/audit.py`, `record_change` and `list_changes`, a hook in each repository function a person uses to change data, a new `assignments` area (moved functions), and `fin audit`. Four test files, the migration, and a diff to the split test were given.

These are correct and must not be reported: hooks written as one helper per area; the before value read before the change and the after value from the arguments; `list_changes` building its query step by step.

## 1. Gates

N is `3298` when Phase 36c was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 15 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_audit_rules.py tests/integration/test_migration_0012.py tests/integration/test_audit_trail.py tests/e2e/test_cli_audit.py --no-cov` | exactly `15 passed` |
| `.venv/bin/python -m pytest tests/unit/test_repositories_split.py tests/integration/test_migration_chain.py tests/integration/test_migrations.py tests/unit/test_text.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.audit --cov=finances.db.repositories --cov=finances.views.audit --cov=finances.cli.audit --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |
| `git grep -n --untracked -E "record_change|AuditRow" -- src/finances/cli src/finances/web` | no output |
| `git diff --stat HEAD -- tests` | only `tests/unit/test_repositories_split.py` |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope, the split test, and the new files: the migration, `domain/audit.py`, `repositories/audit.py`, `repositories/assignments.py`, `views/audit.py`, `cli/audit.py`, and the five test files. The migration and the split-test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R11 | gates 1 to 7 | pass |
| R7, R10 (edges) | the coder's `tests/integration/test_audit_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. Record `category_set` in `_assign` (so rules record too) | `test_rules_and_automatic_pairing_record_nothing` | no new rows | rows from the rule run |
| 2. Record every new pair, automatic ones too | the same | no new rows | a `transfer_confirmed` row |
| 3. Record a rename to the same name | `test_nothing_is_recorded_when_nothing_changes` | same count | one more |
| 4. Record before the budget's checks | `test_a_refused_change_records_nothing` | only `account_added` | a `budget_set` row too |
| 5. `record_change` stamps with `datetime.now` directly | `test_record_change_checks_and_fits` | `NOON` | the real time |
| 6. `list_changes` oldest first | `test_list_changes_newest_first_and_filters` | Pat Example first | Test A first |

## 6. Out of scope

Each must be absent: a statement, backup, or sync event; a History page; an `agent` who; a way to edit or delete rows; a write from `cli` or `web` to the trail.
