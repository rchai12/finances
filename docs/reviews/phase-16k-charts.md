# Review: Phase 16k

- Verdict: PASS
- Passed: 2829
- Findings: 0
- Approved deviations: None
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- Chart.js SHA-256: `3850656abbdc319141e6e8ce8eacde2622fc767c30e20d81704af2bf3159f92d`
- `scripts/check.py`: `2829 passed`, `All checks passed.` (N + 13 = 2826; 3 more are the coder's)
- Given tests: `13 passed`
- Security + account page: all passed
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%` (`2829 passed`)
- Both searches: no output
- `git diff HEAD -- src/finances/web/app.py`: only `script-src` changed in the headers (plus the account chart context)
- Probe: every line `ok`, `FAILURES 0`

## Requirement checklist

- R1: CSP uses `script-src 'self'`; security test updated.
- R2: `pie_chart` / `months_chart` / `balance_chart` in `views/charts.py`; edges in `test_chart_views.py`.
- R3: `GET /account` passes JSON text or `None` for the three charts; pie only when spending is shown.
- R4: given templates and `charts.js`; CSS `.chart` line; only the account page loads scripts.
- R5: no coder change to `docs/architecture.md`.

## Probe

Headless Chrome: site started, three canvases `data-drawn="yes"`, no CSP refusal.

## Spot checks

Each change was made in the code, the named tests (or probe) run, and the file restored from the working tree (not `git checkout` on uncommitted given templates).

1. Inline script on the account page: `test_the_account_page_loads_two_scripts_and_no_inline_script` fails (third tag).
2. Policy keeps `script-src 'none'`: probe `browser: three charts drawn` FAIL.
3. Pie keeps a negative line: `test_the_charts_carry_cents` fails (`Shopping` with `-2000`).
4. Chart data carries dollars: `test_the_charts_carry_cents` fails (`200.0` instead of `20000`).
5. Scripts in the layout for every page: `test_other_pages_load_no_script` fails on `/reports` and the others.

## Out of scope

Absent: charts on other pages; files loaded from another site; a change to `chart.umd.js` after pinning; another library.
