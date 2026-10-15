# Verify Phase 13c: insights on the web

Spec: `docs/phases/phase-13c-insights-on-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added `GET /insights`, `insights_heading`, and a fix so a subscription overlap sees a merchant's category from any earlier charge. Two templates, `tests/support.py`, a rule in `docs/testing.md`, and one test file were given; no migration.

These are correct and must not be reported: a second read of the charges for the category map; a private helper in `app.py` for the month; `tests/integration/test_web_insights_more.py` when the coder listed it.

## 1. Gates

N is `2523` when Phase 13b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 9 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_insights.py --no-cov` | exactly `9 passed` |
| `.venv/bin/python -m pytest tests/e2e/test_cli_insights.py tests/unit/test_insights.py --no-cov` | `21 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.views --cov=finances.analysis --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|format_cents\(|spikes\(|merchant_stats\(" -- src/finances/web` | no output |
| `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M docs/testing.md
 M src/finances/analysis/insights.py
 M src/finances/cli/reports.py
 M src/finances/views/insights.py
 M src/finances/web/app.py
 M src/finances/web/templates/layout.html
?? src/finances/web/templates/insights.html
?? tests/integration/test_web_insights.py
?? tests/support.py
```

and `?? tests/integration/test_web_insights_more.py` only if the coder's report lists it.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1, R3 to R5 | gate 2 | passes |
| R1 | `git diff HEAD -- src/finances/analysis/insights.py` | only the category map changed |
| R2 | gate 3, and read `insights_command` | passes; the command prints `insights_heading` |
| R6 | read the route | one `_reading()` session; no `@api.post` added; no sums or sorting |
| docs | `git diff HEAD -- docs/testing.md` | exactly the given rule added |

## 4. Probe

None: the given tests drive the page and the fix. Use the spot checks instead.

## 5. Spot checks

For each change, say which given test would fail. If none would, that is a finding.

1. The category map uses only the four months again.
2. The page lists inactive recurring charges.
3. A bad month answers `200`.
4. The month field loses what was typed after a refusal.
5. The Insights entry is missing from the menu on other pages.

## 6. Out of scope

Each must be absent: JavaScript; a `POST` route; changes to existing tests; any other change to findings or recurring charges.
