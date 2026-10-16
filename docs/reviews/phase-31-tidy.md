# Review: Phase 31

- Verdict: PASS
- Passed: 2895
- Findings: 0
- Approved deviations: `test_budgets_more.py` now patches `finances.clock.today` (the old `cli.budgets.date` patch could not work after the tidy)
- For the architect: none

## Findings

None

Parts that needed a repair: the Phase 26a coder test that froze `finances.cli.budgets.date`

Built beyond the spec: none

## Gates

- `scripts/check.py`: `2895 passed`, `All checks passed.` (N + 8 = 2895)
- Given tests: `8 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- `date.today()` search: only `src/finances/clock.py` (with `--untracked` while the new file is untracked)
- `_print_rows` / `_statement_cells` / `_taken`: no output
- budget amount message: only `src/finances/domain/budgets.py`
- `test_list_backups` diff: matches the spec

## Requirement checklist

- R1: `clock.today()` via the module; web `_today` wraps it; given one-today tests.
- R2: Sync routes call `_utc_today()`.
- R3: `fin statements list` uses `statement_rows`.
- R4: `cli.common.print_rows`; private copies gone.
- R5: `AMOUNT_MESSAGE` in domain; repo, CLI, web use it.
- R6: `fin backup list` uses `backup_rows` with Size.

## Probe

None, as the guide says.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored.

1. `fin budgets list` keeps `date.today()`: budgets parametrized case fails (real month).
2. Web `_today` keeps UTC: `test_every_page_reads_the_same_today` fails (real date).
3. `fin health` keeps `date.today()`: health test fails (backup problem).
4. `from finances.clock import today` in reports: months case fails (real months).
5. `fin backup list` keeps two columns: `test_list_backups` fails (no Size).

## Out of scope

Absent: split of `web/app.py`; changes to `sync/` or stored timestamps.
