# Review: Phase 16l

- Verdict: PASS
- Passed: 3049
- Findings: 0
- Approved deviations: None
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `3049 passed`, `All checks passed.` (N + 16 = 3049)
- Given tests: `16 passed`
- Forms, sync setup, and ahead: `141 passed`
- `git diff --stat HEAD -- src`: only `layout.html` and `app.css`
- Given files match the spec blocks (`test_web_nav_sync.py`, the four given diffs)

## Requirement checklist

- R1: `test_every_page_ends_its_menu_with_the_button`; `test_the_button_sits_at_the_right_of_the_menu`
- R2: `test_every_account_and_what_is_expected`; forms and sync-setup suites still pass
- R3: `test_pressing_it_on_another_page_runs_a_sync`; `test_the_not_migrated_page_has_it_and_pressing_it_says_so`

## Probe

None, as the guide says. One browser look on `fin web serve --port 18765` with a temporary `FIN_DATA_DIR`: the button sat at the right end of the Reports menu; pressing it opened `/sync/run` with `No mapped accounts.`

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. Drop the hidden `csrf` field from the menu's form: `BUTTON.findall` is `[]`.
2. Put the form before the menu's links: the menu ends with the Backups link, not `</form>`.
3. Undo the reader change in `tests/support.py`: `forms[0]` is the menu's csrf field.

## Out of scope

Absent: a new route; a change to `routes/sync.py`; JavaScript; a redirect after the sync.
