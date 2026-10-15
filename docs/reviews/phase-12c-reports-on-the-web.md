# Review: Phase 12c

- Verdict: PASS
- Passed: 2449
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2449 passed`, `All checks passed.` (N + 16 = 2449)
- Given tests: `16 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Both searches: no output
- Scope: `git status --short` lists exactly the guide's paths, plus this review; no `test_web_reports_more.py` was needed
- Given files: `layout.html`, `reports.html`, and `tests/integration/test_web_reports.py` are identical to the spec's blocks

## Requirement checklist

- R1 to R4: the given tests pass.
- R5: `GET /reports` opens one `_reading()` session; it calls `balance_report`, `spending_report`, and `month_report`, and the views format them. The only date work is `_day`, `month_range`, and `month_bounds` inside the private `_spending_range`.
- No writes: `git diff HEAD -- src/finances/web/app.py` adds no `@api.post`.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the tests run, and the code restored.

1. The months end with the current month even when a month is chosen: `test_a_month` and `test_a_range_by_merchant_and_months_ending_with_it` fail.
2. A refused request answers `200`: all eight cases of `test_a_refused_report` fail.
3. `month` wins silently when `from` and `to` are also given: `test_a_refused_report[month=2026-05&from=2026-05-01-...]` fails.
4. The form loses the dates that were typed: `test_a_range_by_merchant_and_months_ending_with_it` fails.
5. Balances are left out when a request is refused: all eight cases of `test_a_refused_report` fail.

## Out of scope

Absent: JavaScript; a `POST` route; a change to the home page or to `cli/`.
