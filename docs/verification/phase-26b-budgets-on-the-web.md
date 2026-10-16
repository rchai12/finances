# Verify Phase 26b: budgets on the web

Spec: `docs/phases/phase-26b-budgets-on-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a Budgets page (set, remove, progress for a month) and a budgets block on the Home page, on top of Phase 26a. Three templates and one test file were given; no migration.

These are correct and must not be reported: a private helper in `app.py` for the Budgets page; reading the amount with `parse_money` in the route.

## 1. Gates

N is `2868` when Phase 26a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 16 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_budgets.py --no-cov` | exactly `16 passed` |
| `.venv/bin/python -m pytest tests/integration/test_web_dashboard.py tests/integration/test_web_pages.py tests/e2e/test_cli_budgets.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.analysis.dashboard --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|timedelta" -- src/finances/web` | no output |
| `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates/budgets.html src/finances/web/templates/dashboard.html` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/analysis/dashboard.py
 M src/finances/web/app.py
 M src/finances/web/templates/dashboard.html
 M src/finances/web/templates/layout.html
?? src/finances/web/templates/budgets.html
?? tests/integration/test_web_budgets.py
?? tests/integration/test_web_budgets_more.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R5 | gates 2 and 3 | pass |
| R1, links with `&` | the coder's `tests/integration/test_web_budgets_more.py` | each item of the spec's "Tests to write" has a test |
| R1 | `git diff HEAD -- src/finances/analysis/dashboard.py` | `budgets` added last, with a default |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

Each line names the place and the given input that decides it. Make the change, run the given tests, and see one fail; if none does, that is a finding.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `GET /budgets` counts the month gone from the real date, not `_today()` | today set to 25 May | `81%` | `100%` |
| 2. `dashboard` reports last month's budgets | today set to 25 May | Dining `$300.00` spent | `$0.00` |
| 3. A refused `POST /budgets/set` loses the typed amount | amount `ten` | the field holds `ten` | empty |
| 4. `POST /budgets/set` takes the amount as plain digits only | `$300.00` | `303`, target `$300.00` | `400` |
| 5. `GET /budgets` still lists the budgets after a bad month | `month=2026-13` | status `400`, no table | the table shown |

## 6. Out of scope

Each must be absent: charts of budgets; a change to how budgets count; JavaScript.
