# Verify Phase 29c: shared expenses on the web

Spec: `docs/phases/phase-29c-shared-on-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a `shared` router with a Shared page and four form routes, a Shared card on a transaction's page fed by a new `share_of`, four notices, and a menu link. A template diff (one new template), a diff to two earlier tests, and one test file were given.

These are correct and must not be reported: where `shared` sits in `create_app`'s list of areas; the Shared page built by one private function used by the GET and the 400 renders; `people` built from `list_people` in each route or by a small private helper.

## 1. Gates

N is `3736` when Phase 29b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 10 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_shared.py --no-cov` | exactly `10 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web.routes.shared --cov=finances.web.routes.transactions --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | the two files of the given diff |

This search must print nothing:

- `git grep -n "half_share\|signed_share\|balances(\|SharedExpenseRow\|SettlementRow" -- src/finances/web`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files and templates of the spec's Scope (two of them new), the two earlier test files, and two new test files. The templates and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_the_shared_page`); the coder's not-migrated case | pass |
| R2 | gate 2 (`test_settling_on_the_page`, `test_a_refused_settlement`); the coder's blank-date case | pass |
| R3 | gate 2 (`test_deleting_a_settlement`) | passes |
| R4 | the coder's 405 cases | four 405s |
| R5 | gate 2 (`test_a_shared_transactions_page`); the coder's 400-page case | pass |
| R6 | gate 2 (`test_sharing_and_unsharing_on_a_transactions_page`, `test_a_refused_share`); the coder's joint case | pass |
| R7 | gate 2; the coder's not-shared case | pass |
| R8 | gate 2; read `NOTICES` | the four texts as the spec gives them |
| R9 | gate 2 (`test_the_shared_page`) | passes |
| R10 | gate 4 | only the two files |

## 4. Probe

None. Look once in a browser: `fin web` on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with two people and a purchase on a card one owns, share it on its page, record a settlement on the Shared page, and see who owes whom change.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. the settle route: `date.today()` for a blank date | coder: a blank date with `_today` replaced after the app is created | the replaced day | the machine's day |
| 2. the Shared page: `day` not filled with today | given `test_the_shared_page` | `2026-06-01` | `""` |
| 3. the share route: a blank `share` read as zero | coder: a share posted with `share` blank | half owed | the size refusal |
| 4. `_transaction_page`: `share_form` dropped on a 400 | given `test_a_refused_share` (`30`) | the box keeps `30` | `""` |
| 5. the clear route: `unshare_transaction` not called | given `test_sharing_and_unsharing_on_a_transactions_page` | `Sam owes Alex $6.00.` on the Shared page | `Alex owes Sam $4.00.` |

## 6. Out of scope

Each must be absent: shares on the Transactions page or another table; an MCP tool for shares; a filter on the Shared page; editing a settlement or share in place; any change to 29a's rules or 29b's commands.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
