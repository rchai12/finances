# Verify Phase 36b: views that only format (accounts, people, categories)

Spec: `docs/phases/phase-36b-views-that-only-format.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder moved the loading out of the accounts, people, and categories views into two new `analysis` modules, moved the card-credit count to `analysis`, and moved the transaction page's refund text from its route into `views/refunds.py`. Nothing a person sees may change. One test file and a diff to two earlier test files were given; no migration.

These are correct and must not be reported: a loader that reads the accounts once and passes them on; `card_credit_count` written as a loop; the route's variables named differently.

## 1. Gates

N is `3273` when Phase 36a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 8 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_views_take_data.py tests/integration/test_views.py tests/integration/test_category_views.py --no-cov` | all passed |
| `.venv/bin/python -m pytest tests/integration/test_web_pages.py tests/integration/test_web_categories.py tests/integration/test_web_refunds_found.py tests/e2e/test_cli_card_credits.py tests/integration/test_web_forms.py --no-cov` | all passed (pages unchanged) |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis.listings --cov=finances.analysis.categories --cov=finances.views.accounts --cov=finances.views.people --cov=finances.views.categories --cov=finances.views.refunds --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +(finances\.(db|sync)|sqlalchemy|keyring)" -- src/finances/views/accounts.py src/finances/views/people.py src/finances/views/categories.py src/finances/views/refunds.py` | no output |
| `git diff --stat HEAD -- tests` | the two files of the given diff |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the three changed views, the eight callers of the spec, the two earlier test files, and new `analysis/listings.py`, `analysis/categories.py`, `views/refunds.py`, `tests/unit/test_views_take_data.py`, and `tests/integration/test_listings_more.py`. No template changes.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R8 | gates 1 to 6 | pass |
| R1, R2 (edges) | the coder's `tests/integration/test_listings_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None: the earlier page and command tests pin every output these views make.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `card_credit_count` counts money in on any account | `test_uncategorized_lines_and_the_card_note` | 1 | 2 |
| 2. `views/categories.py` imports `list_categories` again | `test_only_the_frozen_views_still_load_data` | pass | fail |
| 3. `refund_view` returns a view for a purchase | `test_the_refund_sections` | `None` | a `RefundView` |
| 4. `account_rows` shows `None` for no owner | `test_account_rows_from_a_listing` | `""` | `"None"` |

## 6. Out of scope

Each must be absent: a change to `views/sync.py`, `views/transfers.py`, `views/backups.py`, `analysis/people.py`, or any template; a change to output.
