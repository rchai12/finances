# Verify Phase 19d: the agent proposes rules

Spec: `docs/phases/phase-19d-rule-proposals.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added rule proposals: a migration with three columns, `propose_rule` with nine checks, accepting through `create_rule`, a service that accepts a list and runs the rules once after, the review texts for a rule, and one MCP tool. A migration, a diff to earlier tests, and two test files were given; most behaviour is tested by the coder's two files, so section 5 carries weight.

These are correct and must not be reported: the order of names in `__all__`; how `fin review accept` and the Review page are rewired, as long as each goes through `accept_proposals`; a private helper shared by the out-of-date check and `propose_rule`'s rule-exists check; `decline` still going through `decline_proposal` per id.

## 1. Gates

N is `3450` when Phase 19c was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 5 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_migration_0015.py tests/integration/test_mcp_rule_proposals.py --no-cov` | exactly `5 passed` |
| `.venv/bin/python -m pytest tests/e2e/test_cli_review.py tests/integration/test_web_review.py tests/integration/test_proposals.py tests/integration/test_transfer_proposals.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.proposals --cov=finances.db.repositories --cov=finances.categorize.service --cov=finances.views.review --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | the nine files of the given diff |
| `git grep -n "from finances.categorize" -- src/finances/db src/finances/domain` | no output |
| `git grep -n "accept_proposal[^s]" -- src/finances/cli src/finances/web` | no output |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope, the nine earlier test files, the new migration, and four new test files. The migration and the diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1, R9, R10 | gates 1 and 2 | pass |
| R2 to R8 (edges) | the coder's `tests/unit/test_rule_proposal_rules.py` and `tests/integration/test_rule_proposals.py` | each item of the spec's "Tests to write" has a test using its deciding input |
| R3 | read `propose_rule` | the nine checks run in the spec's order; the match test is `rule_matches` on `clean_merchant` |
| R5 | read `accept_proposal` | a rule is added only by `create_rule(session, pattern, value, match, priority)` |
| R6 | read `accept_proposals` | `categorize` is called at most once, after the loop |

## 4. Probe

None. Look once through the MCP tools: on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with one card and a purchase `SQ *ACME COFFEE 12345`, call `propose_rule` with `equals`, `ACME COFFEE`, and `Dining`, then `fin review accept --id 1`, and see the rule in `fin rules list` and the purchase in Dining.

## 5. Spot checks

Each row is one change to the named function. The deciding test must fail under it; a row whose test is the coder's checks that the coder's test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `propose_rule`: check the pattern before the reason | coder: blank reason and blank pattern | `a reason must be 1 to 200 characters` | `a rule pattern must be 1 to 100 characters` |
| 2. `propose_rule`: match the example's description, not `clean_merchant` of it | given `test_the_agent_proposes_a_rule` (`equals "ACME COFFEE"`, example `SQ *ACME COFFEE 12345`) | the item | `ToolError`: does not match |
| 3. `propose_rule`: the declined check also compares the priority | coder: declined `contains "ACME COFFEE" -> Dining`, then the same at priority 9 | refused: declined already | stored |
| 4. `propose_rule`: the declined check ignores the category | coder: the same declined, then with `Coffee & Dessert` | stored | refused: declined already |
| 5. `accept_proposals`: run the rules straight after each rule proposal | coder: rule (1) and category for 4 (2), accepted as `[1, 2]` | `CategorizeResult(4, 3, 0)` | `CategorizeResult(4, 3, 1)` |
| 6. `accept_proposals`: run the rules always | earlier `tests/e2e/test_cli_review.py` (a category accepted prints one line) | one line | a second `Categorized ...` line |
| 7. `proposal_out_of_date`: a rule exists when only the pattern matches | coder: `equals` proposed, a `starts_with` rule with the same pattern added | not out of date | out of date |
| 8. `accept_proposal`: skip the out-of-date check for a rule | coder: `Dining` renamed to `Eating Out` | the spec's out-of-date message | `category not found` |
| 9. `_proposal_item`: `"category"` only for a category proposal | given `test_the_agent_proposes_a_rule` | `"Dining"` | `None` |
| 10. `fin review accept`: leave out the categorize line | given `test_a_person_accepts_it_in_the_terminal` | two lines | one line |

## 6. Out of scope

Each must be absent: alias, finding-status, rule-edit, and rule-delete proposals; pairing transfers after the run; a change to `fin rules`, the Categories page, the Review page's template, or `open_suggestions`; a would-change count; a tool that accepts, declines, or adds a rule.
