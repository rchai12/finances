# Verify Phase 28g: splits on the web

Spec: `docs/phases/phase-28g-splits-on-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder put 28e's splits on a transaction's page (a Parts card or a Split card, two form routes, two notices), added `parse_parts` to the critical `domain/splits.py`, and gave search and its rows each part's position so the Transactions page marks parts. A template diff, a diff to one earlier test, and two test files were given.

These are correct and must not be reported: the two routes sharing a private helper with 28f's; `part_lines` given the category names from `list_categories` or `category_tree`; `search_transactions` numbering parts by counting or from `SplitPart.position`, as long as a part's number is its position.

## 1. Gates

N is `3657` when Phase 28f was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.` (its critical coverage step includes `domain/splits.py`); at least N + 13 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_split_lines.py tests/integration/test_web_splits.py --no-cov` | exactly `13 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.splits --cov=finances.analysis.search --cov=finances.views.transactions --cov=finances.web.routes.transactions --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | only `tests/unit/test_web_split.py` |

This search must print nothing:

- `git grep -n "splitlines\|parse_part(" -- src/finances/web`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files and the two templates of the spec's Scope, `tests/unit/test_web_split.py`, and three new test files. The templates and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_a_split_transactions_page`, `test_a_page_that_is_not_split`); the coder's 400-page case | pass; the parts table on the 400 page |
| R2 | gate 2 (`test_splitting_on_the_page`, `test_a_refused_split_keeps_what_was_typed`); the coder's pending and zero cases | pass |
| R3 | gate 2 (`test_removing_the_split`, `test_a_refused_form`); the coder's rule case | pass; the rule's category back |
| R4 | the coder's 405 cases | two 405s |
| R5 | gate 2; read `NOTICES` | both texts as the spec gives them |
| R6 | gate 2 (`test_split_lines.py`); gate 1's critical coverage step | pass |
| R7 | gate 2 (`test_parts_on_the_transactions_page`); the coder's search case | pass |
| R8 | gate 4 | only that file |

## 4. Probe

None. Look once in a browser: `fin web` on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with one purchase of $20.00, split it on its page into `12.00 Groceries` and `8.00 Dining`, see the Parts card and no Set the category card, then the Transactions page with two rows marked `part 1` and `part 2`, then remove the split.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `parse_parts`: blank lines not skipped | given `"\n  12.00 Groceries  \r\n\n 8 Dining\n"` | two parts | the size-and-category message |
| 2. `search_transactions`: parts numbered from 0 | given `test_parts_on_the_transactions_page` | `Dining part 1` | `Dining` (0 shows no badge) |
| 3. `found_rows`: the part left out | given `test_parts_on_the_transactions_page` | `Groceries part 2` | an unpack error |
| 4. `_transaction_page`: `parts` left empty | given `test_a_split_transactions_page` | the parts table, no category form | the category form, no table |
| 5. the split route: the 400 page without the typed text | given `test_a_refused_split_keeps_what_was_typed` | the text in the box | an empty box |
| 6. the clear route: no categorize run | coder: a split whose merchant a rule matches, removed | the rule's category | none |

## 6. Out of scope

Each must be absent: editing one part in place; a category select per part; splits in the bulk form or an MCP tool; a change to the detail table at the top of a transaction's page; a part badge anywhere but the Transactions page.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
