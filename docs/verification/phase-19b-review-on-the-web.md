# Verify Phase 19b: the review queue on the web

Spec: `docs/phases/phase-19b-review-on-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added the Review page (the agent's open proposals with checkboxes, two decision buttons, and its notes), a Suggested column on the Categories page, and a menu link. A template, two diffs, and one test file were given; no migration.

These are correct and must not be reported: the form read with `request.form()`; the decision functions held in a dict; the ids converted before the session opens.

## 1. Gates

N is `3397` when Phase 19a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 12 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_review.py --no-cov` | exactly `12 passed` |
| `.venv/bin/python -m pytest tests/integration/test_web_categories.py tests/unit/test_web_split.py tests/integration/test_web_nav_sync.py tests/e2e/test_cli_review.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis.review --cov=finances.views.review --cov=finances.web.routes.review --cov=finances.web.routes.categories --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | the two files of the given diff |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope, the two templates of the diff, the two earlier test files, and the new `routes/review.py`, `templates/review.html`, and two test files. The template and the diffs equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R7 | gates 1 to 5 | pass |
| R1, R4 (edges) | the coder's `tests/integration/test_web_review_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None. Look once in a browser: with `fin web serve` on a temporary `FIN_DATA_DIR` (never the owner's `data/`) holding one transaction and one proposal made through `propose_category`, tick it, press Accept chosen, and see the notice and the category on the transaction's page.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. Commit after each id | `test_all_or_none` | all three open | proposal 1 accepted |
| 2. Read the ids with `str.isdigit` alone | `test_nothing_chosen_or_a_bad_form[accept-ids3]` (`١`) | 400, all open | proposal 1 accepted |
| 3. Skip `refused` on the post | `test_the_form_token_is_checked` | 403 | a decision |

## 6. Out of scope

Each must be absent: a migration; a dashboard block; a change to the MCP tools or `fin review`; transfer or rule proposals.
