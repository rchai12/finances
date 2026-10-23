# Review: Phase 34a

- Verdict: PASS
- Passed: 3323
- Findings: 0
- Approved deviations: `feed.py` imports `remove_category` from `assignments` after the move; extra tests cover `owner_set` from Joint and `change_rows` with no `record_id`
- For the architect: Scope did not list `feed.py`; a stored rule cannot produce `rule_text` longer than 200 characters

## Findings

None

Parts that needed a repair: `set_account_owner` looked up the new owner's name before flush, which broke `test_an_unknown_account_or_person_is_refused`; after is now read after flush.

Built beyond the spec: the two extra tests named above.

## Gates

- `scripts/check.py`: `3323 passed`, `All checks passed.` (N + 15 = 3313; extra 10 from extra tests and two new split-area parametrize cases)
- Given tests: `15 passed`
- Split, migration chain, migrations, and text: `59 passed`
- Coverage of domain.audit, db.repositories, views.audit, and cli.audit: `Required test coverage of 100% reached`
- `git grep` of domain importing outside itself: no output
- `git grep` of `record_change|AuditRow` in cli and web: no output
- `git diff --stat HEAD -- tests`: only `tests/unit/test_repositories_split.py`
- Given files match the spec blocks

## Requirement checklist

- R1: `test_0012_follows_0011`; `test_the_table_and_its_row_class`; `test_down_and_up_again`; `test_the_lists`
- R2: `test_the_lists`; `test_the_texts`
- R3: `test_record_change_checks_and_fits`; `test_list_changes_newest_first_and_filters`
- R4: `test_the_package_holds_one_module_per_area`; `test_the_facade_offers_every_name_and_only_those`
- R5: `test_each_change_a_person_makes`; `test_owner_set_from_joint_records_joint_as_before`
- R6: `test_each_change_a_person_makes`; `test_deleting_a_group_records_category_deleted`; `test_edit_rule_that_changes_nothing_records_nothing`
- R7: `test_each_change_a_person_makes`; `test_set_and_clear_by_hand_record_one_row_per_transaction`; `test_rules_and_automatic_pairing_record_nothing`
- R8: `test_each_change_a_person_makes`; `test_a_refused_change_records_nothing`
- R9: `test_each_change_a_person_makes`; `test_rules_and_automatic_pairing_record_nothing`
- R10: `test_every_change_newest_first`; `test_one_action_and_a_limit`; `test_nothing_since_a_later_day`; `test_an_unknown_action`
- R11: `test_the_facade_offers_every_name_and_only_those`
- R7, R10 edges: `tests/integration/test_audit_more.py`

## Probe

None. The spot checks.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. Record `category_set` in `_assign`: `test_rules_and_automatic_pairing_record_nothing` fails (`assert 4 == 3`).
2. Record every new pair, automatic ones too: the same test fails (`transfer_confirmed`).
3. Record a rename to the same name: `test_nothing_is_recorded_when_nothing_changes` fails (`assert 7 == 6`).
4. Record before the budget's checks: `test_a_refused_change_records_nothing` fails (`budget_set` first).
5. `record_change` stamps with `datetime.now` directly: `test_record_change_checks_and_fits` fails (`at` is the real time, not `NOON`).
6. `list_changes` oldest first: `test_list_changes_newest_first_and_filters` fails (`Test A` first).

## Out of scope

Absent: a statement, backup, or sync event; a History page; an `agent` who; a way to edit or delete rows; a write from `cli` or `web` to the trail.
