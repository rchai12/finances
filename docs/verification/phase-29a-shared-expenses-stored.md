# Verify Phase 29a: shared expenses stored

Spec: `docs/phases/phase-29a-shared-expenses-stored.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added shared expenses without any command or page: a migration with two tables, a critical pure module for shares and who owes whom, six repository functions, the payer found from the cardholder or the account's owner, a shared transaction kept out of transfers and looked after by the feed, and `owed_report`. A migration, a diff to four earlier tests, and two test files were given. Most repository behaviour is tested by the coder's file, so section 5 carries weight.

These are correct and must not be reported: a private helper that builds a share's audit text; the payer found with the owner and alias lists loaded once per call; `balances` keyed by a sorted pair or by two counters, as long as its output is the spec's.

## 1. Gates

N is `3678` when Phase 28g was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.` (its critical coverage step includes `domain/shared.py`); at least N + 25 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_shared.py tests/integration/test_migration_0020.py --no-cov` | exactly `25 passed` |
| `.venv/bin/python -m pytest tests/unit/test_shared.py -o addopts="" --import-mode=importlib --cov=finances.domain.shared --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.shared --cov=finances.domain.audit --cov=finances.db.repositories --cov=finances.analysis.shared --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | the four files of the given diff |
| `git grep -n "domain/shared.py" -- scripts/critical_modules.txt docs/testing.md` | one line in each |

This search must print nothing:

- `git grep -n "SharedExpenseRow\|SettlementRow" -- src/finances/analysis src/finances/categorize src/finances/cli src/finances/web`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, `docs/testing.md`, `scripts/critical_modules.txt`, the source files of the spec's Scope (three of them new), the four earlier test files, the new migration, and three new test files. The migration and the diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_migration_0020.py`); gate 1 (`tests/integration/test_migration_chain.py`) | pass |
| R2 | gates 2, 3, and 6 | pass; one line in each file |
| R3 | gate 1 (`test_audit_rules.py`, `test_cli_audit.py`) | pass |
| R4 | the coder's share cases; read `share_transaction` | the refusals in the spec's order; the payer from `person_for`; `before` and `after` as the spec gives them |
| R5 | the coder's unshare cases | pass |
| R6 | the coder's settlement cases | pass |
| R7 | the coder's transfer cases; read `_check_transfer` | the shared check after the existing ones |
| R8 | the coder's feed cases; read `update_feed_transaction` | the share cleared only when the amount changes, `who` `system` |
| R9 | the coder's report case | `[Owed("Alex", "Sam", 600)]` |
| R10 | gate 5 | only the four files |

## 4. Probe

None: nothing in this phase reaches a command or a page. The verifier reads `share_transaction`, `_check_transfer`, and `update_feed_transaction` against R4, R7, and R8 instead.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `half_share`: round up | given `(-2001)` | 1000 | 1001 |
| 2. `signed_share`: no sign for money in | given `(2000, 500)` | -500 | 500 |
| 3. `signed_share`: the whole amount refused | given `(-2000, 2000)` | 2000 | refused |
| 4. `balances`: a settlement adds to what the payer owes | given `test_a_settlement_pays_it_down` (700) | `Owed("Sam", "Alex", 200)` | `Owed("Alex", "Sam", 1200)` |
| 5. `balances`: sorted by creditor first | given `test_three_people_by_debtor_then_creditor` | Alex to Kai, Alex to Sam, Kai to Sam | Alex to Kai, Kai to Sam, Alex to Sam |
| 6. `share_transaction`: the owner before the cardholder | coder: purchase 2, cardholder aliased to Alex | payer Alex | payer Sam |
| 7. `share_transaction`: a joint payer let through | coder: purchase 3 with no payer | refused | stored or an error |
| 8. `share_transaction`: people checked before pending | coder: pending with an unknown debtor | the pending message | `person not found` |
| 9. `list_transfer_movements`: keep shared transactions | coder: 5 shared, then `pair_transfers` | nothing paired | 5 and 6 paired |
| 10. `update_feed_transaction`: clear on every update | coder: same amount, new description | share kept | share cleared |

## 6. Out of scope

Each must be absent: any command, page, or MCP tool for shares; more than two people on one share; percentages; a settlement linked to a transfer or edited in place; sharing a pending transaction or a transfer.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
