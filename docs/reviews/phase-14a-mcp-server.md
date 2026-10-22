# Review: Phase 14a

- Verdict: PASS
- Passed: 3033
- Findings: 0
- Approved deviations: tools registered in a loop over a table; `reading()` uses try/finally
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: six extra tests in `tests/integration/test_mcp_more.py`

## Gates

- `scripts/check.py`: `3033 passed`, `All checks passed.` (N + 13 = 3027; extra 6 coder tests)
- `.venv/bin/python -m pip check`: `No broken requirements found.`
- Given tests: `13 passed`
- Coverage command: `Required test coverage of 100% reached. Total coverage: 100.00%`
- Layer search on `mcp_server`: no output
- Logging/print search: no output
- Transport search: one line, `server.py`: `run("stdio")`
- `git diff HEAD -- pyproject.toml`: one added line `"mcp>=2.3,<3",`
- Given files match the spec blocks
- Probe: `FAILURES 0`

## Requirement checklist

- R1: `pyproject.toml` lists `mcp>=2.3,<3`; installed mcp 2.3.0; `pip check` clean
- R2: `test_the_tools_read_through_a_session_that_cannot_write`; `test_read_only_engine_still_enforces_foreign_keys`
- R3: `test_a_database_that_is_not_migrated`; `test_reading_disposes_the_engine_when_the_block_raises`
- R4: `test_the_server_and_its_tools`; `test_a_tool_that_crashes_logs_nothing`; `test_each_tool_description_matches_the_table`
- R5: `test_serve_runs_on_stdio_and_prints_nothing`; transport grep one line
- R6: `test_list_accounts`; `test_list_accounts_and_get_balances_with_no_accounts`
- R7: `test_get_balances`
- R8: `test_get_net_worth_follows_the_app_clock`; `test_get_net_worth_refuses_months_out_of_range`; `test_get_net_worth_without_arguments_uses_twelve_months`
- R9: `test_serve_runs_on_stdio_and_prints_nothing`; `test_serve_takes_no_options`; `test_mcp_help_lists_serve`
- R2, R3, R9 (edges): all six tests in `tests/integration/test_mcp_more.py`

## Probe

Saved outside the repository, run from the root against a temporary `FIN_DATA_DIR`, then deleted.

- `ok   three tools over stdio`
- `ok   balances on an empty database`
- `ok   months 0 refused`
- `FAILURES 0`

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. `reading()` opens a writable engine: the write test does not raise.
2. The `mcp` logger is left at the SDK level: `Tool 'crash' raised an unexpected exception`.
3. `get_net_worth` uses `date.today()`: `as_of` is today's real date.
4. `include_inactive` is ignored: Test Old is absent from the second call.
5. `joint` is true when there is no owner row: Test Savings is joint.
6. `months` is clamped in the body: 61 is accepted (`is_error` is false).
7. The schema check is skipped: the error text is not the fixed not-migrated message.
8. `fin mcp serve` prints a banner: stdout is `Serving MCP`.

## Out of scope

Absent: any tool but the three; a resource or prompt; an option on `fin mcp serve`; a transport but stdio; a write repository function called from `mcp_server`; a migration.
