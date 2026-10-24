# Verify Phase 28f: tags and notes on the web

Spec: `docs/phases/phase-28f-tags-and-notes-on-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder put 28c's tags and notes on a transaction's page (two cards, three form routes, four notices) and added a Tag filter to the Transactions page through a new `TransactionQuery.tag` and a repository function, `tagged_with`. A template diff, a diff to two earlier tests, and one test file were given.

These are correct and must not be reported: the three routes sharing a private helper; `search_transactions` calling `tagged_with` once per search or skipping it when no tag is given; `tag_choices` built from `list_tags` in the route or by a small private function.

## 1. Gates

N is `3640` when Phase 28e was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 9 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_tags_and_notes.py --no-cov` | exactly `9 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.db.repositories --cov=finances.analysis.search --cov=finances.web.routes.transactions --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | the two files of the given diff |

This search must print nothing:

- `git grep -n "TransactionTagRow\|TransactionNoteRow" -- src/finances/web src/finances/analysis src/finances/views`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files and the two templates of the spec's Scope, the two earlier test files, and two new test files. The templates and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_a_transaction_with_tags_and_a_note`); the coder's 400-page case | passes; tags and note on the 400 page |
| R2 | gate 2 (`test_adding_and_removing_a_tag`, `test_a_refused_form`) | pass |
| R3 | gate 2 (`test_saving_and_removing_the_note`) | passes |
| R4 | the coder's 405 cases | three 405s |
| R5 | gate 2; read `NOTICES` | the four texts as the spec gives them |
| R6 | gate 2 (`test_the_tag_filter`); the coder's select-all case | pass |
| R7 | the coder's `tagged_with` cases; read `tagged_with` | one query over `transaction_tags` |
| R8 | gate 2 (`test_the_tag_filter`, `test_a_tag_filter_that_is_refused`); the coder's search cases | pass |
| R9 | gate 4 | only the two files |

## 4. Probe

None. Look once in a browser: `fin web` on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with a few purchases, add a tag and a note on one transaction's page, follow the tag's link, and see the Transactions page filtered by it with the Tag choice selected.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `search_transactions`: compare the tag as typed | given `test_the_tag_filter` (`tag=TRIP`) | two rows | none |
| 2. `search_transactions`: ignore the tag | given `test_the_tag_filter` | `FOOBAR GROCERY`, `ACME COFFEE` | all three |
| 3. `search_transactions`: a refused tag treated as no tag | given `test_a_tag_filter_that_is_refused` | 400 | 200 |
| 4. `_SEARCH_FIELDS`: `tag` not a filter field | given `test_the_tag_filter` (the bulk form's `back`) | `tag=TRIP` | `""` |
| 5. the note route: always `note-saved` | given `test_saving_and_removing_the_note` | `note-removed` | `note-saved` |
| 6. the remove route: calls `add_tags` | given `test_adding_and_removing_a_tag` | `tax` left | `tax`, `trip` |
| 7. `_transaction_page`: `tags` only on a 200 | coder: a refused tag | tags on the 400 page | `No tags.` |

## 6. Out of scope

Each must be absent: a Tags or Note column on the Transactions page; tags or notes in an MCP tool, `fin transactions list`, or a report; tagging from the bulk form; renaming or merging tags.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
