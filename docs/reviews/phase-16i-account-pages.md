# Review: Phase 16i

- Verdict: PASS
- Passed: 2813
- Findings: 0
- Approved deviations: None
- For the architect: Spot check 3's order string also appears on `latest_balance`; a replace that hits the first match leaves `list_balance_snapshots` alone and the given page test still passes. Prefer a mutation scoped to `list_balance_snapshots` in the deciding-case table.

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2813 passed`, `All checks passed.` (N + 11 = 2809; 4 more are the coder's)
- Given tests: `11 passed`
- Earlier pages, search, transfers, reports, accounts and bulk: `119 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%` (`2813 passed`)
- Both searches: no output
- Scope: `git status --short` lists the guide's paths, plus `docs/progress.md` and this review

## Requirement checklist

- R1: `list_balance_snapshots` orders by `as_of_date` desc then `id` desc; `test_list_balance_snapshots_puts_the_higher_id_first_on_the_same_day`.
- R2: one `load_flows`; filter by account name and card; spending via `spending_lines(..., "group")`; months via `summarize` and `months_ending`; income month and later-than-today month in the coder tests.
- R3: closed, Joint, and no Cards line in `test_closed_joint_and_no_cards_on_the_page`.
- R4, R5: given web tests; `section` is `accounts`; thin route; given templates used.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the named tests run, and the file restored.

1. Spending is not filtered by account: `test_the_account_page` fails (`Home` row).
2. The card filter is ignored in spending: `test_one_card_of_the_account` fails (`Food $199.01` first).
3. Balance history comes oldest first (mutate `list_balance_snapshots` only): `test_the_account_page` fails (Balance shows 2026-03-31).
4. An unknown card is accepted: `test_refused` fails (`200` for `card=3333` and `card=12`).
5. The months end with last month: `test_the_account_page` fails (12 month rows instead of 13; last would be 2026-04).

## Out of scope

Absent: charts or JavaScript; a change to the security policy; POST or edit forms on the account page (only the given GET month picker).
