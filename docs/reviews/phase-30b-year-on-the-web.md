# Review: Phase 30b

- Verdict: PASS
- Passed: 3802
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write")

## Gates

- `scripts/check.py`: `3802 passed`, `All checks passed.` (N + 14 = 3796; extra 6 from `test_web_year_more.py`)
- Given tests: `14 passed`
- Coverage of `views.yearend`, `web.routes.reports`, `web.routes.categories`: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: only `tests/unit/test_web_split.py`
- Given `year.html`, the `reports.html` and `categories.html` diffs, and `test_web_year.py` match the spec blocks
- `git status --short` lists `docs/progress.md`, the source files and templates of the spec's Scope (one of them new), `tests/unit/test_web_split.py`, and two new test files

## Requirement checklist

- R1: `test_the_year_page`; `test_year_needs_a_migrated_database`
- R2: `test_the_year_page`; `test_the_first_and_last_years`; `test_this_year_by_default`
- R3: `test_this_year_by_default`; `test_a_year_that_is_refused`
- R4: `test_a_line_drills_down_to_its_transactions`
- R5: `test_reports_links_to_the_year`
- R6: `test_the_tax_card`
- R7: `test_marking_on_the_page`; `test_marking_refused`; `NOTICES` has `Marked tax-relevant.` and `No longer tax-relevant.`
- R8: `test_get_on_the_tax_path_is_405`
- R9: gate 4 (only `tests/unit/test_web_split.py`)

## Tests to write

- GET on `/categories/tax` is 405; `/year` not migrated: `test_get_on_the_tax_path_is_405`; `test_year_needs_a_migrated_database`
- a year with every tax flag turned off shows `No tax-relevant categories.`: `test_a_year_with_no_tax_relevant_categories`
- a refused tax form keeps the Categories page whole: `test_a_refused_tax_form_keeps_the_page`
- marking a category already tax-relevant redirects with `tax-set` and records nothing: `test_marking_an_already_tax_relevant_category_records_nothing`
- a form without a valid form token: `test_a_form_without_a_valid_token_is_refused`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy (not git checkout), with `__pycache__` cleared.

1. `GET /year` `str.isdigit` without an ASCII check: `test_a_year_that_is_refused[２０２６]` failed (200 instead of 400)
2. `GET /year` `date.today()` for a blank year: `test_this_year_by_default` failed (`Year 2026` instead of `Year 2024`)
3. `year_page` a previous year of 0: `test_the_first_and_last_years[1-2]` failed (`0 · 2` instead of `2`) when previous was the truthy `"0"`; integer `0` is hidden by the given template's `{% if report.previous %}`
4. `POST /categories/tax` anything but `off` read as on: `test_marking_refused` (`maybe`) failed (303 instead of 400)
5. `_categories_page` `tax_categories` in id order: `test_the_tax_card` failed (Medical first instead of Gifts & Donations)
6. `POST /categories/tax` the `tax-set` notice for both: `test_marking_on_the_page` failed (`tax-set` after off instead of `tax-cleared`)

## Probe

On a temporary `FIN_DATA_DIR` (never the owner's `data/`): one -$45.00 ACME CLINIC purchase on a card, set to Medical by hand; `fin web serve --port 18768`. Reports showed `The year's totals` and no Year item in the menu. The Year page for 2026 listed Medical in By category and Tax-relevant. Following that line listed the 2026-03-15 purchase. Marking Groceries on Categories put Groceries in the Year page's Tax-relevant table.

## Out of scope

Absent: a Year link in the menu; a chart of the year; comparing years; a Tax column in the Categories table; any change to 30a's report or commands.

## Progress log

`docs/progress.md` has the Phase 30b entry in the required form. Deviations: None.
