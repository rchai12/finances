# Review: Phase 25

- Verdict: PASS
- Passed: 2791
- Findings: 0
- Approved deviations: None
- For the architect: the given `no-statements-needed` case does not catch "mapped accounts also get statements problems" when `has_data` is true and the statement end is not stale; give a mapped account with a stale `newest_statement_end` for that spot check.

## Findings

None

Parts that needed a repair: spot check 4 needed `test_a_mapped_account_has_no_statements_problem` (mapped + stale statement end).

Built beyond the spec: none.

## Gates

- `scripts/check.py`: `2791 passed`, `All checks passed.` (N + 22 = 2785; 6 more are the coder's)
- Given tests: `22 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Both searches: no output
- Scope: `git status --short` lists the guide's 9 paths, plus this review
- Given files: `tests/unit/test_health.py` and `tests/e2e/test_cli_health.py` match the spec's blocks

## Requirement checklist

- R1 to R4: `health_problems` (`domain/health.py`); given unit tests pass, including kind/account/detail order.
- R5: `account_facts` / `gather_health` (`analysis/health.py`); active accounts only; UTC date of `pulled_at`; drift from `with_balance=True`; coder facts tests.
- R6, R7: `health_rows` / `health_summary`; `fin health` with `--as-of` as `fin recurring` reads it; given CLI tests and `test_fin_health_without_as_of_uses_today`.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the code, the named tests run, and the file restored.

1. Closed accounts are checked too: `test_account_facts_leaves_out_a_closed_account` and `test_every_kind_of_problem` fail.
2. A drift of zero is reported: `test_accounts_on_simplefin[no-drift]` fails.
3. A threshold uses "at least" instead of "more than": `test_backups` (2-day edge), `test_accounts_on_simplefin[three-days]`, and `test_accounts_on_statements[45-days]` fail.
4. An account on SimpleFIN also gets `statements` problems: `test_a_mapped_account_has_no_statements_problem` fails (added after the given case did not catch it).
5. Problems come in the order the accounts were listed: `test_problems_come_by_kind_then_account_then_detail` fails.

## Out of scope

Absent: a web page; a change to `fin doctor`; a migration; stored sync failures.
