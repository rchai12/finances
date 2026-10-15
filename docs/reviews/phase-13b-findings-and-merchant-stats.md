# Review: Phase 13b

- Verdict: PASS
- Passed: 2523
- Findings: 0
- Approved deviations: None
- For the architect: R10 maps each merchant to the category of its latest charge "up to M's last day" while loading flows only for the four months; the coder used the loaded months, so a yearly subscription whose latest charge is older than that has no category and never joins an overlap. Say whether overlaps should see it.

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2523 passed`, `All checks passed.` (N + 21 = 2511; 12 more are the coder's)
- Given tests: `21 passed`
- Phase 13a's given tests: `33 passed`, unchanged
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Both searches: no output
- Scope: `git status --short` lists exactly the guide's paths, plus this review
- Given files: `tests/unit/test_insights.py` and `tests/e2e/test_cli_insights.py` are identical to the spec's blocks

## Requirement checklist

- R1 to R9, R11 to R13: the given tests pass.
- R1: `git diff HEAD -- src/finances/domain/recurring.py` adds three lines: the last field `previous_cents: int | None = None`, the second-to-last charge read in `_series`, and the field set there.
- R10, R3 (refund only), R4 (thresholds): `tests/integration/test_insights_report.py` covers each item of "Tests to write": a charge the day before the window left out (and one after M); a merchant whose category changed takes the latest; a merchant with only a refund; the spike at exactly half and exactly $50 and just below each; refunds ignored by `frequent_small`; `fin insights` and `fin merchants` without `--month`.
- R10: `insights_report` calls `load_flows` once over `months_ending(month, 4)` and takes the series from Phase 13a's `recurring_charges`; spending is not defined again.
- R14: `cli/reports.py` has no sums, sorting, or rule checks; each command opens one session.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the tests run, and the code restored.

1. A spike with a baseline of zero is reported: `test_spikes` fails.
2. The fee rule matches `FEED` (a substring): `test_interest_and_fees` and `test_the_findings_of_a_month` fail.
3. `frequent_small` counts refunds as visits: `test_frequent_small_ignores_refunds` fails.
4. Overlaps include an inactive series: `test_overlapping_subscriptions` fails.
5. The baseline divides by the earlier months that had spending instead of 3: `test_spikes`, `test_an_earlier_month`, `test_the_baseline_is_the_three_months_before`, and two cases of `test_the_spike_thresholds` fail.

## Out of scope

Absent: a migration; a stored finding; a web page; any change to Phase 13a's rules other than `previous_cents`.
