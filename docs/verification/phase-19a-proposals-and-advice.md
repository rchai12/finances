# Verify Phase 19a: the agent proposes categories, and a person reviews them

Spec: `docs/phases/phase-19a-proposals-and-advice.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added proposals and an advice log (a given migration), their repository area, two writing MCP tools and two reading ones, and `fin review`. Five test files, the migration, and a diff to nine earlier test files were given.

These are correct and must not be reported: the duplicate and declined checks done in one query loop; `fin review`'s two deciding commands sharing a helper; `review_items` reading the assignments once.

## 1. Gates

N is `3349` when Phase 34b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 39 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_proposal_rules.py tests/integration/test_migration_0013.py tests/integration/test_proposals.py tests/integration/test_mcp_proposals.py tests/e2e/test_cli_review.py --no-cov` | exactly `39 passed` |
| `.venv/bin/python -m pytest tests/integration/test_mcp_accounts.py tests/integration/test_mcp_more.py tests/integration/test_migration_chain.py tests/unit/test_repositories_split.py tests/unit/test_audit_rules.py tests/e2e/test_cli_audit.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.proposals --cov=finances.db.repositories --cov=finances.analysis.review --cov=finances.views.review --cov=finances.cli.review --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` | no output |
| `git grep -n --untracked -E "\.(debug|info|warning|error|exception|critical)\(|print\(" -- src/finances/mcp_server src/finances/cli/mcp.py` | no output |
| `git diff --stat HEAD -- tests` | the nine files of the given diff |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope, the nine earlier test files, and the new files (the migration, `domain/proposals.py`, `repositories/proposals.py`, `analysis/review.py`, `views/review.py`, `cli/review.py`, six test files). The migration, the descriptions, and the diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R11 | gates 1 to 7 | pass |
| R5, R6, R8 (edges) | the coder's `tests/integration/test_proposals_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

Run Phase 14a's stdio probe (its guide, section 4); its tool-list line now lists more tools. Then, with the same `FIN_DATA_DIR`, ask in one line of Python through the stdio client for `propose_category` on transaction 1: it must answer `transaction not found` (an empty database), proving the writing path refuses through a real pipe as well.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `propose_category` writes through `reading()` | `test_a_proposal_and_its_listing` | the proposal | `attempt to write a readonly database` |
| 2. `accept_proposal` writes the assignment directly (`_assign`) | `test_accepting_is_the_persons_choice` | `category_set` row | no `category_set` row |
| 3. `propose_category` treats a rule's category as decided | `test_a_rules_category_can_be_proposed_over` | `Dining` | refused |
| 4. The declined check compares the category as typed, not its stored name | `test_declining_and_not_again` (`coffee & dessert`) | refused | a second proposal |
| 5. `fin review accept` commits each id on its own | `test_all_or_none` | three rows still listed | proposal 2 accepted |
| 6. A third tool is registered with `WRITES_PROPOSALS` | `test_only_two_tools_write_and_none_decides` | two | three |

## 6. Out of scope

Each must be absent: a web page for proposals; transfer or rule proposals; a tool that accepts, declines, or edits; any write from `mcp_server` but the two.
