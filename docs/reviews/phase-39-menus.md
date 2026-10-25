# Review: Phase 39

- Verdict: PASS
- Passed: 4028
- Findings: 0
- Approved deviations: Menu panel `box-shadow` uses `var(--bg)` instead of the given `rgba(0, 0, 0, .12)` so Phase 16m's colour-token test still passes
- For the architect: isolated `--cov=finances.db.repositories.proposals` with `-o addopts=""` makes Alembic raise `TypeError: 'InternalTraversal' object is not callable`; cover `render` and `proposals` through `--cov=finances`. The given `rgba()` shadow fails `test_every_colour_comes_from_a_token`

## Findings

None

Parts that needed a repair: `_review_count` first used `_reading()` and deadlocked on `_RESTORE_GATE` because some routes call `_render` while holding that lock; it now opens its own engine. The given `rgba()` shadow was replaced with `var(--bg)` so `test_every_colour_comes_from_a_token` still passes.

Built beyond the spec: extra tests for `count_open_proposals` at 0 then 1 (one accepted, one open), a 503 error page before migration with no count, the sixteen links in the Goal menus with Home and Review outside, and `/account?name=` marking Money.

## Gates

- `scripts/check.py`: `4028 passed`, last line `All checks passed.` (N + 14 = 4024)
- Given tests: `14 passed`
- Coverage of `finances.web.render` and `finances.db.repositories.proposals`: the spec command (`-o addopts=""` and those two `--cov=` modules) fails during Alembic with `TypeError: 'InternalTraversal' object is not callable`. `scripts/check.py` (`--cov=finances`) reached 100% on both modules (`render.py` 40/0/6, `proposals.py` 198/0/86)
- `git diff --stat HEAD -- tests`: only `tests/unit/test_repositories_split.py`
- `git grep -n "<script" -- src/finances/web/templates/layout.html`: no output
- Given `tests/integration/test_web_menus.py` matches the spec block
- Given `layout.html` matches the spec diff
- Given diff to `tests/unit/test_repositories_split.py` matches the spec
- Given `app.css` matches the spec diff except the approved `box-shadow` token

`git status --short` lists `docs/progress.md`, the source files, template, and stylesheet of the spec's Scope, `tests/unit/test_repositories_split.py`, two new test files, and this review. `.vscode/` is local editor config and is not part of the phase.

## Requirement checklist

- R1: gate 2 (`test_the_menus_and_the_top_links_in_order`, `test_the_menu_holding_the_page_is_marked`); `test_each_link_sits_in_the_menu_the_goal_names`
- R2: gate 1 (`test_repositories_split.py`); `test_count_open_proposals_is_zero_then_one_when_one_is_accepted`
- R3: gate 2 (`test_review_shows_how_many_proposals_wait`, `test_no_count_when_nothing_waits`, `test_no_count_on_the_login_page`, `test_a_page_shown_before_the_database_is_migrated_has_no_count`); `test_an_error_page_before_migration_has_no_count`
- R4: gate 4

## Tests to write

- `count_open_proposals` with none is 0, with one accepted and one open is 1: `test_count_open_proposals_is_zero_then_one_when_one_is_accepted`
- error page before migration has no count: `test_an_error_page_before_migration_has_no_count`
- sixteen links in the Goal menus, Home and Review outside: `test_each_link_sits_in_the_menu_the_goal_names`
- account page marks Money: `test_the_account_page_marks_money`

## Spot checks

Each deciding test failed under the named change. Restored from `/tmp/fin-39-spots/` copies, not `git checkout`. SPOT_FAILURES 0.

| Change | Deciding test | Result |
|---|---|---|
| 1. `count_open_proposals`: every status counted | `test_review_shows_how_many_proposals_wait` | failed (`/` showed 3) |
| 2. `_render`: `review_count` given to the review page only | the same test (`/`, `/accounts`) | failed (`/` had no count) |
| 3. `_render`: the login page counted | `test_no_count_on_the_login_page` | failed (count `2` on `/login`) |
| 4. `_render`: no schema check | `test_a_page_shown_before_the_database_is_migrated_has_no_count` | failed (query on unmigrated db) |

## Out of scope

Absent: JavaScript in any template; hover-only menus; a change to a page's own content or to a link's label; a count beside anything but Review.

## Probe

Temporary `FIN_DATA_DIR=/tmp/fin-39-browser` on `127.0.0.1:18771`. Opening Money then Plan closed Money (`name="menu"`). `/budgets` marks Plan (`class="menu current"`) and Budgets keeps `aria-current="page"`. At 390px width the bar wraps and System opens with SimpleFIN, Backups, and History.
