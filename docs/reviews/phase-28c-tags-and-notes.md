# Review: Phase 28c

- Verdict: PASS
- Passed: 3574
- Findings: 0
- Approved deviations: extra `test_untagging_several_transactions` for the two-id untag line; ruff format folded the given migration's UniqueConstraint onto one line (same name and columns)
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write", plus the two-id untag line the given CLI tests leave uncovered)

## Gates

- `scripts/check.py`: `3574 passed`, `All checks passed.` (N + 14 = 3564; extra 10 from extra tests and the HOMES area pin)
- Given tests: `14 passed`
- Coverage of domain.tags, domain.audit, db.repositories, and cli.tags: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: the three files of the given diff
- `git grep -n "TransactionTagRow\\|TransactionNoteRow" -- src/finances/cli src/finances/web src/finances/analysis`: no output
- Given tests match the spec blocks; the migration UniqueConstraint is one line after ruff format

## Requirement checklist

- R1: `test_0018_follows_0017`; `test_the_tables_and_their_row_classes`; `test_down_and_up_again`
- R2: `test_tagging`; `test_refused`; `test_a_tag_at_the_limit_is_kept`; `test_a_note_at_the_limit_is_kept`
- R3: `test_the_lists`; `test_an_unknown_action`
- R4: `test_refused` (id 9 then a blank tag); `test_add_tags_counts_distinct_ids_and_skips_a_tag_already_there`; `test_remove_tags_of_a_tag_the_transaction_lacks`; `test_add_tags_is_all_or_none`
- R5: `test_a_note`; `test_set_note_records_only_a_change`
- R6: `test_tagging`; `test_untagging`; `test_tags_for_leaves_out_a_transaction_with_none`
- R7: `test_deleting_a_feed_transaction_takes_tags_and_a_note`; `delete_feed_transaction` deletes tags and the note before the transaction
- R8: `test_tagging`; `test_untagging`; `test_untagging_several_transactions`
- R9: `test_a_note`; `test_no_tags`; `cli/tags.py` has no length or case rule
- R10: `git diff --stat HEAD -- tests` lists the three given-diff files

## Tests to write

- `normalize_tag` at 30 kept and 31 refused; `clean_note` at 500 kept and `"   "` is `""`: `test_a_tag_at_the_limit_is_kept`; `test_a_note_at_the_limit_is_kept`
- `add_tags([1, 1])` counts 1; a second tag adds no row; audit of added and removed: `test_add_tags_counts_distinct_ids_and_skips_a_tag_already_there`
- `remove_tags` of a missing tag: `test_remove_tags_of_a_tag_the_transaction_lacks`
- `add_tags([1, 9], "trip")` all or none: `test_add_tags_is_all_or_none`
- `set_note` five recording cases: `test_set_note_records_only_a_change`
- `tags_for` omits a transaction with none, tags in order; `list_tags` counts once: `test_tags_for_leaves_out_a_transaction_with_none`
- feed deletion takes tags and a note: `test_deleting_a_feed_transaction_takes_tags_and_a_note`

## Probe

None. Look through the terminal on a temporary `FIN_DATA_DIR` (never the owner's `data/`): three card purchases; `fin transactions tag` on 1 and 2 as `tax`; `fin transactions note` on 3; `fin audit` showed two `tag_added` rows and one `note_set`. `FAILURES 0`.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. Normalize the tag before checking the ids: `test_refused[args2-transaction not found]` fails (`a tag must be 1 to 30 characters`).
2. No lower case: `test_tagging` fails (`Work Trip`).
3. Strip without making runs one space: `test_tagging` fails (`work   trip`).
4. Record a change for a transaction that had the tag: `test_add_tags_counts_distinct_ids_and_skips_a_tag_already_there` fails (two `tag_added`).
5. Refuse a tag the transaction lacks: `test_remove_tags_of_a_tag_the_transaction_lacks` fails (`ValueError`).
6. Store an empty text: `test_a_note` fails (`""` after removing).
7. Cut to 500 instead of refusing: `test_refused[args4-a note is at most 500 characters]` fails (saved).
8. Leave the tags: `test_deleting_a_feed_transaction_takes_tags_and_a_note` fails (`IntegrityError`).
9. Record a change for the same text: `test_set_note_records_only_a_change` fails (two `note_set` after the same text).
10. By count, not by tag: `test_tagging` fails (`work trip` first).

## Out of scope

Absent: anything on the web; a tag filter or a Tags column in `fin transactions list`; tags or notes in an MCP tool or report; renaming or merging tags; more than one note per transaction.
