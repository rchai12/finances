# Review: Phase 41a

- Verdict: PASS
- Passed: 4092
- Findings: 0
- Approved deviations: extra test `test_a_form_without_the_token_is_refused` so `POST /categories/groups/add`'s `refused` branch is covered
- For the architect: None

## Findings

None

Parts that needed a repair: the new route's `if stopped is not None` line was missed until the extra csrf test.

Built beyond the spec: extra tests for audit `category_added`, stripped `"  Pets  "`, case `food` vs Food, `category_lines` of an empty transfer group, deleting an empty group, web `kind=transfer` with `sensitive=on`, and a form without the token.

## Gates

- `scripts/check.py --first core,web,cli`: last line `All checks passed.`; summary lists `tests (core,web,cli): passed` then `tests: passed`; 4091 passed in that run (before the csrf extra), 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table. Collect-only after the csrf extra: 4092.
- Given tests: `16 passed`
- Coverage include report: `TOTAL 712 0 164 0 100%`
- `git diff --stat HEAD -- tests`: only `tests/unit/test_repositories_split.py` and `tests/unit/test_web_split.py`

`git status --short` lists the spec's Scope paths, this review, and local `.vscode/` (not part of the phase). Given tests, template, and split-test diffs match the spec.

## Requirement checklist

- R1: gate 2; gate 1 (`test_the_facade_offers_every_name_and_only_those`); `create_group` exported
- R2: gate 2 (`test_a_refused_group`, `test_both_kinds_are_refused_before_a_taken_name`); `test_create_group_records_one_change_and_a_refusal_records_none`
- R3: gate 2 (`test_a_spending_group`, `test_a_group_with_flags`, `test_add_group_needs_a_migrated_database`)
- R4: gate 2 (the five web tests); gate 1 (`test_web_split.py`); browser probe
- R5: gate 2 (`test_an_empty_group_is_listed`); `test_an_empty_transfer_group_is_one_line`
- R6: gate 4; only those two split tests in `git diff --stat HEAD -- tests`

## Tests to write

- records `category_added`, refused records none: `test_create_group_records_one_change_and_a_refusal_records_none`
- outer spaces `"  Pets  "`: `test_outer_spaces_are_stripped`
- case `food` vs Food: `test_a_name_that_differs_only_in_case_is_taken`
- empty transfer group line: `test_an_empty_transfer_group_is_one_line`
- delete empty group: `test_an_empty_group_can_be_deleted`
- web `kind=transfer` `sensitive=on`: `test_a_transfer_group_that_is_sensitive`

## Spot checks

Each deciding test failed under the named change. Restored from `/tmp/fin-41a-spots/`, not `git checkout`. SPOT_FAILURES 0.

| Change | Deciding test | Result |
|---|---|---|
| 1. `create_group`: the taken name checked before both kinds | `test_both_kinds_are_refused_before_a_taken_name` | failed |
| 2. `create_group`: the name not stripped | `test_a_refused_group` | failed |
| 3. `create_group`: `transfer` ignored | `test_a_category_takes_its_new_groups_flags` | failed |
| 4. the route: an unknown kind taken as spending | `test_an_unknown_kind_is_refused_and_the_form_kept` | failed |
| 5. `category_lines`: an empty group left out | `test_an_empty_group_is_listed` | failed |
| 6. `category_lines`: a group line even when it has categories | the same test, after `Dog Food` | failed |
| 7. the CLI: the flag words in another order | `test_a_group_with_flags` | failed |

## Out of scope

Absent: a way to change a group's flags after it is added; a first category added with the group; a tax flag on a group (`is_tax` is false at create); anything of 41b or 41c (proposals, the Review page).

## Probe

Temporary `FIN_DATA_DIR=/tmp/fin-41a-web/data`, server on `127.0.0.1:18765` with an in-memory keyring (no real Keychain). Added a sensitive spending group `Pets` on the Categories page: notice `Group added.`, table row `Pets` / empty / `sensitive`. Then added category `Dog Food` to it: notice `Category added.`, table row `Pets` / `Dog Food` / `sensitive`. Server stopped afterwards.
