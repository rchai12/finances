# Phase 47b: faster test execution

Measured 2026-11-15 on the local machine. Recommend **`--workers 4`** for
full acceptance on this machine; the default remains serial (`--workers 1`).
Its command wall time was 2.84× faster than serial.
The fastest measured count was 4; select the lowest worker count within
10% of the fastest time. These single sequential trials are measured guidance,
not a promised speedup. Background machine load and filesystem caches were not
controlled; no comparison was inconclusive under that rule, so no pair was repeated.

## Baseline and environment

- Baseline: `c8ec721fc3c62ab5750e091851cda3a528c87e01`. Phase 47a’s committed
  reassessment is PASS, zero findings; executable 47b spec is committed.
- Clean implementation checkout: `/tmp/finances-47b-c8ec721` (macOS resolves it to
  `/private/tmp/finances-47b-c8ec721`). Existing venv linked, no new environment.
  `PYTHONPATH=/tmp/finances-47b-c8ec721/src` on every Python command; the import
  check resolved finances inside this clone. Original `.vscode/settings.json`
  was preserved; only the nine Phase 47b paths were copied back after acceptance.
- Apple M5 Pro; 18 physical/logical CPUs; 51,539,607,552 bytes (48 GiB) memory;
  macOS-27.2.1-arm64-arm-64bit; Python 3.12.16.
- Packages: pytest 9.1.1, pytest-xdist 3.8.0, execnet 2.1.2, pytest-cov 7.1.0, coverage 7.16.2, ruff 0.17.0, hypothesis 6.169.1, SQLAlchemy 2.1.4, alembic 1.20.0, anyio 4.15.1. Full installed package inventory is in `snapshot.json`
  in the evidence folder below.
- Dependency setup: `.venv/bin/python -m pip install 'pytest-xdist>=3.6,<4'`.
  Sandboxed package-index DNS failed (exit 1); the authorized permitted rerun
  succeeded (exit 0), installing only pytest-xdist 3.8.0 and execnet 2.1.2.
- Baseline `.venv/bin/python scripts/check.py`: sandbox exit 1, 4,327 passed and
  10 existing localhost-bind errors; permitted rerun exit 0, **N = 4,337 passed**
  in 277.27 seconds, all gates passed. Matrix runs used the same loopback permission.
  No existing tests were changed or omitted to resolve the environment restriction.

## Commands and measurement

All commands ran sequentially from the implementation checkout with the
`PYTHONPATH` above. At most four local load-scheduled workers were used; no other
coverage run was launched concurrently by this task, and no agents were delegated.
Real samples were not requested or run.

The acceptance commands are:

```sh
.venv/bin/python scripts/check.py --first scripts --workers 1 --durations 20
.venv/bin/python -m coverage json -o /tmp/finances-47b-evidence-c8ec721/workers-1/saved-coverage.json
.venv/bin/python scripts/check.py --first scripts --workers 2 --durations 20
.venv/bin/python -m coverage json -o /tmp/finances-47b-evidence-c8ec721/workers-2/saved-coverage.json
.venv/bin/python scripts/check.py --first scripts --workers 4 --durations 20
.venv/bin/python -m coverage json -o /tmp/finances-47b-evidence-c8ec721/workers-4/saved-coverage.json
.venv/bin/python -m pytest tests/unit/test_check_parallel.py --no-cov
```

As the spec permits, the three check invocations used a temporary injection
harness rather than losing their JUnit files during normal cleanup. The exact
check invocations were `.venv/bin/python /tmp/finances-47b-evidence-c8ec721/benchmark.py
--first scripts --workers W --durations 20`, for W = 1, 2, 4, redirected respectively
to `serial.log`, `two.log`, `four.log`. The harness imports the checkout’s
`scripts/check.py`, calls its existing `main(argv, run=...)`, and its runner calls
unchanged `run_command(command, cwd)` before copying reports outside the checkout.
No pytest arguments or acceptance gates are replaced. Each subprocess and overall
exit code is saved in `workers-W/timing.json`; all are 0. Each full check ends
`All checks passed.`. All three immediate coverage exports exited 0.

