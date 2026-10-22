# Verify Phase 16l: a Sync now button in the menu

Spec: `docs/phases/phase-16l-sync-button-in-the-menu.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder applied a given diff: a Sync now form at the end of every page's menu posting to the existing `/sync/run`, one CSS rule, and three test page readers that leave the menu's form out. One test file was given; no Python under `src/` changes.

## 1. Gates

N is `3033` when Phase 14a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 16 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_nav_sync.py --no-cov` | exactly `16 passed` |
| `.venv/bin/python -m pytest tests/integration/test_web_forms.py tests/integration/test_web_sync_setup.py tests/integration/test_web_ahead.py --no-cov` | all passed |
| `git diff --stat HEAD -- src` | only `src/finances/web/templates/layout.html` and `src/finances/web/static/app.css` |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/web/static/app.css
 M src/finances/web/templates/layout.html
 M tests/integration/test_web_forms.py
 M tests/integration/test_web_sync_setup.py
 M tests/support.py
?? tests/integration/test_web_nav_sync.py
```

The diff of these paths (apart from `docs/progress.md`) equals the spec's given diff, and the test file equals its block.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R3 | gates 1 to 3 | pass |

## 4. Probe

None. One look in a real browser is worth it: with `fin web serve` on a temporary `FIN_DATA_DIR` (never the owner's `data/`), the button sits at the right end of the menu, and pressing it shows the Sync page with `No mapped accounts.`

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. Drop the hidden `csrf` field from the menu's form | `test_every_page_ends_its_menu_with_the_button` | the token | no match |
| 2. Put the form before the menu's links | the same, last assertion | the menu ends with `</form>` | it ends with a link |
| 3. Undo the reader change in `tests/support.py` | `test_web_ahead.py::test_every_account_and_what_is_expected` | `forms[0]` is the days form | the menu's form |

## 6. Out of scope

Each must be absent: a new route; a change to `routes/sync.py`; JavaScript; a redirect after the sync.
