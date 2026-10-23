# Verify Phase 28c: tags and notes

Spec: `docs/phases/phase-28c-tags-and-notes.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added tags and notes: a migration with two tables, pure rules for a tag and a note, six repository functions that record each change, feed deletions that take tags and notes along, and four `fin transactions` commands. A migration, a diff to three earlier tests, and two test files were given.

These are correct and must not be reported: reusing `_distinct_transaction_ids` and `_require_transaction` from `assignments.py`; the tag rows found per transaction or in one query; `list_tags` counting in SQL or in Python; where in `delete_feed_transaction` the two deletes happen, as long as both come before the transaction's.

## 1. Gates

N is `3550` when Phase 19e was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 14 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_migration_0018.py tests/e2e/test_cli_tags.py --no-cov` | exactly `14 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.tags --cov=finances.domain.audit --cov=finances.db.repositories --cov=finances.cli.tags --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | the three files of the given diff |

This search must print nothing:

- `git grep -n "TransactionTagRow\|TransactionNoteRow" -- src/finances/cli src/finances/web src/finances/analysis`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope (three of them new), the three earlier test files, the new migration, and four new test files. The migration and the diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_migration_0018.py`); gate 1 (`tests/integration/test_migration_chain.py`) | pass |
| R2 | gate 2 (`test_tagging`, `test_refused`); the coder's unit tests | both messages; the 30 and 500 edges |
| R3 | gate 1 (`test_audit_rules.py`, `test_cli_audit.py`) | pass |
| R4 | gate 2 (`test_refused` with id 9 and a blank tag); the coder's tests | ids checked before the tag; audit rows only for a change |
| R5 | gate 2 (`test_a_note`); the coder's note cases | each of the five note cases records what the spec says |
| R6 | gate 2 (`test_tagging`, `test_untagging`); the coder's `tags_for` case | pass |
| R7 | the coder's feed deletion case; read `delete_feed_transaction` | both deletes come before the transaction's |
| R8 | gate 2 | pass |
| R9 | gate 2 (`test_a_note`, `test_no_tags`); read `cli/tags.py` | no length or case rule in the CLI |
| R10 | gate 4 | only the three files |

## 4. Probe

None. Look once in the terminal: on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with a few purchases, tag two, note one, then run `fin audit` and see a `tag_added` row per transaction and one `note_set`.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `add_tags`: normalize the tag before checking the ids | given `test_refused` (id 9, blank tag) | `transaction not found` | `a tag must be 1 to 30 characters` |
| 2. `normalize_tag`: no lower case | given `test_tagging` (`  Work   Trip `) | `work trip` | `Work Trip` |
| 3. `normalize_tag`: strip without making runs one space | given `test_tagging` | `work trip` | `work   trip` |
| 4. `add_tags`: record a change for a transaction that had the tag | coder: tagging the same transaction twice | one `tag_added` | two |
| 5. `remove_tags`: refuse a tag the transaction lacks | coder: untagging a tag it does not have | nothing, no error | `ValueError` |
| 6. `set_note`: store an empty text | given `test_a_note` | `None` after removing | `""` |
| 7. `clean_note`: cut to 500 instead of refusing | given `test_refused` (501 characters) | refused | saved |
| 8. `delete_feed_transaction`: leave the tags | coder: a feed transaction with a tag, deleted | no error, tags gone | `IntegrityError` |
| 9. `set_note`: record a change for the same text | coder: the same note saved twice | one `note_set` | two |
| 10. `list_tags`: by count, not by tag | given `test_tagging` (`tax` 1, `work trip` 2) | `tax` first | `work trip` first |

## 6. Out of scope

Each must be absent: anything on the web; a tag filter or a Tags column in `fin transactions list`; tags or notes in an MCP tool or report; renaming or merging tags; more than one note per transaction.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