Command wall time below is log creation at shell redirection through final output
flush (includes interpreter startup and all acceptance work; excludes the final
process teardown). Separately, the monotonic harness timer measures the whole
`main` call, including report copies and cleanup. Pytest time is its full-suite
summary, not the selected-first step. Those boundaries explain small differences;
coverage exports are separate commands and excluded from benchmark wall time.

| Workers | Command wall (s) | Main wall (s) | Pytest full step (s) | Passed | Failed/skipped/xfail/warnings |
|---:|---:|---:|---:|---:|---:|
| 1 | 284.31 | 284.27 | 275.51 | 4,371 | 0 |
| 2 | 162.60 | 162.54 | 154.63 | 4,371 | 0 |
| 4 | 100.21 | 100.17 | 91.78 | 4,371 | 0 |

The given-only command exited 0: exactly **7 passed**. There are **27 coder cases**,
so the final suite is 4,337 + 7 + 27 = **4,371**; selected-first scripts has 100 cases.

## Test inventory and coverage parity

Before the matrix, the external `collect.py` plugin saved complete `item.nodeid`
inventories with these exact invocations (both exit 0):

```sh
.venv/bin/python /tmp/finances-47b-evidence-c8ec721/collect.py /tmp/finances-47b-evidence-c8ec721/collection-serial.json -p no:xdist
.venv/bin/python /tmp/finances-47b-evidence-c8ec721/collect.py /tmp/finances-47b-evidence-c8ec721/collection-xdist.json -n 4 --dist load
```

The helper uses `pytest.main(['--collect-only', '-q', '--no-cov', ...])`; collection
remains controller-local. Both inventories contain exactly the same ordered
4,371 node IDs. Inventory SHA-256: `ad1c291c3eb547e39fc88943400ceaf72c321008a732254c5e58a3b10471181b`.
The external `compare.py` converts file/class/function portions to JUnit identity
pairs and preserves parameter text verbatim (including IPv6 `::`), then compares
Counters of `(classname, name)` for every saved full-run JUnit report against the
inventory. Every run has all 4,371 expected identities with the same multiplicities
and only passing outcomes. The comparison is not based on counts alone.

All runs measure the **same 199 files** at **99.98479434349578%** overall coverage
(terminal display 99%, above 85%). Every critical module has zero missing lines
and zero missing branches. For every measured file, the missing-line sets and
missing-branch-pair sets are exactly identical across serial, 2 and 4 workers.
Only an absolute checkout root prefix may be removed; no files or gaps are
ignored and execution counts are not compared. The only missing lines in any run
are the existing `src/finances/__init__.py` lines 5 and 6; no branches are missing.
Each immediate persistent-data export also matches its original pytest JSON report.
`compare.py` exited 0 and saved `comparison.json`. No new skips, xfails or warnings.

## Timing observations and later fixture work

Slowest item of each phase **among each full run’s top 20**:

| Workers | Phase | Seconds | Item |
|---:|---|---:|---|
| 1 | setup | 0.45 | `tests/integration/test_mcp_chains.py::test_a_parent_and_its_child_declined_together` |
| 1 | call | 13.18 | `tests/integration/test_ledger_properties.py::test_any_order_of_statements_and_pulls_stores_each_transaction_once` |
| 1 | teardown | 0.50 | `tests/unit/test_transport_proxies.py::test_proxy_settings_are_ignored` |
| 2 | setup | 0.43 | `tests/integration/test_mcp_chains.py::test_declining_a_parent_declines_what_waits_on_it` |
| 2 | call | 13.82 | `tests/integration/test_ledger_properties.py::test_any_order_of_statements_and_pulls_stores_each_transaction_once` |
| 2 | teardown | 0.50 | `tests/unit/test_transport_proxies.py::test_proxy_settings_are_ignored` |
| 4 | setup | 0.39 | `tests/integration/test_web_findings.py::test_reopening_a_finding_on_the_page` |
| 4 | call | 16.16 | `tests/integration/test_ledger_properties.py::test_any_order_of_statements_and_pulls_stores_each_transaction_once` |
| 4 | teardown | 0.50 | `tests/unit/test_transport_proxies.py::test_proxy_settings_are_ignored` |

The property-based ledger and text-limit workflows dominate individual call
timings. Setup timings include repeated fresh migrations: `db_engine` upgrades
an isolated database for each test. That repeated work merits a later, separately
specified fixture profiling/design experiment. These top-20 observations do not
measure aggregate migration cost or prove that caching is safe. This phase changes
no fixture scope, migration setup, property examples, assertions or test identities.

