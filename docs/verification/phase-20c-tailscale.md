# Verify Phase 20c: reaching the site through Tailscale

Spec: `docs/phases/phase-20c-tailscale.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder taught the site its Tailscale name (a checked setting, the host check, the form origins), marked cookies `Secure` for requests that arrive through Tailscale Serve, made the site fail closed when the Keychain cannot be read, and added three `fin doctor` checks. The keep-alive scripts, a diff to six earlier tests, and two test files were given; the runbook `docs/remote-access.md` is the architect's.

These are correct and must not be reported: `over_https` comparing the host without its port by `partition(":")` or `rsplit`; the `Secure` flag passed through a small helper shared by the gate, the login, and `_render`; the hostname check written with `re.fullmatch` in a Pydantic validator.

## 1. Gates

N is `3920` when Phase 20b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 11 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_tailscale.py tests/e2e/test_cli_doctor_web.py --no-cov` | exactly `11 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.config --cov=finances.diagnostics --cov=finances.web.app --cov=finances.web.forms --cov=finances.web.render --cov=finances.web.routes.login --cov=finances.web.session --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | the six files of the given diff |
| `bash -n scripts/install-web-service.sh scripts/uninstall-web-service.sh` | no output |
| `git diff --stat HEAD -- docs/remote-access.md scripts/install-sync-schedule.sh` | no output |

This search must print nothing:

- `git grep -nF -e "0.0.0.0" -e 'host=""' -- src/finances ':!src/finances/web/static'`

## 2. Scope paths

`git status --short` lists `docs/progress.md`, the source files of the spec's Scope, the two given scripts, the six earlier test files, and three new test files. The scripts and the diff equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_a_broken_keychain_closes_the_site`); `tests/unit/test_session.py` in gate 1 | pass |
| R2 | gate 2 (`test_the_setting_is_a_host_name`); the coder's refused names | pass |
| R3 | gate 2 (`test_the_name_and_no_other`, `test_the_name_is_served_only_when_set`) | pass |
| R4 | gate 2 (`test_the_form_origin`); the coder's no-name case | pass |
| R5 | gate 2 (`test_cookies_are_secure_over_tailscale`, `test_cookies_on_this_mac_are_not_secure`, `test_a_request_forwarded_over_https`) | pass |
| R6 | gate 2 (`test_cli_doctor_web.py`); `tests/unit/test_diagnostics.py` in gate 1 | pass |
| R7 | gate 5; the scripts equal the spec's | pass |
| R8 | gate 4 | only the six files |

## 4. Probe

None in this repository: Tailscale is set up on the Mac Studio by the owner with `docs/remote-access.md`. On a Mac with Tailscale, the owner's check is the runbook's step 6: `fin doctor` passes, the login page opens on a phone at the Tailscale name, and the browser shows `fin_session` as `Secure`.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the named function. The deciding test must fail under it; for a row whose test is the coder's, check that the test holds the deciding input.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `gate`: a Keychain error on `has_password` lets the request through (20b's deviation) | given `test_a_broken_keychain_closes_the_site` | 503 | 200 |
| 2. `GET /login`: no Keychain check | given `test_a_broken_keychain_closes_the_site` (`/login`) | 503 | 200 or 500 |
| 3. `_Guard`: `<name>:443` refused | given `test_the_name_and_no_other` | 200 | 400 |
| 4. `configure_origins`: the name without `https://` | given `test_the_form_origin` | 303 | 403 |
| 5. `_render`: the form-token cookie never `Secure` | given `test_cookies_are_secure_over_tailscale` | `Secure` | absent |
| 6. the gate: the re-issued session cookie without `Secure` | given `test_cookies_are_secure_over_tailscale` (the second page) | `Secure` | absent |
| 7. `over_https`: `X-Forwarded-Proto` ignored | given `test_a_request_forwarded_over_https` | `Secure` | absent |
| 8. `Settings`: the name not lower-cased | given `test_the_setting_is_a_host_name` | `mac.tail1234.ts.net` | `Mac.Tail1234.TS.NET` |
| 9. `run_checks`: a missing password reported but passing | given `test_doctor_without_a_password` | exit 1 | exit 0 |

## 6. Out of scope

Each must be absent: a Tailscale identity check; `Strict-Transport-Security`; a bind address other than 127.0.0.1; running Tailscale from the app; asking for the password again; changes to `docs/remote-access.md` or the given scripts.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
