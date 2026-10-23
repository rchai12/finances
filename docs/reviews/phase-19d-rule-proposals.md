# Review: Phase 19d

- Verdict: PASS
- Passed: 3482
- Findings: 0
- Approved deviations: None
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write")

## Gates

- `scripts/check.py`: `3482 passed`, `All checks passed.` (N + 5 = 3455; extra 27 from extra tests)
- Given tests: `5 passed`
- Earlier cli review, web review, proposals, and transfer proposals: `48 passed`
- Coverage of domain.proposals, db.repositories, categorize.service, views.review, and mcp_server: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: the nine files of the given diff
- `git grep -n "from finances.categorize" -- src/finances/db src/finances/domain`: no output
- `git grep -n "accept_proposal[^s]" -- src/finances/cli src/finances/web`: no output
- Given migration and tests match the spec blocks; the nine-file diff applied

## Requirement checklist

- R1: `test_0015_follows_0014`; `test_the_rule_columns_come_and_go`
- R2: `test_the_kinds`; `test_a_rule_out_of_date`; `test_the_text_of_a_rule`; `test_the_new_fields_default_to_none`
- R3: `test_a_stored_rule_proposal_changes_nothing`; `test_refused_rule_proposals`; `test_equals_matches_the_cleaned_merchant`; `test_the_same_match_and_pattern_cannot_be_proposed_again`; `test_declined_then_another_category_is_stored`; `test_one_open_proposal_per_match_and_pattern`
- R4: `test_a_rule_proposal_out_of_date`
- R5: `test_accepting_a_rule_runs_the_rules_once`; `accept_proposal` uses `create_rule(session, pattern, value, match, priority)`
- R6: `test_a_rule_then_a_category_runs_once_at_the_end`; `test_only_a_category_does_not_run_the_rules`; `accept_proposals` calls `categorize` once after the loop
- R7: `test_a_person_accepts_it_in_the_terminal`
- R8: `test_a_person_accepts_it_in_the_terminal`; `test_accepting_a_rule_on_the_review_page`; `test_an_out_of_date_choice_on_the_review_page_adds_no_rule`
- R9: `test_the_agent_proposes_a_rule`; `test_list_proposals_shows_rule_beside_a_category`
- R10: `git diff --stat HEAD -- tests` lists the nine given-diff files
- R2 to R8 edges: `tests/unit/test_rule_proposal_rules.py` and `tests/integration/test_rule_proposals.py`

## Probe

None. Look through the MCP tools on a temporary `FIN_DATA_DIR` (never the owner's `data/`): one card and `SQ *ACME COFFEE 12345`; `propose_rule` with `equals`, `ACME COFFEE`, and `Dining` stored an open rule; `fin review accept --id 1` accepted it and ran the rules; `fin rules list` showed the rule; the purchase was in Dining. `FAILURES 0`.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. Check the pattern before the reason: `test_refused_rule_proposals[kwargs0-a reason must be 1 to 200 characters]` fails (pattern message).
2. Match the example's description, not `clean_merchant` of it: `test_the_agent_proposes_a_rule` fails (the rule does not match).
3. The declined check also compares the priority: `test_declined_then_another_category_is_stored` fails (DID NOT RAISE).
4. The declined check ignores the category: `test_declined_then_another_category_is_stored` fails (`a person declined this proposal already`).
5. Run the rules straight after each rule proposal: `test_a_rule_then_a_category_runs_once_at_the_end` fails (`CategorizeResult(4, 3, 1)`).
6. Run the rules always: `test_accepting_and_declining` fails (a second `Categorized ...` line).
7. A rule exists when only the pattern matches: `test_a_rule_proposal_out_of_date[starts_with-False]` fails (out of date).
8. Skip the out-of-date check for a rule: `test_a_rule_proposal_out_of_date[rename-True]` fails (`category not found`).
9. `"category"` only for a category proposal: `test_the_agent_proposes_a_rule` fails (`None` vs `"Dining"`).
10. Leave out the categorize line: `test_a_person_accepts_it_in_the_terminal` fails (one line).

## Out of scope

Absent: alias, finding-status, rule-edit, and rule-delete proposals; pairing transfers after the run; a change to `fin rules`, the Categories page, the Review page's template, or `open_suggestions`; a would-change count; a tool that accepts, declines, or adds a rule.
