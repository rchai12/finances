# Review: Phase 20c

- Verdict: PASS
- Passed: 3937
- Findings: 0
- Approved deviations: `cookie_flags` is shared by the gate, the login, `_render`, and logout; `tests/conftest.py` installs a default MemoryKeyring at import (beyond the given `FIN_WEB_HOSTNAME` line) so a module-scoped client does not hit a leftover Broken backend
- For the architect: the given `Broken` class in `test_cli_doctor_web.py` is a KeyringBackend with priority 1; after that module is imported, a module-scoped client that runs before the per-test MemoryKeyring was getting 503 until conftest set a default empty store

## Findings

None

Parts that needed a repair: fail-closed made `tests/integration/test_text_limits.py`'s module-scoped `site` fixture get 503 on `GET /accounts` (no `fin_csrf` cookie) after e2e tests that define a Broken KeyringBackend. The repair is a default MemoryKeyring at conftest import, not a change to that earlier test.

Built beyond the spec: `cookie_flags`; the extra `test_post_login_with_a_broken_keychain` so `POST /login`'s Keychain branch is covered; the conftest default MemoryKeyring.

## Gates

- `scripts/check.py`: `3937 passed`, last line `All checks passed.` (N + 11 = 3931; extras from `test_web_tailscale_more.py`)
- Given tests: `11 passed`
- Coverage of `config`, `diagnostics`, `web.app`, `web.forms`, `web.render`, `web.routes.login`, `web.session`: `Required test coverage of 100% reached. Total coverage: 100.00%`
- `git diff --stat HEAD -- tests`: the six files of the given diff
- `bash -n scripts/install-web-service.sh scripts/uninstall-web-service.sh`: no output
- `git diff --stat HEAD -- docs/remote-access.md scripts/install-sync-schedule.sh`: no output
- `git grep -nF -e "0.0.0.0" -e 'host=""' -- src/finances ':!src/finances/web/static'`: no output
- Given test files and both scripts match the spec blocks; scripts are executable
- `docs/remote-access.md` is unchanged

`git status --short` also lists README, `.env.example`, `docs/README.md`, `docs/architecture.md`, and `docs/roadmap.md`. Those are not in this phase's Scope and were not edited for this implementation.

## Requirement checklist

- R1: gate 2 (`test_a_broken_keychain_closes_the_site`); `test_a_keychain_error_on_has_password_closes_the_site`; `test_post_login_with_a_broken_keychain`
- R2: gate 2 (`test_the_setting_is_a_host_name`); `test_a_hostname_with_a_dot_a_space_or_one_label_is_refused`
- R3: gate 2 (`test_the_name_and_no_other`, `test_the_name_is_served_only_when_set`)
- R4: gate 2 (`test_the_form_origin`); `test_the_tailscale_origin_is_refused_with_no_name`
- R5: gate 2 (`test_cookies_are_secure_over_tailscale`, `test_cookies_on_this_mac_are_not_secure`, `test_a_request_forwarded_over_https`)
- R6: gate 2 (`tests/e2e/test_cli_doctor_web.py`); `test_there_are_eight_checks_in_order`
- R7: gate 5; scripts equal the spec's
- R8: gate 4 (the six files; conftest has one extra line, the default MemoryKeyring)

## Tests to write

- `over_https` for the name with a port, another name, `X-Forwarded-Proto: http`, and no header: `test_over_https_for_the_name_with_a_port_another_name_and_the_header`
- a hostname with a leading dot, a space, or one label refused; `mac-studio.tail1234.ts.net` kept: `test_a_hostname_with_a_dot_a_space_or_one_label_is_refused`
- with no name set, origin `https://mac.tail1234.ts.net` is `Bad origin`: `test_the_tailscale_origin_is_refused_with_no_name`
- logout through Tailscale: `test_logout_through_tailscale_ends_the_session`
- `fin doctor` on another `FIN_WEB_PORT`: `test_doctor_shows_another_web_port`

## Spot checks

Each deciding test failed under the named mutation, then the file was restored from a unique-named copy under `/tmp/fin-20c-spots/` (not git checkout), with `__pycache__` cleared. `SPOT_FAILURES 0`.

1. `gate` a Keychain error on `has_password` lets the request through: `test_a_broken_keychain_closes_the_site` failed
2. `GET /login` no Keychain check: `test_a_broken_keychain_closes_the_site` failed
3. `_Guard` `<name>:443` refused: `test_the_name_and_no_other` failed
4. `configure_origins` the name without `https://`: `test_the_form_origin` failed
5. `_render` the form-token cookie never `Secure`: `test_cookies_are_secure_over_tailscale` failed
6. the gate re-issued session cookie without `Secure`: `test_cookies_are_secure_over_tailscale` failed
7. `over_https` `X-Forwarded-Proto` ignored: `test_a_request_forwarded_over_https` failed
8. `Settings` the name not lower-cased: `test_the_setting_is_a_host_name` failed
9. `run_checks` a missing password reported but passing: `test_doctor_without_a_password` failed

## Probe

None in this repository. The runbook walk on the Mac Studio was not run.

## Out of scope

Absent: a Tailscale identity check; `Strict-Transport-Security`; a bind address other than 127.0.0.1; running Tailscale from the app; asking for the password again; changes to `docs/remote-access.md` or the given scripts.

## Progress log

`docs/progress.md` has the Phase 20c entry in the required form. The two deviations are real, justified, and inside the spec's Scope (conftest is listed; the extra MemoryKeyring line is the repair).
