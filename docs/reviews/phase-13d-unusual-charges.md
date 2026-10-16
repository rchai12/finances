# Review: Phase 13d

- Verdict: PASS
- Passed: 2838
- Findings: 0
- Approved deviations: None
- For the architect: Spot check 2's deciding case (refund vs charge) is not hit by switching `_charges` to `_spending` alone, because the group key still uses signed cents. The mutation that fails is grouping spending by absolute amount.

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2838 passed`, `All checks passed.` (N + 6 = 2835; 3 more are the coder's)
- Given tests: `6 passed`
- Earlier insights, web insights, search, dashboard: `63 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%` (`2838 passed`)
- Domain import search: no output
- `git diff HEAD -- tests/unit/test_insights.py`: matches the spec

## Requirement checklist

- R1: `TYPES` ends with `duplicate`, `large_first_charge`; `test_the_two_new_types_come_last`, `test_the_types`.
- R2: `duplicates` groups by account, merchant, day, amount; $20 medium edge in coder tests.
- R3: `large_first_charges` with $250 floor, 3× average (half up), `seen`; refund-only merchant has no finding.
- R4: report adds both; `seen` from all charges before M (`_seen_before(history, first)`).

## Probe

None, as the guide says.

## Spot checks

Each change was made in the named function, the named tests run, and the file restored.

1. `duplicates` ignores the account: `test_duplicates` fails (BAZ BOOKS finding).
2. `duplicates` groups spending by absolute amount (refund with charge): `test_duplicates` fails (QUUX DELI finding).
3. `large_first_charges` uses the first charge, not the largest: `test_large_first_charges` fails (no NEW TV).
4. `insights_report` builds `seen` from the three earlier months only: `test_duplicates_and_a_large_first_charge` fails (BIG HOTEL row).
5. The 3-times rule is `<=` instead of `<`: `test_three_times_the_category_average_exactly` fails (no NEW TV at exactly 3×).

## Out of scope

Absent: a migration; merchant merging; a change to the other six findings.
