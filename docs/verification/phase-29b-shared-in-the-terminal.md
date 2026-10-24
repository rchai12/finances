# Verify Phase 29b: shared expenses in the terminal

Spec: `docs/phases/phase-29b-shared-in-the-terminal.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added `fin shared` with seven commands over 29a's repository and report, and their texts in a new `views/shared.py`. One test file was given; no earlier test changes.

These are correct and must not be reported: the commands sharing a private helper to read money; the tables printed with `print_rows`; `share_text` written with one branch per sign or a small mapping, as long as its output is the spec's.

## 1. Gates

N is `3713` when Phase 29a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 14 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/e2e/test_cli_shared.py --no-cov` | exactly `14 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.cli.shared --cov=finances.views.shared --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | no output |

This search must print nothing:

- `git grep -n "half_share\|signed_share\|balances(\|SharedExpenseRow\|SettlementRow" -- src/finances/cli src/finances/views`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, `src/finances/cli/main.py`, the two new modules, and three new test files.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_refused`); read `cli/shared.py` | every command calls `require_current_schema()` |
| R2 | gate 2; the coder's view tests | pass |
| R3 | gate 2 (`test_sharing`, `test_refused`); the coder's joint and pending cases | pass |
| R4 | gate 2 (`test_unsharing`) | passes |
| R5 | gate 2 (`test_sharing`) | passes |
| R6 | gate 2 (`test_sharing`, `test_settling`, `test_unsharing`) | pass |
| R7 | gate 2 (`test_settling`, `test_a_settlement_today`) | pass |
| R8 | gate 2 (`test_settling`) | passes |
| R9 | gate 2 (`test_settling`, `test_refused`) | pass |

## 4. Probe

None. Look once in the terminal: on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with two people and a purchase on a card one of them owns, `fin shared add`, `fin shared settle`, and `fin shared owed`, and see the difference owed.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `share_text`: no flip for a negative share | given `test_sharing` (the refund) | `Sam owes Alex $2.00.` | `Alex owes Sam -$2.00.` |
| 2. `add`: `--share` blank read as zero | given `test_sharing` (no `--share`) | `$10.00` | the size refusal |
| 3. `settle`: `date.today()` instead of `clock.today()` | given `test_a_settlement_today` | `2026-06-01` | the machine's day |
| 4. `owed`: shares only, settlements left out | given `test_settling` | `Alex owes Sam $6.00.` | `$10.00` |
| 5. `add`: `--paid-by` not passed | coder: a joint purchase with `--paid-by Sam` | stored | the joint message |
| 6. `share_rows`: the owed size, not signed | given `test_sharing` (`list`) | `-$2.00` | `$2.00` |

## 6. Out of scope

Each must be absent: any page or form; an MCP tool for shares; a share's date or description in `fin shared list`; filters; a change to 29a's repository or rules.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
