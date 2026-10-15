# Verify Phase 13b: findings and merchant stats

Spec: `docs/phases/phase-13b-findings-and-merchant-stats.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added six findings and merchant stats (pure), `previous_cents` on Phase 13a's `Recurring`, a report in `analysis`, rows in `views`, and `fin insights` and `fin merchants`. Two test files were given; no migration.

These are correct and must not be reported: integer arithmetic for half-up rounding; one helper per finding or a shared grouping helper; `re` for splitting merchants into words.

## 1. Gates

N is `2490` when Phase 13a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 21 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_insights.py tests/e2e/test_cli_insights.py --no-cov` | exactly `21 passed` |
| `.venv/bin/python -m pytest tests/unit/test_recurring.py tests/e2e/test_cli_recurring.py --no-cov` | `33 passed` (Phase 13a unchanged) |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.insights --cov=finances.domain.recurring --cov=finances.analysis.insights --cov=finances.views.insights --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)|float" -- src/finances/domain/insights.py src/finances/domain/recurring.py` | no output |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|sorted\(|timedelta|spikes\(|merchant_stats\(" -- src/finances/cli/reports.py` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/cli/main.py
 M src/finances/cli/reports.py
 M src/finances/domain/recurring.py
?? src/finances/analysis/insights.py
?? src/finances/domain/insights.py
?? src/finances/views/insights.py
?? tests/e2e/test_cli_insights.py
?? tests/integration/test_insights_report.py
?? tests/unit/test_insights.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R9, R11 to R13 | gate 2 | passes |
| R1 | `git diff HEAD -- src/finances/domain/recurring.py` | only `previous_cents` added (last field, default `None`) and set in the series builder |
| R10, R3 (refund only), R4 (thresholds) | the coder's `tests/integration/test_insights_report.py` | each item of the spec's "Tests to write" has a test |
| R10 | read `insights_report` | one `load_flows` call over four months; recurring from Phase 13a; no second definition of spending |
| R14 | read `cli/reports.py` | no sums, sorting, or rule checks |

## 4. Probe

None: the given tests cover each finding with literal values, through the real database. Use the spot checks instead.

## 5. Spot checks

For each change, say which given test (or test of the coder's) would fail. If none would, that is a finding.

1. A spike with a baseline of zero is reported.
2. The fee rule matches `FEED` (substring instead of word).
3. `frequent_small` counts refunds as visits.
4. Overlaps include an inactive series.
5. The baseline divides by the number of earlier months that had spending instead of 3.

## 6. Out of scope

Each must be absent: a migration; a stored finding; a web page; any change to Phase 13a's rules other than `previous_cents`.
