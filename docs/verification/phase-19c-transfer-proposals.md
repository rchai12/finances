# Verify Phase 19c: the agent proposes transfers

Spec: `docs/phases/phase-19c-transfer-proposals.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added transfer and not-a-transfer proposals: a migration with one column, two repository functions, deciding by kind, two MCP tools, and the review text for both kinds. A migration, a diff to earlier tests, and four test files were given.

These are correct and must not be reported: the order of names in `__all__`; one private helper shared by the two repository functions; `value` stored as `""` for a pair.

## 1. Gates

N is `3417` when Phase 19b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 27 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_pair_proposal_rules.py tests/integration/test_migration_0014.py tests/integration/test_transfer_proposals.py tests/integration/test_mcp_transfer_proposals.py --no-cov` | exactly `27 passed` |
| `.venv/bin/python -m pytest tests/integration/test_proposals.py tests/integration/test_mcp_proposals.py tests/e2e/test_cli_review.py tests/integration/test_web_review.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.proposals --cov=finances.db.repositories --cov=finances.analysis.review --cov=finances.views.review --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | the eleven files of the given diff |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope, the eleven earlier test files, the new migration, and five new test files. The migration and the diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R10 | gates 1 to 5 | pass |
| R3, R5, R7, R8 (edges) | the coder's `tests/integration/test_transfer_proposals_more.py` | each item of the spec's "Tests to write" has a test |
| R5 | read `accept_proposal` | a pair is made only by `create_transfer_pair(..., CONFIRMED)` and refused only by `reject_transfer` |

## 4. Probe

None. Look once through the MCP tools: on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with two accounts and $20.00 out of one and into the other the same day, call `propose_transfer`, then `fin review accept --id 1`, and see the pair in `fin transfers list` as confirmed.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. Refuse a pair once any proposal for it was declined, whatever its kind | `test_declined_then_only_the_other_kind` | the not-a-transfer proposal is stored | refused: declined already |
| 2. Accept a transfer as `auto` | `test_accepting_a_transfer` | status `confirmed`, `transfer_confirmed` recorded | status `auto`, no change recorded |
| 3. Use 19a's out-of-date rule for a pair | `test_an_out_of_date_pair_proposal[rejected]` | refused: out of date | accepted |
| 4. Skip the rejection check when proposing | `test_a_pair_said_not_to_be_a_transfer` | refused | stored |
| 5. Leave the kind filter out of `open_suggestions` | `test_suggestions_are_categories_only` | `{}` | `{1: ""}` |
| 6. Keep `"category": value` for a pair | `test_the_agent_proposes_a_transfer` | `None` | `""` |

## 6. Out of scope

Each must be absent: rule proposals; an unpair proposal; a change to `fin transfers`, the Transfers page, or the Review page's template; a tool that accepts, declines, or pairs.
