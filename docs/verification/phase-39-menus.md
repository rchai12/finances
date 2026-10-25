# Verify Phase 39: menus in the navigation bar

Spec: `docs/phases/phase-39-menus.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder grouped the navigation bar's links into four click-to-open menus (Money, Plan, Organize, System) beside Home and Review, and gave Review a count of waiting proposals. A template and style diff, a diff to one earlier test, and one test file were given.

These are correct and must not be reported: the count's session opened through the web's existing session helper or a session of its own, as long as it commits nothing; the schema check written as a small private helper.

## 1. Gates

N is the number passed in Phase 38's progress entry.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 14 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_menus.py --no-cov` | exactly `14 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web.render --cov=finances.db.repositories.proposals --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | only `tests/unit/test_repositories_split.py` |
| `git grep -n "<script" -- src/finances/web/templates/layout.html` | no output |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files, template, and stylesheet of the spec's Scope, `tests/unit/test_repositories_split.py`, and two new test files. The given test file, the template and style diff, and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_the_menus_and_the_top_links_in_order`, `test_the_menu_holding_the_page_is_marked`); the coder's sixteen-links case | pass |
| R2 | gate 1 (`test_repositories_split.py`); the coder's accepted-and-open case | pass |
| R3 | gate 2 (`test_review_shows_how_many_proposals_wait`, `test_no_count_when_nothing_waits`, `test_no_count_on_the_login_page`, `test_a_page_shown_before_the_database_is_migrated_has_no_count`); the coder's error-page case | pass |
| R4 | gate 4 | only that file |

## 4. Probe

None. Look once in a real browser on a temporary `FIN_DATA_DIR`: open Money, then Plan (Money closes), follow Budgets, and see Plan marked; narrow the window to a phone's width and open System.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `count_open_proposals`: every status counted | given `test_review_shows_how_many_proposals_wait` (two open, one declined) | `2` | `3` |
| 2. `_render`: `review_count` given to the review page only | the same test (`/`, `/accounts`) | `2` on each | none |
| 3. `_render`: the login page counted | given `test_no_count_on_the_login_page` (two open) | no count | `2` |
| 4. `_render`: no schema check | given `test_a_page_shown_before_the_database_is_migrated_has_no_count` (`/backups`, not migrated) | 200, no count | 500 |

## 6. Out of scope

Each must be absent: JavaScript in any template; hover-only menus; a change to a page's own content or to a link's label; a count beside anything but Review.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
