# Review: Phase 42

- Verdict: PASS
- Passed: 4160
- Findings: 0
- Approved deviations: extra tests for the spec's extra cases and a form without the token so the new route's CSRF branch stays at 100%
- For the architect: None

## Findings

None

Parts that needed a repair: none.

Built beyond the spec: extra tests for `list_open_advice` order and limit, `dismiss_advice`'s stamp and a refusal that changes nothing, MCP `dismissed_at` after a dismissal, `fin review list` with a proposal and a note, History unchanged, Insights `month=May`, and a form without the token.

## Gates

- `scripts/check.py --first migrations,core,mcp,cli,web`: last line `All checks passed.`; summary lists `tests (migrations,core,mcp,cli,web): passed` then `tests: passed`; 4160 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table
- Given tests: `16 passed`
- Coverage include report: `TOTAL 1068 0 138 0 100%`
- `git diff --stat HEAD -- tests`: only the five files of the given diff
- `git grep -n "dismiss" -- src/finances/mcp_server`: the description and the two `dismissed_at` keys

`git status --short` lists the spec's Scope paths, this review, and local `.vscode/` (not part of the phase). Given tests, migration, templates, and the five-file diff match the spec.

## Requirement checklist

- R1: gate 2 (`test_migration_0023.py`); gate 1 (the migration-against-ORM tests)
- R2: gate 2 (the dismiss and Insights tests); `test_open_notes_skip_dismissed_ones_and_honour_limit`; `test_dismiss_advice_stamps_now_and_a_refusal_changes_nothing`
- R3: gate 2 (`test_dismissing_on_insights_returns_to_the_month`, the Review table)
- R4: gate 2 (the five CLI tests); `test_the_list_shows_proposals_then_notes`
- R5: gate 2 (the web tests); gate 1 (`test_web_split.py`, the two Review page tests)
- R6: gate 1 (`test_mcp_proposals.py`, `test_mcp_more.py`); gate 5; `test_list_advice_shows_when_a_note_was_dismissed`
- R7: gate 4; only those five files in `git diff --stat HEAD -- tests`

## Tests to write

- `list_open_advice` leaves out a dismissed note, newest first when two share a time, honours `limit`: `test_open_notes_skip_dismissed_ones_and_honour_limit`
- `dismiss_advice` stamps `advice._now`, a refused one changes nothing: `test_dismiss_advice_stamps_now_and_a_refusal_changes_nothing`
- MCP `list_advice` after a dismissal: `test_list_advice_shows_when_a_note_was_dismissed`
- `fin review list` with a proposal and a note: `test_the_list_shows_proposals_then_notes`
- dismissing records nothing in History: `test_dismissing_a_note_is_not_in_history`
- Insights `month=May` 400, no block: `test_a_refused_month_shows_no_notes_block`

## Spot checks

Each deciding test failed under the named change. Restored from `/tmp/fin-42-spots/`, not `git checkout`. SPOT_FAILURES 0.

| Change | Deciding test | Result |
|---|---|---|
| 1. `list_open_advice`: dismissed notes kept | `test_dismissing_on_insights_returns_to_the_month` | failed |
| 2. `dismiss_advice`: a second dismissal allowed | `test_a_refused_dismissal` (`1, 1`) | failed |
| 3. the route: `back` ignored | `test_dismissing_on_insights_returns_to_the_month` | failed |
| 4. the route: the month not checked | `test_a_month_that_is_not_one_is_left_out` (`May`) | failed |
| 5. the route: `id` not checked | `test_a_note_that_is_not_there` (`x`, empty) | failed |
| 6. `fin review list`: `Notes:` printed with no notes | `test_with_no_notes_the_list_is_as_before` | failed |
| 7. `advice_rows`: the state left empty | `test_dismissing_on_insights_returns_to_the_month` (the Review table) | failed |

## Out of scope

Absent: undoing a dismissal; an MCP tool that dismisses; notes in `fin insights` or on the dashboard; a History record for a dismissal.

## Probe

Temporary `FIN_DATA_DIR=/tmp/fin-42-probe/data`, in-memory keyring, TestClient on `127.0.0.1:8765`. Two notes, Insights showed both; dismissing one redirected to the same month with `Note dismissed.` and one note left; Review showed the other marked `dismissed` with no button. Script deleted afterwards. FAILURES 0.
