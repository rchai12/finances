# Verify Phase 20a: the household password and the lockout

Spec: `docs/phases/phase-20a-password-and-lockout.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added the household password: a pure module for the password rule, scrypt hashing, and the lockout schedule; a Keychain store with the lockout's state; `fin web password` and `fin web unlock`; and `fin web serve` refusing to start without a password. Nothing on the web changed. A diff to one earlier test and three test files were given.

These are correct and must not be reported: the lockout's state kept in any text form in its Keychain item, as long as a restart keeps it; the salt from `os.urandom` or `secrets.token_bytes`; the CLI prompting with `typer.prompt(hide_input=True)` and its `confirmation_prompt`.

## 1. Gates

N is `3847` when Phase 30d was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 35 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_login_rules.py tests/integration/test_web_login_store.py tests/e2e/test_cli_web_password.py --no-cov` | exactly `35 passed` |
| `.venv/bin/python -m pytest tests/unit/test_login_rules.py -o addopts="" --import-mode=importlib --cov=finances.domain.login --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.login --cov=finances.web.login --cov=finances.cli.web --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | only `tests/e2e/test_cli_web.py` |
| `git diff --stat HEAD -- src/finances/web/routes src/finances/web/templates src/finances/web/app.py` | no output |

This search must print nothing:

- `git grep -n "logging\|print(\|logger" -- src/finances/domain/login.py src/finances/web/login.py`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, `src/finances/cli/web.py`, the two new modules, `tests/e2e/test_cli_web.py`, and four new test files.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gates 2 and 3 | pass |
| R2 | gate 2 (`test_the_lockout_schedule`) | passes |
| R3 | gate 2 (`test_the_first_password_and_a_change`, `test_a_short_password_stores_nothing`); the coder's salt case | pass |
| R4 | gate 2 (`test_the_lockout`); the coder's exact-end case | pass |
| R5 | gate 2 (`test_unlock_needs_the_password`) | passes |
| R6 | gate 7; the coder's Keychain-failure case; read both modules | nothing echoes a secret |
| R7 | gate 2 (`test_a_change_needs_the_current_password`); the coder's first-password case | pass |
| R8 | gate 2 (`test_unlock`, `test_unlock_refused`) | pass |
| R9 | gate 2 (`test_serve_needs_a_password`); `tests/e2e/test_cli_web.py` | pass |
| R10 | gate 5 | only that file |

## 4. Probe

None. Look once in the terminal on the Mac: run `fin web password` twice (the second time it asks for the current password), then `fin web serve` starts; delete the `finances-web` items in Keychain Access and `fin web serve` refuses. Leave no test password in the owner's Keychain.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `lock_for`: every third failure from 10 | given `test_the_lockout_schedule` (13) | 3 days | 1 day, or None |
| 2. `attempt`: tries during a lock counted | given `test_the_lockout` (three tries while locked) | the 1-day lock at the tenth try after | at the first try after the hour |
| 3. `attempt`: a right password during a lock accepted | given `test_the_lockout` (59 minutes) | refused, locked | `Attempt(True, None)` |
| 4. `attempt`: the count not reset by a right password | given `test_the_lockout` (four wrong after the right one) | no lock | a lock at the next failure |
| 5. `set_password`: the current password not needed for a change | given `test_the_first_password_and_a_change` (None) | refused | changed |
| 6. `set_password`: the session key kept | given `test_the_first_password_and_a_change` | a new key | the same key |
| 7. `unlock`: no password needed | given `test_unlock_needs_the_password` (`wrong`) | refused, still locked | unlocked |
| 8. `verify_password`: raises on unreadable text | given `test_verifying` (`zz` salt) | False | an error |
| 9. `serve`: the check after printing the address | given `test_serve_needs_a_password` | empty stdout | the address printed |

## 6. Out of scope

Each must be absent: any change under `src/finances/web/` but `login.py`; a password per person or in a setting; logins in the audit trail.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
