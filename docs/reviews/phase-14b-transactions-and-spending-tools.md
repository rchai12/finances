# Review: Phase 14b

- Verdict: PASS
- Passed: 3182
- Findings: 0
- Approved deviations: the summary's `spent_cents` is `spent_cents + refunds_cents` because `SpendingSummary` has no `purchases_cents`
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `3182 passed`, `All checks passed.` (N + 27 = 3172; extra 10)
- Given tests: `27 passed`
- Earlier MCP tests: `19 passed`
- Coverage of `finances.mcp_server`: `Required test coverage of 100% reached`
- `git grep` of views/web/cli imports: no output
- `git grep` of log/print: no output
- `git diff --stat HEAD -- tests`: exactly the two files of the earlier-tests diff
- Given files match the spec blocks; the three descriptions match the spec's text

## Requirement checklist

- R1: `test_pages`; `test_refusals` (account, person, kind, start after end)
- R2: `test_every_transaction_latest_first`; `test_filters`
- R3: `test_spending_this_month_by_category`; `test_spending_by_person_over_a_range`; `test_refusals` (both or neither, start after end)
- R4: `test_month_over_month`; `test_month_over_month_ends_this_month_by_default`; `test_month_over_month_ends_with_the_month_given`
- R5: `test_six_read_only_tools`; `test_each_tool_description_matches_the_table`
- R6: given earlier-test diffs applied; `git diff --stat HEAD -- tests` lists those two files
- R1 to R4 edges: `tests/integration/test_mcp_spending_more.py` (account, bank, and group filters; closed account; `limit` 200; spending by merchant, account, bank, card, and group; empty period; `count` 24)

## Probe

Saved outside the repository, run from the root against a temporary `FIN_DATA_DIR`, then deleted. Tool list check expects six names.

- `ok   six tools over stdio`
- `ok   balances on an empty database`
- `ok   months 0 refused`
- `FAILURES 0`

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. `next_offset` set when the page is full: `test_pages` last page fails (`9`).
2. `refund` from the sign alone: `test_every_transaction_latest_first` fails (`[9, 6, 4, 2]`).
3. `get_spending`'s `spent_cents` is the net: `test_spending_this_month_by_category` fails (`2000`).
4. `get_spending` defaults to `date.today()`: the same, start is not `2026-05-01`.
5. `month_over_month` ignores `month`: `test_month_over_month_ends_with_the_month_given` fails (`2026-04`, `2026-05`).
6. `list_transactions` does not check `start` after `end`: `test_refusals` (start after end) fails (no error).

## Out of scope

Absent: a findings, budget, or coverage tool; a change to `analysis`, `views`, `web`, or `cli`; a write of any kind.
