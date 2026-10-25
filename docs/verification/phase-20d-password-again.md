# Verify Phase 20d: the password again for the sensitive actions

Spec: `docs/phases/phase-20d-password-again.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder made four actions ask for the household password again: restoring and deleting a backup, and linking and unlinking SimpleFIN, through one `recheck` that shares the login's lockout; unlinking gained a confirmation page. A template diff (one new template), a diff to one earlier test, and one test file were given.

These are correct and must not be reported: `reauth` computed by a small shared helper; the unlink page rendered by a private function used by the GET and the 400; the order of the form token and the schema check, as long as both come before the password.

## 1. Gates

N is `3937` when Phase 20c was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 7 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_recheck.py --no-cov` | exactly `7 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web.session --cov=finances.web.routes.backups --cov=finances.web.routes.sync --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | only `tests/unit/test_web_split.py` |
| `git diff --stat HEAD -- src/finances/cli` | no output (the terminal is unchanged) |

This search must list only `src/finances/web/routes/login.py`:

- `git grep -n "attempt(" -- src/finances/web/routes`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files and templates of the spec's Scope (one new), `tests/unit/test_web_split.py`, and two new test files. The templates and the test diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_wrong_passwords_here_lock_the_login`); the coder's `recheck` cases | pass |
| R2 | gate 2 (`test_deleting_needs_the_password`, `test_restoring_needs_the_password_before_the_name`); the coder's order case | pass |
| R3 | gate 2 (`test_linking_needs_the_password`); the coder's empty-Keychain case | pass |
| R4 | gate 2 (`test_unlinking_has_a_page_and_needs_the_password`); the coder's bad-name case | pass |
| R5 | gate 2 (`test_the_boxes_with_a_password`, `test_no_password_box_without_a_password`) | pass |
| R6 | gate 4 | only that file |

## 4. Probe

None. Look once in a real browser with a password set on a temporary `FIN_DATA_DIR`: open a backup's Delete page, type a wrong password, see the error and the backup still listed; type the right one and see it gone.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `recheck`: `check_password` (no lockout) | given `test_wrong_passwords_here_lock_the_login` | the login locked | the login works |
| 2. `delete`: no check | given `test_deleting_needs_the_password` (wrong) | 400, the file kept | 303, deleted |
| 3. `restore`: the typed name checked before the password | coder: wrong password and wrong name | `wrong password` | the name's message |
| 4. `link`: the token claimed before the password | given `test_linking_needs_the_password` (wrong, token `x`) | `wrong password` | `setup token is not valid` |
| 5. `link`: the token shown back | given `test_linking_needs_the_password` | no `value="x"` | the token in the page |
| 6. `sync.html`'s Unlink still a POST | given `test_unlinking_has_a_page_and_needs_the_password` | `get` | `post` |
| 7. `unlink`: no check | given `test_unlinking_has_a_page_and_needs_the_password` (wrong) | 400, the access kept | 303, removed |
| 8. `reauth` always true | given `test_no_password_box_without_a_password` | no box | a box |

## 6. Out of scope

Each must be absent: a password asked by the terminal; a remembered password; any other action asking; changes to 20a's store, 20b's gate, or 20c's rules.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
