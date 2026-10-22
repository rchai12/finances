# Verify Phase 35a: Spent, Refunds, and Net

Spec: `docs/phases/phase-35a-spent-refunds-net.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder split spending into Spent (purchases), Refunds, and Net in the spending tables of the terminal, the Reports page, and the account page, and made every net spending figure (spending, months, budgets) read `$X back` instead of a minus. Three test files and a diff to six earlier test files were given; no migration.

These are correct and must not be reported: `refunds_cents` summed in the same loop as `spent_cents`; `net_text` written with a conditional expression; `max(..., 0)` or an `if` for the used percentage.

## 1. Gates

N is `3093` when Phase 16n was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 14 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_net_text.py tests/e2e/test_cli_refunds.py tests/integration/test_web_refunds.py --no-cov` | exactly `14 passed` |
| `.venv/bin/python -m pytest tests/e2e/test_cli_spending.py tests/integration/test_web_reports.py tests/integration/test_web_account_page.py tests/integration/test_web_search.py tests/unit/test_spending.py tests/integration/test_account_and_bulk_repositories.py tests/integration/test_web_cards.py tests/unit/test_web_cards_style.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.spending --cov=finances.views.spending --cov=finances.views.format --cov=finances.views.months --cov=finances.views.budgets --cov=finances.views.account_page --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | exactly the six files of the given diff |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the seven source files and two templates of the spec's Scope, the six earlier test files, and the four new test files. The diff of the six earlier test files equals the spec's given diff.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R10 | gates 1 to 5 | pass |
| R5 to R8 (edges) | the coder's `tests/integration/test_refunds_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `spending_lines` adds every `SPENDING` flow's amount to refunds, of either sign | `test_a_tie_goes_by_name_ignoring_case_and_a_refund_can_win` (QUUX) | `refunds_cents=700` | `500` |
| 2. `summarize` counts money in without a category as refunds | `test_cli_spending.py::test_a_month_by_category` (a $25.00 unsorted credit) | `Refunds: $5.99.` | `Refunds: $30.99.` |
| 3. `spending_rows` puts the net in Spent | the same, Groceries | `$25.99` | `$20.00` |
| 4. `net_text` writes a minus | `test_net_spending_never_shows_a_minus[-599-$5.99 back]` | `$5.99 back` | `-$5.99` |
| 5. `amount_class` leaves `back` plain | `test_the_reports_page` | two green `$5.99 back` cells | none |
| 6. `month_rows` keeps `format_cents` | `test_the_months_table_says_back` | `$5.99 back` | `-$5.99` |
| 7. `budget_rows` shows the used percentage below zero | `test_a_budget_with_money_back_is_not_below_zero_used` | `0%` | `-6%` |

## 6. Out of scope

Each must be absent: a refund label or filter on transactions; matching refunds to purchases; any change to a total, budget left, the Change column, insights, or the pie chart.
