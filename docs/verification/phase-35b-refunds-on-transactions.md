# Verify Phase 35b: refunds on transactions

Spec: `docs/phases/phase-35b-refunds-on-transactions.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a refund rule, a `refund` search kind, a pure match from a refund to its likely purchase, refund facts for a transaction's page, and a note on uncategorized money in on a card. Templates, CSS, and three earlier test lines were given as diffs; three test files were given.

These are correct and must not be reported: the transactions loaded once for both directions in `refund_facts`; `max` with a key for the latest purchase; the note built with `str.format`.

## 1. Gates

N is `3111` when Phase 35a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 27 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_refunds.py tests/integration/test_web_refunds_found.py tests/e2e/test_cli_card_credits.py --no-cov` | exactly `27 passed` |
| `.venv/bin/python -m pytest tests/integration/test_transaction_search.py tests/integration/test_web_search.py tests/integration/test_web_account_page.py tests/integration/test_web_cards.py tests/unit/test_web_style.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.spending --cov=finances.domain.refunds --cov=finances.analysis.search --cov=finances.analysis.refunds --cov=finances.views.transactions --cov=finances.views.categories --cov=finances.web.routes.transactions --cov=finances.web.routes.categories --cov=finances.cli.categories --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |
| `git diff --stat HEAD -- tests` | the three files of the earlier-tests diff |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope, the five templates and `app.css` of the given diff, the three earlier test files, and the four new test files. The template, CSS, and earlier-test diffs equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R9 | gates 1 to 6 | pass |
| R5 (edges) | the coder's `tests/integration/test_refunds_found_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None. Use the spot checks.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `likely_purchase` takes the earliest purchase | `test_the_likely_purchase[the latest that fits]` | 2 | 1 |
| 2. `likely_purchase` allows purchases after the refund | `[after the refund]` | `None` | 1 |
| 3. The window stops one day short (`<` for the 90th day) | `[90 days before]` | 1 | `None` |
| 4. A tie goes to the lowest id | `[a tie goes to the newest]` | 5 | 3 |
| 5. `is_refund` also counts money in without a category | `test_refunds_carry_a_label` (QUUX CREDIT) | category cell empty | `refund` |
| 6. `refund_facts` lists every refund of the merchant on a purchase | `test_no_refund_section_where_none_applies[1]` | no section | a Refunds section |
| 7. `card_credits_note` counts every account's money in | `test_money_in_on_a_card_without_a_category` | `Money in on a card: 1, ...` | `2` |
| 8. `kind=refund` keeps spending of either sign | `test_only_refunds` | two rows | five |

## 6. Out of scope

Each must be absent: a migration or a stored match; a kind option in the terminal; a Kind column; a change to totals, reports, budgets, insights, or transfers.
