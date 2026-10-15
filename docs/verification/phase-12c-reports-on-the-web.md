# Verify Phase 12c: reports on the web

Spec: `docs/phases/phase-12c-reports-on-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added `GET /reports`, which shows balances, months, and spending through Phase 12a's and 12b's functions. Two templates and one test file were given; no migration.

These are correct and must not be reported: a private helper in `app.py` that reads the four fields; `tests/integration/test_web_reports_more.py` when the coder listed it (the spec allows it).

## 1. Gates

N is `2433` when Phase 12b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 16 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_reports.py --no-cov` | exactly `16 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.views --cov=finances.analysis --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|summarize\(|load_flows\(|format_cents\(" -- src/finances/web` | no output |
| `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/web/app.py
 M src/finances/web/templates/layout.html
?? src/finances/web/templates/reports.html
?? tests/integration/test_web_reports.py
```

and `?? tests/integration/test_web_reports_more.py` only if the coder's report lists it.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R4 | gate 2 | passes |
| R5 | read the route | one `_reading()` session; no sums, sorting, date arithmetic beyond `month_bounds` and `_day`, or formatting |
| no writes | `git diff HEAD -- src/finances/web/app.py` | no new `@api.post` |

## 4. Probe

None: the given tests drive the page with every kind of request. Use the spot checks instead.

## 5. Spot checks

For each change, say which given test would fail. If none would, that is a finding.

1. The months end with the current month even when a month is chosen.
2. A refused request answers `200`.
3. `month` wins silently when `from` and `to` are also given.
4. The form loses the dates that were typed.
5. The page leaves balances out when a request is refused.

## 6. Out of scope

Each must be absent: JavaScript; a `POST` route; a change to the home page or to `cli/`.
