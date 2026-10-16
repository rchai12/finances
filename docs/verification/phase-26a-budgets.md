# Verify Phase 26a: budgets

Spec: `docs/phases/phase-26a-budgets.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added budgets (migration 0010, given), their rules (pure), a report, the `over_budget` finding, and `fin budgets`. Three test files and a change to `test_the_types` were given.

These are correct and must not be reported: integer arithmetic for the half-up percents; `spending_lines` called twice (by category, by group).

## 1. Gates

N is `2838` when Phase 13d was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 26 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_budgets.py tests/integration/test_migration_0010.py tests/e2e/test_cli_budgets.py --no-cov` | exactly `26 passed` |
| `.venv/bin/python -m pytest tests/unit/test_insights.py tests/unit/test_unusual_charges.py tests/e2e/test_cli_insights.py tests/e2e/test_cli_category_editing.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.budgets --cov=finances.domain.insights --cov=finances.analysis.budgets --cov=finances.analysis.insights --cov=finances.views.budgets --cov=finances.cli.budgets --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|sorted\(" -- src/finances/cli/budgets.py` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/analysis/insights.py
 M src/finances/cli/main.py
 M src/finances/db/orm.py
 M src/finances/db/repositories.py
 M src/finances/domain/insights.py
 M src/finances/domain/models.py
 M tests/unit/test_insights.py
?? src/finances/analysis/budgets.py
?? src/finances/cli/budgets.py
?? src/finances/db/migrations/versions/0010_budgets.py
?? src/finances/domain/budgets.py
?? src/finances/views/budgets.py
?? tests/e2e/test_cli_budgets.py
?? tests/integration/test_budgets_more.py
?? tests/integration/test_migration_0010.py
?? tests/unit/test_budgets.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R9 | gates 2 and 3 | pass |
| R1, R2, R6 (edges) | the coder's `tests/integration/test_budgets_more.py` | each item of the spec's "Tests to write" has a test |
| test change | `git diff HEAD -- tests/unit/test_insights.py` | exactly the spec's diff |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

Each line names the function and the given input that decides it. Make the change, run the given tests, and see one fail; if none does, that is a finding.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `budget_report` adds charges only, ignoring refunds | Groceries: $120.00 less a $20.00 refund | `$100.00`, `50%` | `$120.00`, `60%` |
| 2. `budget_report` takes a group's spent from its budgeted categories only | Food: Dining, Groceries, and Coffee & Dessert | `$404.50` | `$400.00` |
| 3. `over_budget` reports spent equal to the target | Groceries at exactly $200.00 of $200.00 (unit test) | no finding | a finding |
| 4. `over_budget` makes `high` strict (> 1.5 times) | Food at exactly 150% (unit test) | `high` | `medium` |
| 5. `delete_category` leaves the budget | deleting Groceries with a budget | exit 0; Groceries gone from the list | an error (foreign key) |

## 6. Out of scope

Each must be absent: a web page; rollover; budgets per person or account.
