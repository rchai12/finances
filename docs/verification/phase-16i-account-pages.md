# Verify Phase 16i: account pages

Spec: `docs/phases/phase-16i-account-pages.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a page per account (and per card of an account) with details, spending by group, 12 months, balance history, and latest transactions, and links to it from four pages. Five templates and one test file were given; no migration.

These are correct and must not be reported: filtering flows in Python; a private helper in `app.py` for the page.

## 1. Gates

N is `2798` when Phase 16h was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 11 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_account_page.py --no-cov` | exactly `11 passed` |
| `.venv/bin/python -m pytest tests/integration/test_web_pages.py tests/integration/test_web_search.py tests/integration/test_web_transfers.py tests/integration/test_web_reports.py tests/integration/test_web_accounts_and_bulk.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.views --cov=finances.analysis --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|timedelta|sum\(" -- src/finances/web` | no output |
| `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/db/repositories.py
 M src/finances/web/app.py
 M src/finances/web/templates/accounts.html
 M src/finances/web/templates/reports.html
 M src/finances/web/templates/transactions.html
 M src/finances/web/templates/transfers.html
?? src/finances/analysis/account_page.py
?? src/finances/views/account_page.py
?? src/finances/web/templates/account.html
?? tests/integration/test_account_page_more.py
?? tests/integration/test_web_account_page.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R2 to R5 | gates 2 and 3 | pass |
| R1, R2 (edges), R3 (closed, joint) | the coder's `tests/integration/test_account_page_more.py` | each item of the spec's "Tests to write" has a test |
| R2 | read `account_page` | one `load_flows` call; flows kept by account name and card; spending and months from Phase 12a's functions |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

Each line names the given input that decides it. Make the change, run the given tests, and see one fail; if none does, that is a finding.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. Spending is not filtered by account | Test Checking's utility bill in May | no `Home` row on Test Card's page | a `Home` row |
| 2. The card filter is ignored in spending | `&card=2222` | `Uncategorized $15.00`, `Food $5.00` | `Food $199.01` first |
| 3. Balance history comes oldest first | three snapshots | 2026-05-20 first | 2026-03-31 first |
| 4. An unknown card is accepted | `&card=3333` | `404`, `card not found` | `200` |
| 5. The months end with last month | today is 25 May | last row `2026-05` | last row `2026-04` |

## 6. Out of scope

Each must be absent: charts or JavaScript; a change to the security policy; forms on the account page.
