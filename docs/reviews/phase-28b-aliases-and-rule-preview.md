# Review: Phase 28b

- Verdict: PASS
- Passed: 3534
- Findings: 0
- Approved deviations: `tests/unit/test_web_split.py` ROUTES and the fixed-path order check gained the three new posts (the given diff omitted this pin)
- For the architect: include `tests/unit/test_web_split.py` in the given diff whenever a web route is added

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra CSRF posts in `test_rule_preview.py` cover the new routes' refused branches for the 100% coverage gate)

## Gates

- `scripts/check.py`: `3534 passed`, `All checks passed.` (N + 12 = 3519; extra from the coder's tests)
- Given tests: `12 passed`
- Coverage of db.repositories, categorize.service, views.categories, cli.categories, web.routes.categories: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: `tests/unit/test_repositories_split.py` and `tests/unit/test_web_split.py` (approved deviation)
- `git grep -n "pick_rule\|merchant_names\|rule_matches" -- src/finances/web src/finances/cli src/finances/views`: no output
- Given templates and given tests match the spec blocks; HOMES given diff applied

## Requirement checklist

- R1: `test_no_aliases_yet`; template diff equals the spec
- R2: `test_merging_on_the_page`; `test_a_refused_alias`
- R3: `test_unmerging_on_the_page`; NOTICES `merchant-merged` and `merchant-unmerged` as specified
- R4: `test_check_rule_returns_the_normalized_pair`; `test_check_rule_refuses`; `test_check_rule_refuses_an_existing_rule`; `create_rule` calls `check_rule` and makes no check of its own
- R5: `test_a_hand_set_transaction_the_rule_matches_is_not_counted`; `test_a_winning_rule_that_changes_nothing_is_not_counted`; `test_an_older_rule_wins_a_tie_and_a_higher_priority_wins`; `test_an_alias_lets_equals_see_the_merged_name`; `test_same_day_examples_come_newest_id_first`; `test_a_preview_writes_nothing_and_matches_categorize`
- R6: `test_a_preview_shows_the_ten_newest`; `test_one_transaction`; `test_no_transactions`
- R7: those CLI tests; the command calls `require_current_schema()` and prints `preview_text`, `preview_lines`, `preview_more`
- R8: `test_previewing_a_rule`; `test_a_refused_preview`; `test_both_rule_forms_offer_a_preview`; `test_a_preview_with_a_bad_priority_is_refused`
- R9: given HOMES diff applied; `test_web_split.py` listed as an approved deviation
- Tests to write: `tests/integration/test_rule_preview.py`

## Probe

None. Look once in a browser: `fin web` on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with ACME CAFE, ACME COFFEE, and FOOBAR GROCERY. Preview of `acme` -> Dining showed "This rule would put 2 transactions in Dining." with the table, while Rules still said "No rules." Add rule from the same filled form showed "Rule added, and the rules were run again." on `/categories`. `FAILURES 0`.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. Count categories set by hand: `test_a_hand_set_transaction_the_rule_matches_is_not_counted` fails (changes 1).
2. Count every transaction the new rule wins: `test_a_winning_rule_that_changes_nothing_is_not_counted` fails (changes 1).
3. Give the new rule id 0: `test_an_older_rule_wins_a_tie_and_a_higher_priority_wins` fails (tied.changes 1).
4. Match `clean_merchant` only: `test_an_alias_lets_equals_see_the_merged_name` fails (changes 0).
5. Oldest first: `test_a_preview_shows_the_ten_newest` fails (ids 1 to 10).
6. `preview_more` always None: `test_a_preview_shows_the_ten_newest` fails (`Showing the 10 newest.` absent).
7. No singular: `test_one_transaction` fails (`1 transactions`).
8. The name as typed: `test_no_transactions` fails (`dining`).
9. Alias add route, no categorize: `test_merging_on_the_page` fails (1 without a category).
10. Alias delete route, no categorize: `test_unmerging_on_the_page` fails (`{1, 2, 3}`).
11. Preview route calls `create_rule`: `test_previewing_a_rule` fails (two rules).

## Out of scope

Absent: a preview on the rule edit page or for an edit or a delete; a preview of an alias; a change to `fin aliases`, 28a's alias rules, or the uncategorized lists; a page other than Categories after a preview.
