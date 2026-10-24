# Verify Phase 30b: the year and the tax flag on the web

Spec: `docs/phases/phase-30b-year-on-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added the Year page (a route on the reports router, `year_page` in the views, a link from Reports) and the Tax-relevant card on Categories (a context value and one form route with two notices). A template diff (one new template), a diff to one earlier test, and one test file were given.

These are correct and must not be reported: the year read with `_WHOLE` or an equal ASCII-only check; `tax_categories` built from `list_categories` filtered and sorted in the route or by a small helper; the tax route sharing the aliases routes' error handling.

## 1. Gates

N is `3782` when Phase 30a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 14 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_year.py --no-cov` | exactly `14 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.views.yearend --cov=finances.web.routes.reports --cov=finances.web.routes.categories --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | only `tests/unit/test_web_split.py` |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files and templates of the spec's Scope (one of them new), `tests/unit/test_web_split.py`, and two new test files. The templates and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_the_year_page`); the coder's not-migrated case | pass |
| R2 | gate 2 (`test_the_year_page`, `test_the_first_and_last_years`, `test_this_year_by_default`) | pass |
| R3 | gate 2 (`test_this_year_by_default`, `test_a_year_that_is_refused`) | pass |
| R4 | gate 2 (`test_a_line_drills_down_to_its_transactions`) | passes |
| R5 | gate 2 (`test_reports_links_to_the_year`) | passes |
| R6 | gate 2 (`test_the_tax_card`) | passes |
| R7 | gate 2 (`test_marking_on_the_page`, `test_marking_refused`); read `NOTICES` | pass; both texts as the spec gives them |
| R8 | the coder's 405 case | 405 |
| R9 | gate 4 | only that file |

## 4. Probe

None. Look once in a browser: `fin web` on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with a few purchases this year, open Reports, follow the year's link, follow a category's line to its transactions, then mark a category on Categories and see it in the Year page's Tax-relevant table.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `GET /year`: `str.isdigit` without an ASCII check | given `test_a_year_that_is_refused` (`２０２６`) | 400 | 200, the year 2026 |
| 2. `GET /year`: `date.today()` for a blank year | given `test_this_year_by_default` (today replaced by 2024) | `Year 2024` | `Year 2026` |
| 3. `year_page`: a previous year of 0 | given `test_the_first_and_last_years` (`1`) | `2` | `0 · 2` |
| 4. `POST /categories/tax`: anything but `off` read as on | given `test_marking_refused` (`maybe`) | 400 | 303 |
| 5. `_categories_page`: `tax_categories` in id order | given `test_the_tax_card` | Gifts & Donations, Medical, Taxes | Medical first |
| 6. `POST /categories/tax`: the `tax-set` notice for both | given `test_marking_on_the_page` | `tax-cleared` after off | `tax-set` |

## 6. Out of scope

Each must be absent: a Year link in the menu; a chart of the year; comparing years; a Tax column in the Categories table; any change to 30a's report or commands.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
