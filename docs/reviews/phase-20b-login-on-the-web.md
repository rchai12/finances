# Review: Phase 20b

- Verdict: PASS
- Passed: 3920
- Findings: 0
- Approved deviations: gate does not slide the cookie on `/logout`; extras live in `tests/unit/test_session.py` because 20a already shipped `test_web_login_more.py`; a Keychain error from `has_password()` is treated as no password, and 503 is only for `session_key()`
- For the architect: 20c should not name `tests/integration/test_web_login_more.py` (20a owns it); a broken Keychain on `has_password()` currently lets the site through so earlier SimpleFIN tests still pass

## Findings

None

Parts that needed a repair: the gate first answered 503 whenever `has_password()` raised, which failed four earlier SimpleFIN Keychain tests and the module-scoped form-length check (no `fin_csrf` cookie). The repair treats that error as no password and keeps 503 for `session_key()` only.

Built beyond the spec: none (the extra tests are the spec's "Tests to write", plus the `has_password()` Keychain case the repair needs)

## Gates

- `scripts/check.py`: `3920 passed`, last line `All checks passed.` (N + 14 = 3901; extras from `test_session.py` and the three new route rows in `test_web_split.py`)
- Given tests: `14 passed`
- Coverage of `finances.web.session`, `finances.web.routes.login`, `finances.views.login`: `Required test coverage of 100% reached. Total coverage: 100.00%`
- `git diff --stat HEAD -- tests`: only `tests/unit/test_web_split.py`
- `git grep -n "session_key()\|has_password()" -- src/finances/web/routes` with `--untracked` lists only `src/finances/web/routes/login.py` (lines 22, 36, 41)
- Given `tests/integration/test_web_login.py` and `login.html` match the spec blocks; `layout.html` has Log out before Sync now
- `git status --short` lists `docs/progress.md`, `src/finances/web/app.py`, the two templates, the three new modules, `tests/unit/test_web_split.py`, and two new test files (`test_web_login.py`, `test_session.py`)

## Requirement checklist

- R1: gate 2 (`test_the_idle_and_the_longest_time`); `test_make_cookie_has_three_signed_parts`, `test_read_cookie_refuses_a_bad_value`, `test_read_cookie_accepts_the_idle_and_longest_edges`
- R2: gate 2 (`test_only_this_sites_pages`); `test_safe_next`
- R3: gate 2 (`test_no_password_means_no_login`, `test_a_page_needs_the_login`, `test_a_new_password_ends_every_session`); `test_head_without_a_session_is_sent_to_the_login`, `test_a_keychain_error_on_session_key_is_503`
- R4: gate 2 (`test_no_password_means_no_login`)
- R5: gate 2 (`test_logging_in_returns_to_the_page`, `test_a_wrong_password`, `test_the_lock_says_when_it_ends`, `test_a_login_without_the_form_token`)
- R6: gate 2 (`test_logging_out`); `test_login_and_static_need_no_session_and_logout_is_post`
- R7: gate 2 (`test_the_lock_says_when_it_ends`); `test_lock_text_uses_london_local_time`
- R8: gate 2 (`test_the_menu_logs_out_before_sync_now`); `tests/integration/test_web_nav_sync.py` in gate 1
- R9: gate 4 (only `tests/unit/test_web_split.py`)

## Tests to write

- `make_cookie` / `read_cookie` refusals: `test_make_cookie_has_three_signed_parts`, `test_read_cookie_refuses_a_bad_value`
- idle and longest edges: `test_read_cookie_accepts_the_idle_and_longest_edges`
- `safe_next` of `/a?b=c`, `/`, `//x`, `/\x`, `x`, and `""`: `test_safe_next`
- `lock_text` with `TZ=Europe/London`: `test_lock_text_uses_london_local_time`
- HEAD without a session: `test_head_without_a_session_is_sent_to_the_login`
- `/login` and `/static/charts.js` without a session; `GET /logout` is 405: `test_login_and_static_need_no_session_and_logout_is_post`
- Keychain error on `session_key` is 503: `test_a_keychain_error_on_session_key_is_503`
- cookie from before a password change refused: `test_a_cookie_from_before_a_password_change_is_refused`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy under `/tmp/fin-20b-spots/` (not git checkout), with `__pycache__` cleared. `SPOT_FAILURES 0`.

1. `gate` the cookie not set again: `test_the_idle_and_the_longest_time` failed
2. `read_cookie` idle measured from the issued time: `test_the_idle_and_the_longest_time` failed
3. `read_cookie` no longest limit: `test_the_idle_and_the_longest_time` failed
4. `safe_next` `//` allowed: `test_only_this_sites_pages` failed
5. `gate` the query left out of `next`: `test_a_page_needs_the_login` failed
6. `gate` a fixed key kept from start-up: `test_a_new_password_ends_every_session` failed
7. `lock_text` UTC, not local time: `test_the_lock_says_when_it_ends` failed
8. `POST /login` checked without `attempt`: `test_the_lock_says_when_it_ends` failed
9. `gate` `/static/` behind the login: `test_login_and_static_need_no_session_and_logout_is_post` failed (`follow_redirects=False`; the given test follows redirects)

## Probe

None. The browser walk in the guide was not run (it would write to the owner's Keychain).

## Out of scope

Absent: the `Secure` flag; a host check for another name; `fin doctor` changes; asking for the password again; a remembered device; logins in the audit trail; changes to 20a's store or commands.

## Progress log

`docs/progress.md` has the Phase 20b entry in the required form. The three deviations are real, justified, and inside the spec's Scope.