Before the first parallel run, inspection of test writes, subprocesses, socket
binds and fixtures found database/file/Git-hook paths rooted in `tmp_path` or
`TemporaryDirectory`; loopback HTTP servers bind `127.0.0.1` on port 0. Proxy port 9
is a deliberately unusable configuration, not a listener. Process-local patches,
parser registries and memory keyrings remain isolated per worker. The successful
matrix establishes actual isolation and coordinated coverage aggregation; the fake
runner cases alone do not. No out-of-scope existing-test repair was needed.

## Tested bytes and evidence

Dirty source/test/config content digest:
`529342c8032e08480cfda283eb9f6613da20cf4ad128a7fa7305a3c4f86cdb65`.
It is SHA-256 of the UTF-8 canonical JSON mapping below (keys sorted, separators
`,` and `:`, no whitespace); each value is SHA-256 of the file’s raw bytes.
These five files cover every changed source/test/dependency/config path.
Documentation was completed after measurement without changing these bytes.

| Path | SHA-256 |
|---|---|
| `pyproject.toml` | `7a6a97081fc023e232cf29bc316c607eded5be7aba9350a5985d1c52402dd2fa` |
| `scripts/check.py` | `9c2ed2fbadb77ffefbca03bd3a179a8a4b193f97f61d29b9f78f24643409d9c0` |
| `tests/sections.toml` | `c640879a98885103710a755bfe7079d33864631801fbe336f42bc55544787ecd` |
| `tests/unit/test_check_parallel.py` | `e95597ad3509b0b5a7d73be6efb8fd3ec9b9f1c4cb53daa04fe3b59aa5a04e29` |
| `tests/unit/test_check_parallel_behavior.py` | `afa4b0847afbccce616c2e2ba53c3223423b9091e2107fd02dca87d82f6681c9` |

Full synthetic evidence is outside the repository in
`/tmp/finances-47b-evidence-c8ec721`: baseline logs, failing-first given log
(6 failed/1 serial guard passed), focused logs, collection logs/inventories,
three benchmark logs, preserved JUnit/coverage/timing reports, installed package
snapshot, and comparison helper/results. The checkout’s temporary reports still
clean up normally; its persistent `.coverage` remains available to later commands.
Evidence is coder acceptance evidence; the independent verifier must run its own gates.

## Requirements and deciding evidence

| Requirement | Test or evidence |
|---|---|
| R1 | Given `test_invalid_workers_are_usage_errors`; coder `test_positive_workers_accepted`, `test_invalid_options_launch_nothing` |
| R2 | Given `test_workers_reach_both_test_steps`, `test_default_stays_serial`, `test_section_forwards_workers_and_durations`; coder `test_flags_reach_first_and_full_only`, `test_section_can_time_serial_tests` |
| R3 | Coder `test_invalid_options_launch_nothing`, `test_explicit_zero_durations_omits_flag`, `test_flags_reach_first_and_full_only`; given section forwarding test |
| R4 | Coder `test_failed_first_prevents_full_tests`, `test_pytest_failure_or_worker_crash_stops_coverage` (exit 1/2/3/4), `test_missing_or_malformed_coverage_fails`, `test_invalid_coverage_counts_cannot_pass`, `test_parallel_reports_root_interpreter_cleanup_and_summary`; existing serial command pins unchanged |
| R5 | Three actual full-run JUnit identity/outcome Counters, per-file coverage-set comparison, all overall/critical gates |
| R6 | Sequential benchmark logs, preserved reports, versions, machine facts, revision and raw-byte digest above |
| R7 | Measured worker selection and timing/fixture observations above |
| R8 | Development loop and bounded evidence-reuse rules in `docs/testing.md` and `docs/phase-conventions.md` |
| R9 | Shared-resource inspection above, successful real worker runs, documented per-checkout coverage and machine-wide worker budget |

Both new files are explicitly assigned to scripts; coder
`test_both_new_files_belong_to_scripts` checks assignment and section selection.
No public application API, application code or migration changes. No unresolved
blockers, no commit or push; independent verification is the next handoff.
