# Verify Phase 20b: the login on the web

Spec: `docs/phases/phase-20b-login-on-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder put the site behind 20a's password: a signed session cookie, a gate in front of every page, a `login` router with the login and logout routes, the lock's words in a view, and a Log out button in the menu (given). A template diff, a diff to one earlier test, and one test file were given.

These are correct and must not be reported: the gate written as a function or a small class, as long as `create_app` adds it with `api.middleware("http")`; `read_cookie` splitting with `str.split` or `partition`; `lock_text` building the day with `str(local.day)` or a format code without a leading zero.

## 1. Gates

N is `3887` when Phase 20a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 14 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_login.py --no-cov` | exactly `14 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web.session --cov=finances.web.routes.login --cov=finances.views.login --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | only `tests/unit/test_web_split.py` |

This search must list only `src/finances/web/routes/login.py`:

- `git grep -n "session_key()\|has_password()" -- src/finances/web/routes`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, `src/finances/web/app.py`, the given templates (one new), the three new modules, `tests/unit/test_web_split.py`, and three new test files. The templates and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_the_idle_and_the_longest_time`); the coder's cookie tests | pass |
| R2 | gate 2 (`test_only_this_sites_pages`); the coder's `safe_next` cases | pass |
| R3 | gate 2 (`test_no_password_means_no_login`, `test_a_page_needs_the_login`, `test_a_new_password_ends_every_session`); the coder's HEAD and 503 cases | pass |
| R4 | gate 2 (`test_no_password_means_no_login`) | passes |
| R5 | gate 2 (`test_logging_in_returns_to_the_page`, `test_a_wrong_password`, `test_the_lock_says_when_it_ends`, `test_a_login_without_the_form_token`) | pass |
| R6 | gate 2 (`test_logging_out`); the coder's 405 case | pass |
| R7 | gate 2 (`test_the_lock_says_when_it_ends`); the coder's London case | pass |
| R8 | gate 2 (`test_the_menu_logs_out_before_sync_now`); `tests/integration/test_web_nav_sync.py` in gate 1 | pass |
| R9 | gate 4 | only that file |

## 4. Probe

None. Look once in a real browser (16c's lesson: test clients do not send what browsers send): with a password set on a temporary `FIN_DATA_DIR`, `fin web serve`, open the site, log in, follow a few pages, log out; then wait 31 minutes, or set the clock forward, and see the login again.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `gate`: the cookie not set again (no sliding) | given `test_the_idle_and_the_longest_time` (59 minutes) | 200 | 303 |
| 2. `read_cookie`: idle measured from the issued time | given `test_the_idle_and_the_longest_time` (59 minutes) | 200 | 303 |
| 3. `read_cookie`: no longest limit | given `test_the_idle_and_the_longest_time` (a day and 20 minutes) | 303 | 200 |
| 4. `safe_next`: `//` allowed | given `test_only_this_sites_pages` (`//evil.example/x`) | `/` | `//evil.example/x` |
| 5. `gate`: the query left out of `next` | given `test_a_page_needs_the_login` | `/login?next=/reports%3Fmonth%3D2026-05` | `/login?next=/reports` |
| 6. `gate`: a fixed key kept from start-up | given `test_a_new_password_ends_every_session` | 303 | 200 |
| 7. `lock_text`: UTC, not local time | given `test_the_lock_says_when_it_ends` (Chicago) | `15:30` | `20:30` |
| 8. `POST /login`: checked without `attempt` | given `test_the_lock_says_when_it_ends` (the right password while locked) | 400, locked | 303 |
| 9. `gate`: `/static/` behind the login | given `test_a_page_needs_the_login` (`/static/app.css`) | 200 | 303 |

## 6. Out of scope

Each must be absent: the `Secure` flag; a host check for another name; `fin doctor` changes; asking for the password again; a remembered device; logins in the audit trail; changes to 20a's store or commands.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
