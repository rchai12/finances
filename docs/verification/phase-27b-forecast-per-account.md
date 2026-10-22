# Verify Phase 27b: a 30-day forecast per account

Spec: `docs/phases/phase-27b-forecast-per-account.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a pure walk of a balance through expected items, a forecast per account built from that account's own series, and `fin forecast` (a summary, or one account day by day). Two test files were given; no migration.

These are correct and must not be reported: transfers counted in the forecast though `fin upcoming` leaves them out; a private helper that picks one account's charges and credits from the loaded flows.

## 1. Gates

N is `2954` when Phase 27a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 16 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_forecast.py tests/e2e/test_cli_forecast.py --no-cov` | exactly `16 passed` |
| `.venv/bin/python -m pytest tests/unit/test_upcoming.py tests/e2e/test_cli_upcoming.py tests/e2e/test_cli_recurring.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.forecast --cov=finances.analysis.forecast --cov=finances.views.forecast --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|sorted\(|timedelta" -- src/finances/cli/reports.py` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/cli/main.py
 M src/finances/cli/reports.py
?? src/finances/analysis/forecast.py
?? src/finances/domain/forecast.py
?? src/finances/views/forecast.py
?? tests/e2e/test_cli_forecast.py
?? tests/integration/test_forecast_more.py
?? tests/unit/test_forecast.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R8 | gates 2 and 3 | pass |
| R4, R5 (edges) | the coder's `tests/integration/test_forecast_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

Each line names the function and the given input that decides it. Make the change, run the given tests, and see one fail; if none does, that is a finding.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. Bills take `SPENDING` only | PAYMENT TO TEST CARD on checking | Checking out `-$620.00` | `-$120.00` |
| 2. Income leaves out `TRANSFER` | PAYMENT THANK YOU on the card | Card in `$500.00` | `$0.00` |
| 3. Series found over every account's flows | BAZ BOX (card only) | Checking out `-$620.00` | more, BAZ BOX in the checking detail |
| 4. The lowest point starts from the first step, not the start | Test Savings (only interest) | Lowest `$1,000.00` on 2026-05-25 | `$1,001.00` on 2026-05-30 |
| 5. `walk` replaces the lowest on a tie (`<=`) | `test_a_tie_keeps_the_earliest_day` | 2026-05-26 | 2026-05-28 |
| 6. `latest_balance` used for the start | Savings snapshot of $2,000.00 dated 2026-06-01 | `$1,000.00` as of 2026-05-24 | `$2,000.00` |
| 7. An account without a balance forecast from 0 | Test Brokerage | `No balance yet: Test Brokerage.` | a Brokerage row |

## 6. Out of scope

Each must be absent: a web page or chart; a migration; a household total; a change to `fin upcoming`.
