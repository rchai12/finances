# Verify Phase 45b: the agent proposes a finding's status

Spec: `docs/phases/phase-45b-agent-proposes-a-finding-status.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added `set_aside` to `get_insights` and a `propose_finding_status` tool whose proposal, once accepted in review, stores the status as `fin findings handle` and `ignore` do. The proposal is out of date when the finding has a status by then. A migration, a diff to `tests/support.py` and twelve earlier test files, and two test files were given.

These are correct and must not be reported: a private helper shared by `set_finding_status` and accepting; a private helper moved out of `proposals.py` to keep it within 400 lines; an import inside a function to avoid a cycle with `proposals.py`; the tool calling `find_finding` and then `propose_finding_status` in one session.

## 1. Gates

N is `4268` when Phase 45a was the last phase built. Sections: migrations, core, mcp, cli, web.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first migrations,core,mcp,cli,web` | last line `All checks passed.`; the summary lists `tests (migrations,core,mcp,cli,web): passed`; at least N + 15 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table |
| `.venv/bin/python -m pytest tests/integration/test_migration_0026.py tests/integration/test_mcp_finding_proposals.py --no-cov` | exactly `15 passed` |
| `.venv/bin/python -m coverage report --include="*/finances/domain/proposals.py,*/finances/domain/findings.py,*/finances/db/orm.py,*/finances/db/repositories/findings.py,*/finances/db/repositories/finding_proposals.py,*/finances/db/repositories/proposals.py,*/finances/db/repositories/chains.py,*/finances/analysis/review.py,*/finances/views/review.py,*/finances/mcp_server/tools.py,*/finances/mcp_server/server.py" --fail-under=100` | exit 0, `TOTAL` at `100%` |
| `git diff --stat HEAD -- tests` | `tests/support.py` and the twelve files of the given diff, no other |
| `git grep -n -e "set_finding_status" -e "reopen_finding" -- src/finances/mcp_server` | no output |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope (`finding_proposals.py` and the migration new), the thirteen files of the given diff, and three new test files. The migration, the given test files, and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_migration_0026.py`) | pass |
| R2 | gate 1 (`test_proposal_rules.py`, `test_rule_proposal_rules.py`); gate 2 (`test_accepting_records_the_status_in_history`); the coder's `status_for` case | pass |
| R3 | gate 2 (`test_a_refused_proposal`, `test_a_finding_with_a_status_is_refused`, `test_one_open_proposal_for_a_finding`, `test_a_declined_proposal_is_not_made_again`); the coder's stored-fields and declined-month cases | pass |
| R4 | gate 2 (the accept tests, `test_a_person_setting_the_status_first_puts_it_out_of_date`); the coder's ignored-from-June case | pass |
| R5 | gate 2 (the review rows and accepted texts); the coder's Review page case | pass |
| R6 | gate 2 (`test_get_insights_lists_the_set_aside_findings`, the item shapes); gate 1 (`test_mcp_more.py`, `test_mcp_accounts.py`, `test_mcp_proposals.py`); gate 5; the descriptions read against the spec | pass, word for word |
| R7 | gate 4 | only those files |

## 4. Probe

None.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `propose_finding_status`: no check of the finding's status | given `test_a_finding_with_a_status_is_refused` | `this finding is already ignored` | stored |
| 2. the declined check without the status | given `test_a_declined_proposal_is_not_made_again` (then handled) | proposal 2 | `a person declined this proposal already` |
| 3. no open-proposal check | given `test_one_open_proposal_for_a_finding` | refused | stored |
| 4. out of date never true | given `test_a_person_setting_the_status_first_puts_it_out_of_date` | `out of date`, accept refused | accepted |
| 5. accepting stores the row without its History record | given `test_accepting_records_the_status_in_history` | `finding_handled` second | `proposal_accepted` then an older row |
| 6. the subject stored as the agent typed it | given `test_the_agent_proposes_a_finding_handled` (`dining`) | `"about": "Dining"` | `"about": "dining"` |
| 7. `accepted_text`: the month kept for ignored | given `test_the_agent_proposes_a_finding_ignored` | `interest in every month is ignored.` | `interest in 2026-05 is ignored.` |
| 8. `set_aside` holding every finding | given `test_get_insights_lists_the_set_aside_findings` | the spike alone | five items |
| 9. `_proposal_item`: `transaction_id` from `target_id` | given `test_the_agent_proposes_a_finding_handled` | `None` | `0` |
| 10. the open check by type and subject only, not month | the coder's open-month case (interest handled proposed for May, then for June) | stored | `this finding already has an open proposal` |

## 6. Out of scope

Each must be absent: a proposal to reopen; a proposal shown on the Insights page; a check that the finding still shows when accepting; a History link for kind `finding`.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
