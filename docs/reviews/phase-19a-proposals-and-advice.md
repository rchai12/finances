# Review: Phase 19a

- Verdict: PASS
- Passed: 3397
- Findings: 0
- Approved deviations: extra tests also cover a declined proposal decided again, a rule-set category that is not out of date, and pairing after a proposal
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: three extra tests in `tests/integration/test_proposals_more.py` for declined-again, a rule-set category that stays current, and pairing after a proposal (needed for repository branch coverage)

## Gates

- `scripts/check.py`: `3397 passed`, `All checks passed.` (N + 39 = 3388; extra 9 from extra tests and one new split-area parametrize case)
- Given tests: `39 passed`
- Earlier accounts, more, chain, split, audit rules, and cli audit tests: `44 passed`
- Coverage of domain.proposals, db.repositories, analysis.review, views.review, cli.review, and mcp_server: `Required test coverage of 100% reached`
- Domain import search: no output
- MCP and mcp CLI log/print search: no output
- `git diff --stat HEAD -- tests`: the nine files of the given diff
- Given migration, descriptions, and tests match the spec blocks; the nine-file diff applied

## Requirement checklist

- R1: `test_0013_follows_0012`; `test_the_tables_and_their_row_classes`; `test_the_lists_and_limits`
- R2: `test_out_of_date`; `test_the_text_of_a_proposal`
- R3: `test_the_lists`
- R4: `test_a_proposal_changes_nothing`; `test_a_rules_category_can_be_proposed_over`; `test_refused_proposals`; `test_declining_and_not_again`
- R5: `test_accepting_is_the_persons_choice`; `test_an_out_of_date_proposal_cannot_be_accepted`; `test_listing_by_status`
- R6: `test_the_advice_log`
- R7: `test_the_open_proposals`; `test_an_out_of_date_proposal_shows_and_is_refused`
- R8: `test_accepting_and_declining`; `test_all_or_none`; `test_needs_a_migrated_database`
- R9: `test_a_database_that_is_not_migrated`; `test_a_proposal_and_its_listing`
- R10: `test_only_two_tools_write_and_none_decides`; `test_the_server_reaches_only_these_repository_functions`; `test_each_tool_description_matches_the_table`
- R11: `git diff --stat HEAD -- tests` lists the nine given-diff files
- R5, R6, R8 edges: `tests/integration/test_proposals_more.py`

## Probe

14a stdio probe: `FAIL three tools over stdio`; `ok   balances on an empty database`; `ok   months 0 refused`; `FAILURES 1`. Tool names now include `propose_category`, `list_proposals`, `log_advice`, and `list_advice`. On the same empty upgraded database, `propose_category` for transaction 1 answered `Error executing tool propose_category: transaction not found`.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. `propose_category` writes through `reading()`: `test_a_proposal_and_its_listing` fails (`structured_content` is None, the tool errors).
2. `accept_proposal` writes through `_assign`: `test_accepting_is_the_persons_choice` fails (no `category_set` row).
3. A rule's category counts as decided: `test_a_rules_category_can_be_proposed_over` fails (`a person has already decided this transaction`).
4. The declined check compares the typed name: `test_declining_and_not_again` fails (DID NOT RAISE).
5. `fin review accept` commits each id on its own: `test_all_or_none` fails (`2 == 3`, proposal 2 accepted).
6. `list_proposals` is registered with `WRITES_PROPOSALS`: `test_only_two_tools_write_and_none_decides` fails (three writers).

## Out of scope

Absent: a web page for proposals; transfer or rule proposals; a tool that accepts, declines, or edits; any write from `mcp_server` but `propose_category` and `log_advice`.
