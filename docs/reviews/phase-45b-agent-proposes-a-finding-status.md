# Review: Phase 45b

- Verdict: PASS
- Passed: 4291
- Findings: 0
- Approved deviations: `_open_row` moved into `chains.py` and `_propose_pair` into `transfers.py` (still using `proposals._now`) so `proposals.py` stays within 400 lines; `finding_subject` uses `String(NAME_LIMIT)`; extra tests for `status_for`, stored fields, declined and open month checks, out of date from June, the Review page, and a default month on the tool
- For the architect: None

## Findings

None

Parts that needed a repair: `_propose_pair` kept calling `proposals._now` after the move so earlier transfer tests that patch that clock still pass; unreachable `finding_month is None` guards in `finding_proposals` were replaced with asserts so the include coverage report stays at 100%.

Built beyond the spec: extra tests for `status_for` matching `status_of`, `target_id` 0 with a cut subject and stored month on ignore, declined and open handled across May and June, an ignored May proposal going out of date when ignored from June, the Review page accepting a finding proposal, and `propose_finding_status` with no month.

## Gates

- `scripts/check.py --first migrations,core,mcp,cli,web`: last line `All checks passed.`; summary lists `tests (migrations,core,mcp,cli,web): passed` then `tests: passed`; 4291 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table
- Given tests: `15 passed`
- Coverage include report: `TOTAL 1330 0 306 0 100%`
- `git diff --stat HEAD -- tests`: `tests/support.py` and the twelve files of the given diff, no other
- `git grep -n -e "set_finding_status" -e "reopen_finding" -- src/finances/mcp_server`: no output

`git status --short` lists the spec's Scope paths, `docs/progress.md`, `docs/reviews/phase-45b-agent-proposes-a-finding-status.md`, and local `.vscode/` (not part of the phase). The given test files and the thirteen-file test diff match the spec.

## Requirement checklist

- R1: gate 2 (`test_migration_0026.py`)
- R2: gate 1 (`test_proposal_rules.py`, `test_rule_proposal_rules.py`); gate 2 (`test_accepting_records_the_status_in_history`); `test_status_for_matches_status_of_for_the_same_parts`
- R3: gate 2 (`test_a_refused_proposal`, `test_a_finding_with_a_status_is_refused`, `test_one_open_proposal_for_a_finding`, `test_a_declined_proposal_is_not_made_again`); `test_a_stored_proposal_keeps_target_zero_month_and_a_cut_subject`; `test_a_declined_handled_for_may_allows_handled_for_june`
- R4: gate 2 (the accept tests, `test_a_person_setting_the_status_first_puts_it_out_of_date`); `test_an_ignored_proposal_goes_out_of_date_when_ignored_from_june`
- R5: gate 2 (the review rows and accepted texts); `test_the_review_page_lists_and_accepts_a_finding_proposal`
- R6: gate 2 (`test_get_insights_lists_the_set_aside_findings`, the item shapes); gate 1 (`test_mcp_more.py`, `test_mcp_accounts.py`, `test_mcp_proposals.py`); gate 5; descriptions match the spec
- R7: gate 4; only those files

## Tests to write

- `status_for` matches `status_of` (handled in May asked for June: None): `test_status_for_matches_status_of_for_the_same_parts`
- stored `target_id` 0, ignored keeps `finding_month`, subject cut to 100: `test_a_stored_proposal_keeps_target_zero_month_and_a_cut_subject`
- declined handled for May allows handled for June: `test_a_declined_handled_for_may_allows_handled_for_june`
- open handled for May allows handled for June: `test_an_open_handled_for_may_allows_handled_for_june`
- ignored from May goes out of date when ignored from June: `test_an_ignored_proposal_goes_out_of_date_when_ignored_from_june`
- Review page lists and accepts: `test_the_review_page_lists_and_accepts_a_finding_proposal`
- tool with no month uses this month: `test_propose_finding_status_with_no_month_uses_this_month`

## Spot checks

Each deciding test failed under the named change. Restored from `/tmp/` copies, not `git checkout`. SPOT_FAILURES 0.

| Change | Deciding test | Result |
|---|---|---|
| 1. no check of the finding's status | `test_a_finding_with_a_status_is_refused` | failed |
| 2. declined check without the status | `test_a_declined_proposal_is_not_made_again` | failed |
| 3. no open-proposal check | `test_one_open_proposal_for_a_finding` | failed |
| 4. out of date never true | `test_a_person_setting_the_status_first_puts_it_out_of_date` | failed |
| 5. accepting stores without History | `test_accepting_records_the_status_in_history` | failed |
| 6. subject stored as the agent typed it | `test_the_agent_proposes_a_finding_handled` | failed |
| 7. `accepted_text` keeps the month for ignored | `test_the_agent_proposes_a_finding_ignored` | failed |
| 8. `set_aside` holding every finding | `test_get_insights_lists_the_set_aside_findings` | failed |
| 9. `transaction_id` from `target_id` | `test_the_agent_proposes_a_finding_handled` | failed |
| 10. open check without month | `test_an_open_handled_for_may_allows_handled_for_june` | failed |

## Out of scope

Absent: a proposal to reopen; a proposal shown on the Insights page; out of date when the finding no longer shows; a History link for kind `finding`; a chain through a finding proposal.

## Probe

None.
