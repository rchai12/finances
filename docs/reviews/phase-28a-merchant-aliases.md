# Review: Phase 28a

- Verdict: PASS
- Passed: 3507
- Findings: 0
- Approved deviations: `tests/e2e/test_cli_audit.py` UNKNOWN extended with the new actions (the given diff omitted this 19a pin of ACTIONS); extra `test_refund_facts_when_the_refund_uses_the_source_name`
- For the architect: include the `fin audit` UNKNOWN string in a given diff whenever ACTIONS grows

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra refund case is the spec's "Tests to write" plus the source-name direction so spot 7 has a deciding input)

## Gates

- `scripts/check.py`: `3507 passed`, `All checks passed.` (N + 10 = 3492; extra from extra tests and one new HOMES parametrize)
- Given tests: `10 passed`
- Coverage of domain.merchants, domain.rules, domain.audit, db.repositories, analysis.spending, analysis.refunds, categorize.service, views.categories, cli.aliases: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: the two given-diff files plus `tests/e2e/test_cli_audit.py` (approved deviation)
- `git grep -n "clean_merchant(" -- src/finances/analysis/spending.py src/finances/analysis/refunds.py src/finances/categorize src/finances/db`: no output
- `git grep -n "pick_rule(" -- src/finances/categorize`: no output
- Given migration and tests match the spec blocks; the two-file diff applied, plus the UNKNOWN pin

## Requirement checklist

- R1: `test_0016_follows_0015`; `test_the_table_and_its_row_class`; `MERCHANT_NAME_LIMIT = 100`
- R2: `test_refused`; `test_check_alias_refuses_a_long_target`; `test_check_alias_returns_the_normalized_pair`; `test_normalize_merchant`; `test_merchant_name_and_names`
- R3: `test_pick_rule_for_takes_the_highest_priority_across_names`; `test_pick_rule_for_takes_the_oldest_at_equal_priority`; `test_pick_rule_for_when_none_match`
- R4: `test_the_lists`
- R5: `test_add_list_delete_and_audit`; `test_a_refused_alias_stores_nothing`; `aliases.py` has no categorize import
- R6: `test_load_flows_uses_the_merged_name`; `test_refund_facts_across_an_alias`; `alias_map(session)` once in `flows_for`
- R7: `test_merging_a_merchant`; `test_an_alias_does_not_take_a_category_away`; `test_propose_rule_matches_either_name`
- R8: `test_merging_a_merchant`; `test_removing_it`; `test_refused`; each command calls `require_current_schema()`; no R2 message in `cli/aliases.py`
- R9: given diff applied; UNKNOWN pin listed as an approved deviation
- Tests to write: `tests/unit/test_merchant_aliases.py` and `tests/integration/test_merchant_aliases.py`

## Probe

None. Look through `fin recurring` on a temporary `FIN_DATA_DIR` (never the owner's `data/`): ACME CAFE in January, February, and March and ACME COFFEE in April and May, one a month on the 5th for $4.50. Before the alias, a cafe series; after `fin aliases add --from "ACME CAFE" --to "ACME COFFEE"`, one series named ACME COFFEE. `FAILURES 0`.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. Match the merged name only: `test_an_alias_does_not_take_a_category_away` fails (empty assignments).
2. Match the cleaned name only: `test_merging_a_merchant` fails (`0 changed, 1 without a category`).
3. The first name with any match wins: `test_pick_rule_for_takes_the_highest_priority_across_names` fails (id 1).
4. The already-merged check before the same-name check: `test_refused[args1-a merchant cannot be merged into itself]` fails (`this merchant is already merged into another`).
5. No check that the target is merged: `test_refused[args3-the merchant to merge into is itself merged into another]` fails (exit 0, a chain stored).
6. Keep `clean_merchant` in `flows_for`: `test_load_flows_uses_the_merged_name` fails (`ACME CAFE`).
7. Keep `clean_merchant` in `refund_facts`: `test_refund_facts_when_the_refund_uses_the_source_name` fails (purchase None).
8. No categorize run after delete: `test_removing_it` fails (one line).
9. Match the cleaned name only in `propose_rule`: `test_propose_rule_matches_either_name` fails (`the rule does not match the example transaction`).
10. Store the names as typed: `test_merging_a_merchant` fails (`Merged "  acme   cafe "`).

## Out of scope

Absent: an aliases page or form; the rule preview; an MCP alias tool; the uncategorized lists showing the merged name (`clean_merchant` remains in `views/categories.py` and `list_uncategorized`); an edit command; chains or their repair.
