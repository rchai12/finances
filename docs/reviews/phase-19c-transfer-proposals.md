# Review: Phase 19c

- Verdict: PASS
- Passed: 3450
- Findings: 0
- Approved deviations: None
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write")

## Gates

- `scripts/check.py`: `3450 passed`, `All checks passed.` (N + 27 = 3444; extra 6 from extra tests)
- Given tests: `27 passed`
- Earlier proposals, mcp proposals, cli review, and web review tests: `41 passed`
- Coverage of domain.proposals, db.repositories, analysis.review, views.review, and mcp_server: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: the eleven files of the given diff
- Given migration and tests match the spec blocks; the eleven-file diff applied
- Working tree also lists `.claude/hooks/`, `.claude/settings.json`, and `.claude/skills/phase-architect/SKILL.md`, which are not in this phase's Scope

## Requirement checklist

- R1: `test_0014_follows_0013`; `test_other_id_comes_and_goes`
- R2: `test_the_kinds`; `test_a_pair_out_of_date`; `test_the_text_of_each_kind`; `test_a_category_proposal_has_no_other_id`
- R3: `test_a_transfer_proposal_changes_nothing`; `test_refused_pair_proposals`; `test_a_pair_said_not_to_be_a_transfer`; `test_one_open_proposal_per_pair`; `test_declined_then_only_the_other_kind`
- R4: `test_an_out_of_date_pair_proposal`; `test_a_deleted_transaction_makes_a_pair_out_of_date`
- R5: `test_accepting_a_transfer`; `test_accepting_not_a_transfer`; `accept_proposal` uses `create_transfer_pair(..., CONFIRMED)` and `reject_transfer`
- R6: `test_suggestions_are_categories_only`
- R7: `test_a_person_reviews_it_in_the_terminal`; `test_reviewing_not_a_transfer_in_the_terminal`
- R8: `test_the_agent_proposes_a_transfer`; `test_the_not_transfer_tool_and_in_id_on_the_list`
- R9: `test_the_agent_proposes_a_transfer` (registered after `propose_category`); given diff to `test_mcp_proposals.py`
- R10: `git diff --stat HEAD -- tests` lists the eleven given-diff files
- R3, R5, R7, R8 edges: `tests/integration/test_transfer_proposals_more.py`

## Probe

None. Look through the MCP tools on a temporary `FIN_DATA_DIR` (never the owner's `data/`): two accounts and $20.00 out of one and into the other the same day; `propose_transfer` stored an open pair; `fin review accept --id 1` printed `Accepted proposal 1: transactions 1 and 2 are a transfer.`; `fin transfers list` showed the pair as confirmed. `FAILURES 0`.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. Refuse a pair once any proposal for it was declined, whatever its kind: `test_declined_then_only_the_other_kind` fails (`a person declined this proposal already`).
2. Accept a transfer as `auto`: `test_accepting_a_transfer` fails (`(1, 2, 'auto') == (1, 2, 'confirmed')`).
3. Use 19a's out-of-date rule for a pair: `test_an_out_of_date_pair_proposal[rejected]` fails (DID NOT RAISE).
4. Skip the rejection check when proposing: `test_a_pair_said_not_to_be_a_transfer` fails (DID NOT RAISE).
5. Leave the kind filter out of `open_suggestions`: `test_suggestions_are_categories_only` fails (`{1: ''} == {}`).
6. Keep `"category": value` for a pair: `test_the_agent_proposes_a_transfer` fails (`"category": None` vs `""`).

## Out of scope

Absent: rule proposals; an unpair proposal; a change to `fin transfers`, the Transfers page, or the Review page's template; a tool that accepts, declines, or pairs.
