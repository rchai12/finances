# Verify Phase 28e: splits in the reports and the terminal

Spec: `docs/phases/phase-28e-splits-in-reports.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder made the reports count a split transaction's parts where money is grouped by category and the whole transaction where charges are counted at a merchant, made search find each part with its own amount, added two pure helpers to the critical `domain/splits.py`, a repository function, and three `fin transactions` commands. A diff to one earlier test and three test files were given.

These are correct and must not be reported: `insights_report` loading flows twice (whole and in parts) or loading parts once and rebuilding whole flows from them, as long as each finding reads what R2 and R3 say; the part flows built inside `flows_for` or by a private helper; `cli/splits.py` loading the category names with `list_categories`.

## 1. Gates

N is `3605` when Phase 28d was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.` (its critical coverage step includes `domain/splits.py`); at least N + 24 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_split_parts.py tests/integration/test_split_reports.py tests/e2e/test_cli_splits.py --no-cov` | exactly `24 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.splits --cov=finances.db.repositories --cov=finances.analysis.spending --cov=finances.analysis.months --cov=finances.analysis.budgets --cov=finances.analysis.account_page --cov=finances.analysis.insights --cov=finances.analysis.search --cov=finances.views.transactions --cov=finances.mcp_server --cov=finances.cli.splits --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | only `tests/unit/test_repositories_split.py` |
| `git diff --stat HEAD -- src/finances/analysis/recurring.py src/finances/analysis/forecast.py src/finances/analysis/names.py src/finances/analysis/refunds.py` | no output |

This search must print nothing:

- `git grep -n "parts=True" -- src/finances/analysis/recurring.py src/finances/analysis/forecast.py src/finances/analysis/names.py src/finances/analysis/refunds.py src/finances/views src/finances/cli src/finances/web src/finances/mcp_server`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope (one of them new), `tests/unit/test_repositories_split.py`, and four new test files. The diff equals the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_flows_whole_and_in_parts`); the coder's transfer-part case | pass |
| R2 | gate 2 (`test_spending_counts_the_parts`); the coder's month, budget, account page, and spikes cases | pass |
| R3 | gate 5; the coder's recurring and merchant stats cases; read `insights_report` | no change in the four modules; each finding reads what R3 says |
| R4 | gate 2 (`test_a_drill_down_finds_the_part`); the coder's kind and limit cases | pass |
| R5 | the coder's MCP and Transactions page cases | parts' amounts |
| R6 | gate 2 (`test_split_parts.py`); gate 1's critical coverage step | pass |
| R7 | the coder's order cases; read `split_by_sizes` | not found, then sizes, then `set_split` |
| R8 | gate 2 (`test_splitting`, `test_refused`) | pass |
| R9 | gate 2 (`test_unsplitting`) | passes |
| R10 | gate 2 (`test_splitting`, `test_unsplitting`, `test_refused`) | pass |
| R11 | gate 4 | only that file |

## 4. Probe

None. Look once in the terminal: on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with one purchase, `fin transactions split --id 1 --part "12.00 Groceries" --part "8.00 Dining"`, then `fin spending --month` for its month, and see Groceries and Dining lines of $12.00 and $8.00.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `flows_for`: a part takes the transaction's first part's group | given `test_flows_whole_and_in_parts` (Home & Garden) | `Home` | `Food` |
| 2. `search_transactions`: whole flows | given `test_a_drill_down_finds_the_part` | `(1, -1200, "Groceries")` | nothing found |
| 3. `spending_report`: whole flows | given `test_spending_counts_the_parts` | three category lines | `Split` 2000 and Dining |
| 4. `recurring_charges`: flows in parts | coder: STREAMFLIX split in its fourth month | one series | the series broken |
| 5. `found_rows`: the transaction's amount | coder: the Transactions page | `-$12.00` and `-$8.00` | `-$20.00` twice |
| 6. `signed_parts`: negative for a zero amount | given `(0, [100, 100])` | `[100, 100]` | `[-100, -100]` |
| 7. `parse_part`: split on every space | given `"  $8   Home & Garden  "` | `Home & Garden` | refused or `Home` |
| 8. `fin transactions unsplit`: no categorize run | given `test_unsplitting` | two lines | one line |
| 9. `split_by_sizes`: sizes before the transaction | coder: id 9 with a size of 0 | `transaction not found` | the size message |
| 10. `merchant_stats` input: flows in parts | coder: a split purchase | counted once | twice |
| 11. `_transaction_item`: the transaction's amount | coder: `list_transactions` | `-1200` and `-800` | `-2000` twice |

## 6. Out of scope

Each must be absent: a page or form for splits; a mark or column saying a row is a part; any change to `recurring.py`, `forecast.py`, `names.py`, or `refunds.py`.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
