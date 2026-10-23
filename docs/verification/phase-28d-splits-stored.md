# Verify Phase 28d: splits stored

Spec: `docs/phases/phase-28d-splits-stored.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added splits without any command or page: a migration with one table, a critical pure rule, three repository functions, and changes in six existing modules so a split transaction counts as decided everywhere a category is decided, and its parts are looked after when a transaction or category is rewritten or deleted. A migration, a diff to four earlier tests, and two test files were given. Most behaviour is tested by the coder's file, so section 5 carries weight.

These are correct and must not be reported: a private helper in `splits.py` that the other repositories import to ask whether a transaction is split; the parts replaced by deleting and inserting or by updating; `delete_category` counting parts in one query with assignments or in a second.

## 1. Gates

N is `3574` when Phase 28c was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.` (its critical coverage step includes `domain/splits.py`); at least N + 19 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_splits.py tests/integration/test_migration_0019.py --no-cov` | exactly `19 passed` |
| `.venv/bin/python -m pytest tests/unit/test_splits.py -o addopts="" --import-mode=importlib --cov=finances.domain.splits --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.splits --cov=finances.domain.audit --cov=finances.db.repositories --cov=finances.categorize.service --cov=finances.analysis.spending --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | the four files of the given diff |
| `git grep -n "domain/splits.py" -- scripts/critical_modules.txt docs/testing.md` | one line in each |

This search must print nothing:

- `git grep -n "TransactionSplitRow" -- src/finances/analysis src/finances/categorize src/finances/cli src/finances/web`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, `docs/testing.md`, `scripts/critical_modules.txt`, the source files of the spec's Scope (two of them new), the four earlier test files, the new migration, and three new test files. The migration and the diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_migration_0019.py`); gate 1 (`tests/integration/test_migration_chain.py`) | pass |
| R2 | gates 2, 3, and 6 | pass; one line in each file |
| R3 | gate 1 (`test_audit_rules.py`, `test_cli_audit.py`) | pass |
| R4 | the coder's `set_split` cases; read `set_split` | the five refusals in the spec's order; the own category removed; `before` and `after` as the spec gives them |
| R5 | the coder's `clear_split` and `splits_for` cases | pass |
| R6 | the coder's categorize and by-hand cases; read the four by-hand functions | each refuses after its existence checks and before any change |
| R7 | the coder's proposal and uncategorized cases | pass |
| R8 | the coder's transfer cases; read `_check_transfer` | the split check comes after the three earlier checks |
| R9 | the coder's feed and category cases; read `update_feed_transaction` | the split cleared only when the amount changes, `who` `system` |
| R10 | the coder's flows case; read `flows_for` | `SPLIT` for category and group; no other `analysis` module changed |
| R11 | gate 5 | only the four files |

## 4. Probe

None: nothing in this phase reaches a command or a page. The verifier reads the six changed modules against R6 to R9 instead.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `check_split`: no sign check | given `(-2000, [-2100, 100])`, which adds up | refused: sign | None |
| 2. `check_split`: the count check after the sign check | given `(-2000, [100])` | `a split has 2 to 10 parts` | the sign message |
| 3. `check_split`: `MAX_PARTS` exclusive | given ten parts of -100 | None | refused: count |
| 4. `set_split`: `check_split` before the pending check | coder: a pending transaction with parts that do not add up | the pending message | the sum message |
| 5. `set_split`: keep the own category | coder: split of 1 after the rule set it | 1 has no own category | Groceries |
| 6. `categorize`: no skip for a split | coder: the rule run after the split | no own category | Groceries again |
| 7. `set_categories_by_hand`: check each id as it is set | coder: `[3, 1]` | 3 unchanged | 3 set to Dining |
| 8. `decided_by_a_person`: ignore a split | coder: `propose_category(1, ...)` | refused | stored |
| 9. `list_transfer_movements`: keep split transactions | coder: 3 split, then `pair_transfers` | nothing paired | 3 and 4 paired |
| 10. `update_feed_transaction`: clear on every update | coder: same amount, new description | split kept | split cleared |
| 11. `delete_category`: count assignments only | coder: deleting `Home & Garden` used by a part | refused: in use | `IntegrityError` or deleted |
| 12. `flows_for`: no `Split` label | coder: `load_flows` of 1 | `Split` | `Uncategorized` |

## 6. Out of scope

Each must be absent: parts counted in any report; any command, page, or MCP tool that splits or shows parts; splitting a pending transaction or a transfer; a split kept through an amount change.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
