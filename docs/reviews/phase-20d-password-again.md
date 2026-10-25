# Review: Phase 20d

- Verdict: PASS
- Passed: 3952
- Findings: 0
- Approved deviations: `_sync_page` also lists SimpleFIN names from a Keychain backend that exposes `passwords`, so a Keychain-only link has an Unlink GET form; `GET /sync/unlink` without a `link` query answers 405 so the earlier form-path GET test still passes
- For the architect: the given unlink test saves access without a mapping, so Unlink on `/sync` only appears here because MemoryKeyring exposes `passwords`; `GET /sync/unlink` with no query is 405 only to keep `test_a_form_path_does_nothing_on_get`

## Findings

None

Parts that needed a repair: `GET /sync/unlink` made `test_a_form_path_does_nothing_on_get[/sync/unlink]` fail (it expected 405). The repair answers 405 when the `link` query is missing, not a change to that earlier test. The given unlink test needed a Keychain-only name on `/sync`; `_keychain_links` reads MemoryKeyring's `passwords`.

Built beyond the spec: extra tests for a Keychain error from `recheck`, a missing backup with a wrong password, and a Keychain backend that does not list names; `_keychain_links`.

## Gates

- `scripts/check.py`: `3952 passed`, last line `All checks passed.` (N + 7 = 3944; extras from `test_web_recheck_more.py`)
- Given tests: `7 passed`
- Coverage of `finances.web.session`, `finances.web.routes.backups`, `finances.web.routes.sync`: `Required test coverage of 100% reached. Total coverage: 100.00%`
- `git diff --stat HEAD -- tests`: only `tests/unit/test_web_split.py`
- `git diff --stat HEAD -- src/finances/cli`: no output
- `git grep -n "attempt(" -- src/finances/web/routes`: only `src/finances/web/routes/login.py:48`
- Given `tests/integration/test_web_recheck.py` and the three templates match the spec blocks

`git status --short` lists `docs/progress.md`, the source files and templates of the spec's Scope (one new), `tests/unit/test_web_split.py`, and two new test files.

## Requirement checklist

- R1: gate 2 (`test_wrong_passwords_here_lock_the_login`); `test_recheck_with_no_password_or_while_locked`
- R2: gate 2 (`test_deleting_needs_the_password`, `test_restoring_needs_the_password_before_the_name`); `test_restore_checks_the_password_before_the_typed_name`
- R3: gate 2 (`test_linking_needs_the_password`); `test_a_wrong_password_on_link_leaves_the_keychain_empty`
- R4: gate 2 (`test_unlinking_has_a_page_and_needs_the_password`); `test_unlink_refuses_a_bad_link_name`
- R5: gate 2 (`test_the_boxes_with_a_password`, `test_no_password_box_without_a_password`)
- R6: gate 4; only `tests/unit/test_web_split.py`

## Tests to write

- `recheck` with no password set gives None for any text; while locked it gives the lock's text even for the right password: `test_recheck_with_no_password_or_while_locked`
- a restore with a wrong password and a wrong typed name gives `wrong password`; with the right password and a wrong name, the name's message: `test_restore_checks_the_password_before_the_typed_name`
- `GET /sync/unlink?link=Bad` answers 400 on the SimpleFIN page with the link-name message: `test_unlink_refuses_a_bad_link_name`
- with no password set, posting each of the four forms without a `password` field works as before: `test_the_four_forms_work_without_a_password`
- a wrong password on the link form leaves the Keychain empty: `test_a_wrong_password_on_link_leaves_the_keychain_empty`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy under `/tmp/fin-20d-spots/` (not git checkout), with `__pycache__` cleared. `SPOT_FAILURES 0`.

1. `recheck` `check_password` (no lockout): `test_wrong_passwords_here_lock_the_login` failed
2. `delete` no check: `test_deleting_needs_the_password` failed
3. `restore` the typed name checked before the password: `test_restore_checks_the_password_before_the_typed_name` failed
4. `link` the token claimed before the password: `test_linking_needs_the_password` failed
5. `link` the token shown back: `test_linking_needs_the_password` failed
6. `sync.html`'s Unlink still a POST: `test_unlinking_has_a_page_and_needs_the_password` failed
7. `unlink` no check: `test_unlinking_has_a_page_and_needs_the_password` failed
8. `reauth` always true: `test_no_password_box_without_a_password` failed

## Probe

None. The browser walk in the guide was not run (it would write to the owner's Keychain).

## Out of scope

Absent: a password asked by the terminal; a remembered password; any other action asking; changes to 20a's store, 20b's gate, or 20c's rules.

## Progress log

`docs/progress.md` has the Phase 20d entry in the required form. The two deviations are real, justified, and inside the spec's Scope (`session.py` and `sync.py`).
