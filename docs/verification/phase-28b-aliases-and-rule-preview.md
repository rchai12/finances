# Verify Phase 28b: aliases on the web and the rule preview

Spec: `docs/phases/phase-28b-aliases-and-rule-preview.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder put 28a's aliases on the Categories page (a card, two forms, two notices) and added a rule preview: `check_rule` taken out of `create_rule`, `preview_rule` in the categorize service, its texts in views, `fin rules preview`, and a preview route behind a second button on the rule form. A template diff, a diff to one earlier test, and two test files were given.

These are correct and must not be reported: how `preview_rule` loads the examples' dates and accounts (one query or several); a private helper shared by `add_rule` and the preview route to read the form; `back` read and ignored; the preview's `CategoryRule` built inside `preview_rule` or by a private helper.

## 1. Gates

N is `3507` when Phase 28a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 12 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_aliases_and_preview.py tests/e2e/test_cli_rule_preview.py --no-cov` | exactly `12 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.db.repositories --cov=finances.categorize.service --cov=finances.views.categories --cov=finances.cli.categories --cov=finances.web.routes.categories --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | only `tests/unit/test_repositories_split.py` |

This search must print nothing:

- `git grep -n "pick_rule\|merchant_names\|rule_matches" -- src/finances/web src/finances/cli src/finances/views`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files and the two templates of the spec's Scope, `tests/unit/test_repositories_split.py`, and three new test files. The templates and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_no_aliases_yet`); `git diff HEAD -- src/finances/web/templates` | passes; the diff equals the spec's |
| R2 | gate 2 (`test_merging_on_the_page`, `test_a_refused_alias`) | pass |
| R3 | gate 2 (`test_unmerging_on_the_page`); read `NOTICES` | passes; both texts as the spec gives them |
| R4 | the coder's `check_rule` tests; read `create_rule` | it calls `check_rule` and makes no check of its own |
| R5 | the coder's preview tests; read `preview_rule` | the deciding cases of "Tests to write" each have a test; nothing is added, flushed, or recorded |
| R6 | gate 2 (`tests/e2e/test_cli_rule_preview.py`) | passes |
| R7 | gate 2; read the command | it calls `require_current_schema()` and only prints what views give |
| R8 | gate 2 (`test_previewing_a_rule`, `test_a_refused_preview`, `test_both_rule_forms_offer_a_preview`) | pass |
| R9 | gate 4 | only that file |

## 4. Probe

None. Look once in a browser: `fin web` on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with a few purchases, press Preview on the Categories page's rule form and see the count and the table without a rule added, then Add rule from the same filled form.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `preview_rule`: count categories set by hand | coder: a hand-set transaction the rule matches | not counted | counted |
| 2. `preview_rule`: count every transaction the new rule wins | coder: `contains "ACME"` at 5 over `ACME COFFEE` already in Dining | not counted | counted |
| 3. `preview_rule`: give the new rule id 0 | coder: the tie at priority 0 with an older rule | not counted | counted |
| 4. `preview_rule`: match `clean_merchant` only | coder: alias, `equals "ACME COFFEE"`, purchase `ACME CAFE` | counted | not counted |
| 5. `preview_rule`: oldest first | given `test_a_preview_shows_the_ten_newest` | ids 11 to 2 | ids 1 to 10 |
| 6. `preview_more`: always None | given `test_a_preview_shows_the_ten_newest` | `Showing the 10 newest.` | absent |
| 7. `preview_text`: no singular | given `test_one_transaction` | `1 transaction` | `1 transactions` |
| 8. `preview_text`: the name as typed | given `test_no_transactions` (`dining`) | `Dining` | `dining` |
| 9. alias add route: no categorize run | given `test_merging_on_the_page` | 1 in Coffee & Dessert | 1 without a category |
| 10. alias delete route: no categorize run | given `test_unmerging_on_the_page` | `{2, 3}` | `{1, 2, 3}` |
| 11. preview route: call `create_rule` | given `test_previewing_a_rule` | one rule | two rules |

## 6. Out of scope

Each must be absent: a preview on the rule edit page or for an edit or a delete; a preview of an alias; a change to `fin aliases`, 28a's alias rules, or the uncategorized lists; a page other than Categories after a preview.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
