# Review: Phase 20a

- Verdict: PASS
- Passed: 3887
- Findings: 0
- Approved deviations: lockout Keychain text is `count` or `count <ISO datetime>` (the spec left the form open; the guide allows any text form)
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none (the extra tests are the spec's "Tests to write")

## Gates

- `scripts/check.py`: `3887 passed`, `All checks passed.` (N + 35 = 3882; extra 5 from `test_web_login_more.py`)
- Given tests: `35 passed`
- Coverage of `domain.login` from the given unit file: `Required test coverage of 100% reached`
- Coverage of `domain.login`, `web.login`, `cli.web`: `Required test coverage of 100% reached`
- `git diff --stat HEAD -- tests`: only `tests/e2e/test_cli_web.py`
- `git diff --stat HEAD -- src/finances/web/routes src/finances/web/templates src/finances/web/app.py`: no output
- `git grep -n "logging\|print(\|logger" -- src/finances/domain/login.py src/finances/web/login.py` prints nothing
- Given test files and the `test_cli_web.py` diff match the spec blocks
- `git status --short` lists `docs/progress.md`, `src/finances/cli/web.py`, the two new modules, `tests/e2e/test_cli_web.py`, and four new test files

## Requirement checklist

- R1: gates 2 and 3 (`test_the_hash`, `test_verifying`, `test_a_new_password_that_is_kept`)
- R2: `test_the_lockout_schedule` (13)
- R3: `test_the_first_password_and_a_change`, `test_a_short_password_stores_nothing`, `test_the_stored_hash_uses_scrypt_and_a_new_salt_each_time`
- R4: `test_the_lockout`, `test_a_lock_that_ended_exactly_now_is_over`
- R5: `test_unlock_needs_the_password`
- R6: grep gate; `test_a_keychain_error`; neither module prints or returns a password or hash in an error
- R7: `test_a_change_needs_the_current_password`, `test_the_first_password_does_not_ask_for_a_current_one`
- R8: `test_unlock`, `test_unlock_refused`
- R9: `test_serve_needs_a_password`; `tests/e2e/test_cli_web.py` serving fixture sets a password
- R10: gate 5 (only `tests/e2e/test_cli_web.py`)

## Tests to write

- stored hash `scrypt$16384$8$1$` and different salts: `test_the_stored_hash_uses_scrypt_and_a_new_salt_each_time`
- `check_password` neither counts nor locks (10 wrong checks): `test_check_password_neither_counts_nor_locks`
- Keychain `KeyringError`: `test_a_keychain_error`
- a lock that ended exactly at `now`: `test_a_lock_that_ended_exactly_now_is_over` (`T0 + 1 hour`)
- `fin web password` with no password set does not ask for a current one: `test_the_first_password_does_not_ask_for_a_current_one`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy (not git checkout), with `__pycache__` cleared.

1. `lock_for` every third failure from 10: `test_the_lockout_schedule` failed (13 gave None)
2. `attempt` tries during a lock counted: `test_the_lockout` failed (1-day lock at the first try after the hour)
3. `attempt` a right password during a lock accepted: `test_the_lockout` failed (`Attempt(True, None)` at 59 minutes)
4. `attempt` the count not reset by a right password: `test_the_lockout` failed (a lock among the four wrong after the right one)
5. `set_password` the current password not needed for a change: `test_the_first_password_and_a_change` failed (`current=None` changed it)
6. `set_password` the session key kept: `test_the_first_password_and_a_change` failed (the same key)
7. `unlock` no password needed: `test_unlock_needs_the_password` failed (`wrong` unlocked)
8. `verify_password` raises on unreadable text: `test_verifying` failed (`zz` salt raised)
9. `serve` the check after printing the address: `test_serve_needs_a_password` failed (the address printed)

## Probe

None. The Mac Keychain walk in the guide was not run (it would write to the owner's Keychain).

## Out of scope

Absent: any change under `src/finances/web/` but `login.py`; a password per person or in a setting; logins in the audit trail.

## Progress log

`docs/progress.md` has the Phase 20a entry in the required form. The lockout text form is a choice the spec left open.
