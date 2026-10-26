# Verify Phase 42: the agent's notes beside the findings

Spec: `docs/phases/phase-42-notes-beside-the-findings.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder let a person dismiss the agent's notes, showed the notes not yet dismissed on the Insights page, listed the notes in `fin review list`, and gave MCP's notes their `dismissed_at`. A migration, a template diff, a diff to five earlier test files, and three test files were given.

These are correct and must not be reported: the redirect worked out by a small private helper; the month checked with a regular expression or by parsing; the notes table printed by `print_rows` like every other CLI table.

## 1. Gates

N is `4136` when Phase 41c was the last phase built. Sections: migrations, core, mcp, cli, web.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first migrations,core,mcp,cli,web` | last line `All checks passed.`; the summary lists `tests (migrations,core,mcp,cli,web): passed`; at least N + 16 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table |
| `.venv/bin/python -m pytest tests/integration/test_migration_0023.py tests/e2e/test_cli_notes.py tests/integration/test_web_notes.py --no-cov` | exactly `16 passed` |
| `.venv/bin/python -m coverage report --include="*/finances/db/orm.py,*/finances/domain/proposals.py,*/finances/db/repositories/advice.py,*/finances/views/review.py,*/finances/cli/review.py,*/finances/web/routes/review.py,*/finances/web/routes/reports.py,*/finances/web/render.py,*/finances/mcp_server/tools.py,*/finances/mcp_server/server.py" --fail-under=100` | exit 0, `TOTAL` at `100%` |
| `git diff --stat HEAD -- tests` | only the five files of the given diff |
| `git grep -n "dismiss" -- src/finances/mcp_server` | only the description and the `dismissed_at` keys |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files and templates of the spec's Scope (`advice.py` and the migration new), the five files of the given diff, and four new test files. The migration, the templates, the given test files, and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_migration_0023.py`); gate 1 (the migration-against-ORM tests) | pass |
| R2 | gate 2 (the dismiss and Insights tests); the coder's ordering, limit, and stamp cases | pass |
| R3 | gate 2 (`test_dismissing_on_insights_returns_to_the_month`, the Review table) | pass |
| R4 | gate 2 (the five CLI tests); the coder's proposals-and-notes case | pass |
| R5 | gate 2 (the web tests); gate 1 (`test_web_split.py`, the two Review page tests) | pass |
| R6 | gate 1 (`test_mcp_proposals.py`, `test_mcp_more.py`); gate 5; the coder's `dismissed_at` case | pass |
| R7 | gate 4 | only those files |

## 4. Probe

None. Look once on a temporary `FIN_DATA_DIR` with two notes: open Insights, dismiss one, see `Note dismissed.` on the same month and one note left; open Review and see the other marked `dismissed` without a button.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `list_open_advice`: dismissed notes kept | given `test_dismissing_on_insights_returns_to_the_month` | one note left | two |
| 2. `dismiss_advice`: a second dismissal allowed | given `test_a_refused_dismissal` (`1, 1`) | `note 1 is already dismissed` | `Dismissed note 1.` |
| 3. the route: `back` ignored | given `test_dismissing_on_insights_returns_to_the_month` | `/insights?month=2026-05&notice=note-dismissed` | `/review?…` |
| 4. the route: the month not checked | given `test_a_month_that_is_not_one_is_left_out` (`May`) | `/insights?notice=note-dismissed` | `month=May` kept |
| 5. the route: `id` not checked | given `test_a_note_that_is_not_there` (`x`, empty) | 400, `note not found` | a 500 |
| 6. `fin review list`: `Notes:` printed with no notes | given `test_with_no_notes_the_list_is_as_before` | `No open proposals.` alone | `Notes:` too |
| 7. `advice_rows`: the state left empty | given `test_dismissing_on_insights_returns_to_the_month` (the Review table) | `dismissed`, no button | `""`, `Dismiss` |

## 6. Out of scope

Each must be absent: undoing a dismissal; an MCP tool that dismisses; notes in `fin insights` or on the dashboard; a History record for a dismissal.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
