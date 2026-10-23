# Review: Phase 19e

- Verdict: PASS
- Passed: 3550
- Findings: 0
- Approved deviations: None
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write")

## Gates

- `scripts/check.py`: `3550 passed`, `All checks passed.` (N + 5 = 3539; extra 11 from extra tests)
- Given tests: `5 passed`
- Coverage of domain.proposals, db.repositories, categorize.service, views.review, and mcp_server: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: the ten files of the given diff
- `git grep -n "add_alias" -- src/finances/mcp_server`: no output
- Given migration and tests match the spec blocks; the ten-file diff applied

## Requirement checklist

- R1: `test_0017_follows_0016`; `test_the_source_column_comes_and_goes`
- R2: `test_a_stored_alias_proposal_changes_nothing` (`alias: ACME CAFE -> ACME COFFEE`); `test_the_kinds`; `test_the_lists_and_limits`
- R3: `test_the_agent_proposes_an_alias`; `test_a_refused_alias`; `test_refused_alias_proposals`; `test_a_persons_alias_is_read_when_proposing`; `test_a_declined_alias_keys_on_source_and_target`; `test_an_open_alias_keys_on_the_source_only`
- R4: `test_an_alias_proposal_out_of_date_after_a_person_merges`; `test_an_unrelated_alias_does_not_stale_the_proposal`
- R5: `test_a_person_accepts_it_in_the_terminal`; `test_accepting_an_alias_runs_the_rules_once`; `accept_proposal` calls `add_alias(session, source, value)`
- R6: `test_a_person_accepts_it_in_the_terminal`
- R7: `test_the_agent_proposes_an_alias`; `test_list_proposals_shows_alias_beside_a_category`; `test_the_server_reaches_only_these_repository_functions`
- R8: `git diff --stat HEAD -- tests` lists the ten given-diff files

## Tests to write

- stored whole, no alias added: `test_a_stored_alias_proposal_changes_nothing`
- reason before `check_alias`; example 99: `test_refused_alias_proposals`
- person's alias then already-merged: `test_a_persons_alias_is_read_when_proposing`
- declined then other target stored: `test_a_declined_alias_keys_on_source_and_target`
- open keys on source only: `test_an_open_alias_keys_on_the_source_only`
- out of date after a person's alias; unrelated alias not stale: `test_an_alias_proposal_out_of_date_after_a_person_merges`; `test_an_unrelated_alias_does_not_stale_the_proposal`
- accept `CategorizeResult(3, 2, 0)` and audit: `test_accepting_an_alias_runs_the_rules_once`
- Review page sets purchase 1 to Dining: `test_accepting_an_alias_on_the_review_page`
- `list_proposals` alias beside category null: `test_list_proposals_shows_alias_beside_a_category`

## Probe

None. Look through the MCP tools on a temporary `FIN_DATA_DIR` (never the owner's `data/`): purchases `SQ *ACME CAFE 12345` and `ACME COFFEE`; `propose_merchant_alias` with example 1 and target `ACME COFFEE` stored an open alias; `fin review accept --id 1` accepted it and ran the rules; `fin aliases list` showed `ACME CAFE` to `ACME COFFEE`. `FAILURES 0`.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. Source is the description, not its cleaned name: `test_the_agent_proposes_an_alias` fails (`SQ *ACME CAFE 12345`).
2. `check_alias` against no aliases: `test_a_persons_alias_is_read_when_proposing` fails (DID NOT RAISE).
3. The declined check ignores the target: `test_a_declined_alias_keys_on_source_and_target` fails (`a person declined this proposal already`).
4. The open check also compares the target: `test_an_open_alias_keys_on_the_source_only` fails (DID NOT RAISE).
5. Skip the out-of-date check for an alias: `test_an_alias_proposal_out_of_date_after_a_person_merges` fails (`this merchant is already merged into another`).
6. Run the rules after a rule only: `test_a_person_accepts_it_in_the_terminal` fails (one line).
7. `"category"` the stored value for an alias: `test_the_agent_proposes_an_alias` fails (`"ACME COFFEE"`).
8. An alias falls to the category line: `test_a_person_accepts_it_in_the_terminal` fails (`ACME COFFEE for transaction 1`).

## Out of scope

Absent: finding-status or alias-removal proposals; an MCP tool that lists aliases; a change to `fin aliases`, the aliases card, 28a's alias rules, or the Review page's template; a tool that accepts, declines, or adds an alias.
