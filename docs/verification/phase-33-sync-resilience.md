# Verify Phase 33: sync resilience

Spec: `docs/phases/phase-33-sync-resilience.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder made `fin sync run` retry when SimpleFIN cannot be reached, stored each link's last failure (migration 0011, given) for `fin sync status` and `fin health`, and the given schedule scripts stamp each run. Four test files were given.

These are correct and must not be reported: the retry loop written as a `for` over the waits; `on_retry` printing through a small CLI helper. Do not run the schedule scripts: they install `launchd` jobs for the real user.

## 1. Gates

N is `2911` when Phase 32 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 15 passed, 0 failed, 0 skipped, 0 xfailed; no critical-coverage gaps |
| `.venv/bin/python -m pytest tests/integration/test_sync_resilience.py tests/integration/test_migration_0011.py tests/unit/test_health_sync_failures.py tests/e2e/test_cli_sync_resilience.py --no-cov` | exactly `15 passed`, in seconds (a real 30-second wait means `time.sleep` was bound early) |
| `bash -n scripts/install-sync-schedule.sh && bash -n scripts/install-backup-schedule.sh` | nothing |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.sync --cov=finances.domain.health --cov=finances.analysis.health --cov=finances.views.sync --cov=finances.cli.sync --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "urlopen|urllib\.request|socket\." -- src/finances` | only `src/finances/sync/transport.py` |

## 2. Scope paths

```
 M docs/progress.md
 M scripts/install-backup-schedule.sh
 M scripts/install-sync-schedule.sh
 M src/finances/analysis/health.py
 M src/finances/cli/sync.py
 M src/finances/db/orm.py
 M src/finances/db/repositories.py
 M src/finances/domain/health.py
 M src/finances/domain/models.py
 M src/finances/sync/runner.py
 M src/finances/sync/simplefin.py
 M src/finances/sync/transport.py
 M src/finances/views/sync.py
?? src/finances/db/migrations/versions/0011_sync_failures.py
?? tests/e2e/test_cli_sync_resilience.py
?? tests/integration/test_migration_0011.py
?? tests/integration/test_sync_resilience.py
?? tests/integration/test_sync_resilience_more.py
?? tests/unit/test_health_sync_failures.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R7 | gates 1 to 3 | pass |
| R3 (keychain, not set up), R4 (web) | the coder's `tests/integration/test_sync_resilience_more.py` | each item of the spec's "Tests to write" has a test |
| R4 | `git diff HEAD -- src/finances/web` | nothing: the web passes no waits |
| R7 | compare the scripts with the spec's blocks | identical |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

Each line names the function and the given input that decides it. Make the change, run the given tests, and see one fail; if none does, that is a finding.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `run_links` retries every `SyncError` | an answer with status 500 | 1 call, no wait | 4 calls, three waits |
| 2. `run_links` retries revoked access | an answer with status 403 | 1 call | 4 calls |
| 3. A good sync clears every link's failure | sam's stored failure, alex synced | sam's failure kept | none left |
| 4. `run_links` keeps the first failure instead of the newest | an older failure, then a new error | `NOW` and the new message | the older one |
| 5. `health_problems` drops the failures | a stored failure for alex | a `sync` problem naming link alex | none |

## 6. Out of scope

Each must be absent: retries of error answers; a change to the web; syncing more than once a day.
