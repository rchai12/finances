# Verify Phase 28a: merchant aliases

Spec: `docs/phases/phase-28a-merchant-aliases.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added merchant aliases: a migration with one table, pure alias rules and a rule picker over several names, four repository functions with audit rows, the merged name in flows and refunds, either name for rules, and `fin aliases`. A migration, a diff to two earlier tests, and two test files were given; much of the behaviour is tested by the coder's two files, so section 5 carries weight.

These are correct and must not be reported: `pick_rule` rewritten on top of `pick_rule_for`, as long as its behaviour is unchanged; the option parameters in `cli/aliases.py` named anything (`from` is a Python keyword); the audit text built by a private helper; `alias_map` called inside `add_alias` or passed in.

## 1. Gates

N is `3482` when Phase 19d was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 10 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_migration_0016.py tests/e2e/test_cli_aliases.py --no-cov` | exactly `10 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.merchants --cov=finances.domain.rules --cov=finances.domain.audit --cov=finances.db.repositories --cov=finances.analysis.spending --cov=finances.analysis.refunds --cov=finances.categorize.service --cov=finances.views.categories --cov=finances.cli.aliases --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | the two files of the given diff |
| `git grep -n "clean_merchant(" -- src/finances/analysis/spending.py src/finances/analysis/refunds.py src/finances/categorize src/finances/db` | no output |
| `git grep -n "pick_rule(" -- src/finances/categorize` | no output |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope (two of them new), the two earlier test files, the new migration, and four new test files. The migration and the diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_migration_0016.py`); read `domain/text.py` | passes; `MERCHANT_NAME_LIMIT = 100` and the ORM uses it |
| R2 | gate 2 (`test_refused`); the coder's unit tests | each of the six checks refuses in the spec's order with its message |
| R3 | the coder's `pick_rule_for` tests | priority across names, lowest id among equals, None |
| R4 | gate 1 (`tests/unit/test_audit_rules.py`) | passes |
| R5 | the coder's integration tests; read `aliases.py` | two audit rows with the spec's text; no call into `categorize` |
| R6 | the coder's flows and refund tests; read `flows_for` | aliases loaded once per call, not once per transaction |
| R7 | gate 2 (`test_merging_a_merchant`); the coder's kept-category and `propose_rule` tests | pass |
| R8 | gate 2; read `cli/aliases.py` | each command calls `require_current_schema()`; no rule of R2 repeated there |
| R9 | gate 4 | only the two files |

## 4. Probe

None. Look once in the terminal: on a temporary `FIN_DATA_DIR` (never the owner's `data/`) with purchases `ACME CAFE` in January, February, and March and `ACME COFFEE` in April and May, one a month on the 5th for $4.50, run `fin recurring` before and after `fin aliases add --from "ACME CAFE" --to "ACME COFFEE"`, and see one series named `ACME COFFEE` after.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `categorize`: match the merged name only | coder: rule `contains "ACME CAFE"`, then the alias | `ACME CAFE` stays in Dining | it loses its category |
| 2. `categorize`: match the cleaned name only | given `test_merging_a_merchant` | `1 changed, 0 without a category` | `0 changed, 1 without a category` |
| 3. `pick_rule_for`: the first name with any match wins | coder: rules at priority 0 (`ACME CAFE`) and 5 (`ACME COFFEE`) | id 2 | id 1 |
| 4. `check_alias`: the already-merged check before the same-name check | given `test_refused` (`acme cafe` into `Acme Cafe`) | `a merchant cannot be merged into itself` | `this merchant is already merged into another` |
| 5. `check_alias`: no check that the target is merged | given `test_refused` (`BAZ CAFE` into `ACME CAFE`) | refused | exit 0, a chain stored |
| 6. `flows_for`: keep `clean_merchant` | coder: `load_flows` with the alias | `ACME COFFEE` | `ACME CAFE` |
| 7. `refund_facts`: keep `clean_merchant` | coder: refund `ACME COFFEE`, purchase `ACME CAFE` | the purchase found | none |
| 8. `fin aliases delete`: no categorize run after | given `test_removing_it` | two lines | one line |
| 9. `propose_rule`: match the cleaned name only | coder: example `ACME CAFE`, `equals "ACME COFFEE"` | stored | refused |
| 10. `add_alias`: store the names as typed | given `test_merging_a_merchant` (`  acme   cafe `) | `Merged "ACME CAFE"` | the typed text |

## 6. Out of scope

Each must be absent: an aliases page or form; the rule preview; an MCP alias tool; the uncategorized lists showing the merged name; an edit command; chains or their repair.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
