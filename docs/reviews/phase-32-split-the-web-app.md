# Review: Phase 32

- Verdict: PASS
- Passed: 2911
- Findings: 0
- Approved deviations: shared helpers named `access`, `forms`, `helpers`, `render`; routers use `finances.web.app` at call time; `create_app` imports routers inside the function
- For the architect: spot checks 1 and 2 as written do not fail under that allowed design (lazy router import; page reads take `_RESTORE_GATE` via `access._reading`)

## Findings

None

Parts that needed a repair: spot-check restores left a stale `categories` `.pyc` that hid the correct source order until `__pycache__` was cleared

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2911 passed`, `All checks passed.` (N + 16 = 2911)
- Given tests: `16 passed`
- `git diff --stat HEAD -- tests`: nothing
- templates/static status: nothing
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Thin-web search: no output
- Bind-time import search: no output

## Requirement checklist

- R1, R3, R4: `test_web_split.py` (16)
- R2, R5: earlier dashboard, backups-gate, sync-setup, budgets, and security tests still pass
- R6: `docs/architecture.md` `web/` line matches the spec
- Moved, not rewritten: `home`, `back_up`, and `budgets` bodies match `HEAD:src/finances/web/app.py` aside from imports and `web_app.` hooks

## Probe

None, as the guide says.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored (with `__pycache__` cleared so restores take effect).

1. `home.py` imports `_today` by name: `test_web_dashboard.py` still shows `Today is 2026-05-25.` (lazy import in `create_app` binds after the patch; allowed by the guide preamble).
2. `backups.py` makes its own lock: `test_requests_wait_while_a_restore_runs` still waits (the deciding GET `/accounts` uses `access._reading` on `web._RESTORE_GATE`). Mutating `access.py` to use its own lock fails as expected.
3. Categories registers `/categories/rules/{rule_id}` first: `test_fixed_paths_come_before_the_rule_id` fails.
4. `sync.py` imports `urllib_transport` by name: `test_web_sync_setup.py` fails with refused network calls.
5. One route left out: `test_the_same_routes_as_before_the_split` fails (49 vs 50).

## Out of scope

Absent: changed templates, static files, messages, notices, statuses, new routes, or changed earlier tests.
