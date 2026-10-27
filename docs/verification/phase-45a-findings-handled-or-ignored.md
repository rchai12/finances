# Verify Phase 45a: findings a person handled or ignored

Spec: `docs/phases/phase-45a-findings-handled-or-ignored.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a `finding_statuses` table and let a person mark a finding handled (that month) or ignored (every month), or reopen it, from `fin findings` and the Insights page. Findings with a status left the open list, the dashboard, and the savings total, and show under Handled or ignored; each change is recorded in History. A migration, a template diff, a diff to `tests/support.py` and five earlier test files, and four test files were given.

These are correct and must not be reported: a shared private helper for the month option between `cli/reports.py` and `cli/findings.py`; a private helper in `routes/reports.py` that renders the refusal page; `get_insights` listing only open findings (45b adds the statuses).

## 1. Gates

N is `4218` when Phase 44b was the last phase built. Sections: migrations, core, cli, web.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first migrations,core,cli,web` | last line `All checks passed.`; the summary lists `tests (migrations,core,cli,web): passed`; at least N + 37 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table |
| `.venv/bin/python -m pytest tests/integration/test_migration_0025.py tests/unit/test_finding_rules.py tests/e2e/test_cli_findings.py tests/integration/test_web_findings.py --no-cov` | exactly `37 passed` |
| `.venv/bin/python -m coverage report --include="*/finances/domain/findings.py,*/finances/domain/audit.py,*/finances/db/orm.py,*/finances/db/repositories/findings.py,*/finances/analysis/insights.py,*/finances/views/insights.py,*/finances/cli/findings.py,*/finances/cli/reports.py,*/finances/cli/main.py,*/finances/web/routes/reports.py,*/finances/web/render.py" --fail-under=100` | exit 0, `TOTAL` at `100%` |
| `git diff --stat HEAD -- tests` | `tests/support.py` and the five files of the given diff, no other |
| `git grep -n "^from finances\.\(db\|analysis\|views\|cli\|web\)" -- src/finances/domain/findings.py` | no output |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope (`domain/findings.py`, `repositories/findings.py`, `cli/findings.py`, and the migration new), the template, the six files of the given test diff, and five new test files. The migration, the template diff, the given test files, and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_migration_0025.py`) | pass |
| R2 | gate 2 (`test_finding_rules.py`); gate 5 | pass |
| R3 | gate 1 (`test_audit_rules.py`, `test_cli_audit.py`) | pass |
| R4 | gate 2 (`test_history_records_each_change`, the refusals); gate 1 (`test_repositories_split.py`); the coder's stored-month, reopen-month, order, and cut cases | pass |
| R5 | gate 2 (`test_handling_a_finding_moves_it_below`, `test_a_refusal`); the coder's dashboard and `get_insights` cases | pass |
| R6 | gate 2 (the `Handled or ignored` rows) | pass |
| R7 | gate 2 (`test_cli_findings.py`) | pass |
| R8 | gate 2 (`test_web_findings.py`); gate 1 (`test_web_insights.py`, `test_web_split.py`); the coder's empty-month case | pass |
| R9 | gate 4 | only those files |

## 4. Probe

None.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `status_of`: the first matching status wins | given `test_the_status_of_a_finding` (handled May, then ignored) | `ignored` | `handled` |
| 2. `status_of`: handled matched in any month | given `test_handled_holds_for_that_month_only` (June) | interest open | under Handled or ignored |
| 3. `set_finding_status`: an ignored status stored with its month | the coder's stored-month case | month None | `2026-05-01` |
| 4. `find_finding`: subject compared exactly | given `test_handling_a_finding_moves_it_below` (`dining`) | `Marked handled: spike for Dining in 2026-05.` | `no such finding: spike for dining in 2026-05` |
| 5. `reopen_finding`: only the month's handled row removed | given `test_reopening_a_finding` (ignored in May, reopened from June) | `Reopened: interest in 2026-06.` | `this finding is open` |
| 6. `split_findings`: the closed list in the statuses' order | given `test_splitting_keeps_the_order` | interest, then coffee | coffee, then interest |
| 7. `insights_report`: `findings` still holds every finding | given `test_handling_a_finding_moves_it_below` | `Findings: 4. Could save up to $55.44 a month.` | `Findings: 5. ...$195.44...` |
| 8. `set_finding_status`: no check for a status already set | given `test_a_finding_with_a_status_is_refused` (ignore, then handle) | `this finding is already ignored` | exit 0 |
| 9. no History record on reopen | given `test_history_records_each_change` | `finding_reopened` first | `finding_ignored` first |
| 10. the redirect's month from the form instead of the finding | the coder's empty-month case | `/insights?month=<this month>&notice=...` | `/insights?month=&notice=...` |

## 6. Out of scope

Each must be absent: a change to `mcp_server`; buttons on the dashboard; `fin findings list`; a status on a merchant stat or a recurring charge.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
