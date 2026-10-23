# Verify Phase 19e: the agent proposes merchant aliases

Spec: `docs/phases/phase-19e-alias-proposals.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added alias proposals: a migration with one column, `propose_merchant_alias` with five checks, accepting through `add_alias`, the rules run after an accepted alias, the review texts, and one MCP tool. A migration, a diff to ten earlier test files, and two test files were given.

These are correct and must not be reported: the order of names in `__all__`; `proposal_out_of_date` catching `check_alias`'s `ValueError` directly or through a private helper; the open and declined checks done in one query or two.

## 1. Gates

N is `3534` when Phase 28b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 5 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_migration_0017.py tests/integration/test_mcp_alias_proposals.py --no-cov` | exactly `5 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.proposals --cov=finances.db.repositories --cov=finances.categorize.service --cov=finances.views.review --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | the ten files of the given diff |
| `git grep -n "add_alias" -- src/finances/mcp_server` | no output |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope, the ten earlier test files, the new migration, and three new test files. The migration and the diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_migration_0017.py`) | passes |
| R2 | the coder's tests; read `proposal_text` | `alias: ACME CAFE -> ACME COFFEE` for an alias, the other kinds unchanged |
| R3 | gate 2 (`test_the_agent_proposes_an_alias`, `test_a_refused_alias`); the coder's refusal cases | the five checks in the spec's order; the source is `clean_merchant` of the example |
| R4 | the coder's out-of-date cases | out of date only when `check_alias` would refuse |
| R5 | gate 2 (`test_a_person_accepts_it_in_the_terminal`); read `accept_proposal` and `accept_proposals` | the alias added only by `add_alias`; the rules run when a rule or an alias was accepted |
| R6 | gate 2 | both texts as the spec gives them |
| R7 | gate 2; gate 1 (`tests/integration/test_mcp_proposals.py`) | the item's `"alias"` and `"category"`; the repository names imported exactly |
| R8 | gate 4 | only the ten files |

## 4. Probe

None. Look once through the MCP tools: on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with purchases `SQ *ACME CAFE 12345` and `ACME COFFEE`, call `propose_merchant_alias` with example 1 and target `ACME COFFEE`, then `fin review accept --id 1`, and see the alias in `fin aliases list`.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `propose_merchant_alias`: the source is the description, not its cleaned name | given `test_the_agent_proposes_an_alias` | source `ACME CAFE` | `SQ *ACME CAFE 12345` |
| 2. `propose_merchant_alias`: `check_alias` against no aliases | coder: a person's `ACME CAFE -> BAZ CAFE`, then the proposal | refused: already merged | stored |
| 3. `propose_merchant_alias`: the declined check ignores the target | coder: declined into `ACME COFFEE`, then into `BAZ CAFE` | stored | refused: declined already |
| 4. `propose_merchant_alias`: the open check also compares the target | coder: open into `ACME COFFEE`, then example 3 into `BAZ CAFE` | refused: open | stored |
| 5. `accept_proposal`: skip the out-of-date check for an alias | coder: a person's `ACME CAFE -> BAZ CAFE` after the proposal | R5's message | `this merchant is already merged into another` |
| 6. `accept_proposals`: run the rules after a rule only | given `test_a_person_accepts_it_in_the_terminal` | two lines | one line |
| 7. `_proposal_item`: `"category"` the stored value for an alias | given `test_the_agent_proposes_an_alias` | `None` | `"ACME COFFEE"` |
| 8. `accepted_text`: an alias falls to the category line | given `test_a_person_accepts_it_in_the_terminal` | `ACME CAFE merged into ACME COFFEE` | `ACME COFFEE for transaction 1` |

## 6. Out of scope

Each must be absent: finding-status or alias-removal proposals; an MCP tool that lists aliases; a change to `fin aliases`, the aliases card, 28a's alias rules, or the Review page's template; a tool that accepts, declines, or adds an alias.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
