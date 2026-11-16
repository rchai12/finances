# Verify Phase 47a: categorize and pair

Spec: `docs/phases/phase-47a-categorize-and-pair.md`. Follow `docs/phase-conventions.md` for review and report format. N is 4310; seven given cases.

## 1. Coder ran

The implementation files and progress entry must exist. The spec and guide must be committed in the intended baseline. Read `git status --short` and `git diff HEAD` before writing a review. If the baseline is uncommitted or unrelated changes make a scope gate inconclusive, report that condition separately.

## 2. Gates

Run separately, in order. The first gate is required before coverage. The given-test run comes after the coverage report because pytest can replace coverage data.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first web,cli,core` | final line `All checks passed.`; sections all 0 failed; at least 4317 passed, no skips, xfails, warnings summary, or failures |
| `.venv/bin/python -m coverage report --include="*/finances/categorize/service.py" --fail-under=100` | exit 0, TOTAL 100% |
| `.venv/bin/python -m pytest tests/integration/test_web_pair_after_rules.py --no-cov` | 7 passed |
| `git grep -n -F 'categorize(session)' -- src/finances/web/routes/categories.py src/finances/web/routes/transactions.py src/finances/web/routes/statements.py src/finances/web/routes/sync.py` | no output |
| `git status --short` | only spec Scope paths |

Compare the given file with the spec block, and check that no earlier test or migration changed.

## 3. Requirements and deciding evidence

| Requirement | Evidence |
|---|---|
| R1 | coder unit tests assert order, identity, same session, exception and no commit/rollback |
| R2 | coder CLI case checks returned result and unchanged output |
| R3 | seven given cases check stored pair and each exact redirect |
| R4 | coder acceptance cases distinguish proposal submission, rule/alias acceptance, and an unrelated kind |
| R5 | coder web cases check one invocation per existing path |
| R6 | coder failure case reads initiating write and audit state in a fresh session after failure |
| R7 | coder exclusion and report cases; full suite and given scope audit |

For each listed coder test case, name the actual test that covers it. A missing case or an assertion that only executes code is a finding. Correct private helpers inside Scope are reasonable.

## 4. Spot checks

Trace these changes in a scratch copy only; do not modify the code being reviewed. Confirm the named test's input reaches the changed behavior, and the deciding result differs. Restore nothing in the reviewed tree.

| Change | Deciding test | Correct | Broken |
|---|---|---|---|
| Omit pairing after rule creation | `tests/integration/test_web_pair_after_rules.py::test_action_pairs_waiting_transfer[rule-add]` | pair found | pair absent |
| Omit pairing after bulk category clear | `tests/integration/test_web_pair_after_rules.py::test_action_pairs_waiting_transfer[bulk-clear]` | pair found | pair absent |
| Omit pairing after alias deletion | `tests/integration/test_web_pair_after_rules.py::test_action_pairs_waiting_transfer[alias-delete]` | pair found | pair absent |

No independent probe is specified: the given behavioral matrix, coder tests, and existing suite cover the required paths.

## 5. Scope and report

No migration, dependency, matching rule, MCP write capability, or later-phase feature is added. The progress entry must use the required format and list real deviations. Write `docs/reviews/phase-47a-categorize-and-pair.md` as the sole review artifact, with the verdict block and findings in the exact form in `docs/phase-conventions.md`.
