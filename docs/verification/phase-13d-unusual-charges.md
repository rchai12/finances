# Verify Phase 13d: unusual charges

Spec: `docs/phases/phase-13d-unusual-charges.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added two findings, `duplicate` and `large_first_charge`, to the Phase 13b engine and the report. One template, two test files, and a change to `test_the_types` were given; no migration.

These are correct and must not be reported: a `Counter` or `defaultdict` for the groups; reusing the report's all-history flows for `seen`.

## 1. Gates

N is `2829` when Phase 16k was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 6 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_unusual_charges.py tests/e2e/test_cli_unusual_charges.py --no-cov` | exactly `6 passed` |
| `.venv/bin/python -m pytest tests/unit/test_insights.py tests/e2e/test_cli_insights.py tests/integration/test_web_insights.py tests/integration/test_web_search.py tests/integration/test_web_dashboard.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.insights --cov=finances.analysis.insights --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/analysis/insights.py
 M src/finances/domain/insights.py
 M src/finances/web/templates/insights.html
 M tests/unit/test_insights.py
?? tests/e2e/test_cli_unusual_charges.py
?? tests/unit/test_unusual_charges.py
?? tests/unit/test_unusual_charges_more.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R4 | gates 2 and 3 | pass |
| R2, R3 (edges) | the coder's `tests/unit/test_unusual_charges_more.py` | each item of the spec's "Tests to write" has a test |
| test change | `git diff HEAD -- tests/unit/test_insights.py` | exactly the spec's diff |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

Each line names the given input that decides it. Make the change in the named function, run the given tests, and see one fail; if none does, that is a finding.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `duplicates` ignores the account | BAZ BOOKS on Test Card and Test Checking, same day and amount | no BAZ BOOKS finding | a BAZ BOOKS finding |
| 2. `duplicates` counts a refund as a charge | QUUX DELI −$5.00 and +$5.00 on one day | no QUUX DELI finding | a QUUX DELI finding |
| 3. `large_first_charges` uses the first charge, not the largest | NEW TV ($10.00 on 2 May, $600.00 on 8 May) | `$600.00 on 2026-05-08` | no NEW TV finding |
| 4. `insights_report` builds `seen` from the three earlier months only | BIG HOTEL in December and again in May | no BIG HOTEL row in May | a BIG HOTEL row |
| 5. The 3-times rule is strict (`>`) | NEW TV at exactly $300.00 against a $100.00 average | a finding | none |

## 6. Out of scope

Each must be absent: a migration; merchant merging; a change to the other findings.
