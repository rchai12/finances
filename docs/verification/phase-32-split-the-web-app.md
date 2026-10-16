# Verify Phase 32: split the web app

Spec: `docs/phases/phase-32-split-the-web-app.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder moved the routes of `web/app.py` into eleven router modules and the shared helpers into modules of their own, with no change in behaviour. One test file was given.

These are correct and must not be reported: any names for the shared modules; routers that read the hooks through a small accessor function; `app.py` importing the routers inside `create_app`.

## 1. Gates

N is `2895` when Phase 31 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 16 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_web_split.py --no-cov` | exactly `16 passed` |
| `git diff --stat HEAD -- tests` | nothing |
| `git status --short src/finances/web/templates src/finances/web/static` | nothing |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|timedelta" -- src/finances/web` | no output |
| `git grep -n --untracked -E "from finances\.web\.app import [^\n]*(_today|_now|_utc_today)|from finances\.sync\.transport import" -- src/finances/web` | no output |

## 2. Scope paths

```
 M docs/architecture.md
 M docs/progress.md
 M src/finances/web/app.py
?? src/finances/web/routes/
?? src/finances/web/<the shared modules>
?? tests/unit/test_web_split.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1, R3, R4 | gate 2 | passes |
| R2, R5 | gates 1, 3, 4 (the earlier tests replace the hooks, hold the gate, and replace the transport) | pass |
| R6 | `git diff HEAD -- docs/architecture.md` | exactly the spec's line |
| moved, not rewritten | read a sample of three routes in their new modules against `git show HEAD:src/finances/web/app.py` | the bodies are the same apart from imports |

## 4. Probe

None. The whole suite is the probe.

## 5. Spot checks

Each line names the place and the test that decides it. Make the change, run the tests, and see one fail; if none does, that is a finding.

| Change | Deciding test | Correct | Broken |
|---|---|---|---|
| 1. `routes/home.py` imports `_today` by name (`from finances.web.app import _today`) | `test_web_dashboard.py` (replaces `finances.web.app._today`) | `Today is 2026-05-25.` | the real date |
| 2. `routes/backups.py` makes its own lock | `test_backups_page_more.py` (holds `web._RESTORE_GATE`) | a request waits | it does not wait |
| 3. The categories router registers `/categories/rules/{rule_id}` first | `test_fixed_paths_come_before_the_rule_id` | passes | fails |
| 4. `routes/sync.py` imports `urllib_transport` by name | `test_web_sync_setup.py` (replaces `transport.urllib_transport`) | the fake answers | a refused network call |
| 5. One route is left out of every router | `test_the_same_routes_as_before_the_split` | 49 routes | 48 |

## 6. Out of scope

Each must be absent: a changed template, static file, message, notice, or status; a new route; a changed earlier test.
