# Review: Phase 30d

- Verdict: PASS
- Passed: 3847
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write")

## Gates

- `scripts/check.py`: `3847 passed`, `All checks passed.` (N + 10 = 3838; extra 8 from `test_web_export_more.py` and 1 from `test_web_split.py`'s new area)
- Given tests plus 30c's CLI export file: `18 passed` (10 in `test_web_export.py`, 8 in `test_cli_export.py`)
- Coverage of `analysis.export`, `web.routes.export`: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: only `tests/unit/test_web_split.py`
- `git grep -n "write_csv\|write_text\|open(" -- src/finances/web/routes/export.py` prints nothing
- Given templates, `test_web_split.py` diff, and `test_web_export.py` match the spec blocks
- `git status --short` lists `docs/progress.md`, the source files and templates of the spec's Scope (one of them new), `tests/unit/test_web_split.py`, and two new test files

## Requirement checklist

- R1: 30c's `test_transactions`; `test_fin_export_transactions_writes_the_same_bytes`; `transactions_for_export` returns `export_lines`
- R2: `test_transactions_by_dates`; `test_transactions_as_the_filters_choose`; `test_a_download_that_is_refused`
- R3: `test_the_year`; `test_a_download_that_is_refused`; `test_a_blank_year_exports_today`
- R4: `test_spending`; `test_a_download_that_is_refused`; `test_spending_with_no_options_exports_this_month`
- R5: `test_each_page_links_to_its_download`
- R6: `test_a_download_writes_nothing`; grep gate
- R7: gate 4 (only `tests/unit/test_web_split.py`)

## Tests to write

- `/export/year` with no year, `_today` replaced after the app is created: `test_a_blank_year_exports_today` (`date(2024, 8, 1)`)
- `/export/spending` with no options: `test_spending_with_no_options_exports_this_month`
- `?tag=work`; named date range; `?from=2026-05-02` alone: `test_transactions_by_tag_and_a_named_date_range`
- `?limit=x`: `test_a_bad_limit_is_refused_as_the_page_refuses_it`
- not migrated: `test_downloads_need_a_migrated_database`
- `fin export transactions` same bytes as 30c: `test_fin_export_transactions_writes_the_same_bytes`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy (not git checkout), with `__pycache__` cleared.

1. `GET /export/transactions` the filters left out: `test_transactions_as_the_filters_choose` failed (every transaction and part instead of one Groceries row)
2. `export_lines` the query's limit used: `test_transactions_as_the_filters_choose` failed (`limit=1` gave one row instead of five)
3. the downloads no `Content-Disposition`: `test_the_year` failed (header absent)
4. `GET /export/transactions` dates in the name when only one is given: `test_transactions_by_tag_and_a_named_date_range` failed (`?from=2026-05-02` named with an empty date)
5. `GET /export/year` `date.today()` for a blank year: `test_a_blank_year_exports_today` failed (the machine's year instead of 2024)
6. `GET /export/transactions` an unknown account exported as no rows: `test_a_download_that_is_refused` (`account=Nope`) failed (200 instead of 400)

## Probe

On a temporary `FIN_DATA_DIR` (never the owner's `data/`): ACME COFFEE and a FOOBAR GROCERY split; `fin web serve --port 18769`. The Transactions page filtered to Groceries showed that split part and `Download these as CSV`. The download was `transactions.csv` with only the Groceries row. No `data/exports` folder was created.

## Out of scope

Absent: a file written to the export folder from the web; other reports; a choice of columns or format; filters on `fin export transactions`; any change to the CSVs.

## Progress log

`docs/progress.md` has the Phase 30d entry in the required form. Deviations: None.
