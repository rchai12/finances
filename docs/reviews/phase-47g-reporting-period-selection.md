# Review: Phase 47g: shared reporting period selection

- Verdict: PASS
- Passed: 4639
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None.

Parts that needed a repair: None.

Built beyond the spec: None.

## Baseline, scope and provenance (2026-11-16)

Reviewed delivery commit `f792f13aaa1bb7f910c639e464267ac83397ad36` against finalized planning baseline `d417171dbb99d5d78ab5b6a02adeb1bdf180ba48`. The baseline includes approved and committed Phase 47f at `666e035a66e2bbf311c016ddb72e5dbd5e962968`, with N = 4583. The Phase 47g spec and guide match the committed planning baseline and HEAD. Read AGENTS.md, architecture, phase conventions, testing strategy, handoff procedure, spec/guide, progress, the 47g remediation design, all changed production files and tests, and the existing report/export/MCP callers and tests.

The baseline-to-delivery changed-path set is exactly the twelve Scope paths: eight production files, three new tests and progress. Only the three new test files appear in the test diff; no existing tests or fixtures changed. Both supplied unit-test files are byte-identical to the Python blocks in the spec. `git diff --check` is clean. No dependency, configuration, migration, permission, option/schema or critical-module change is present. The phase adds the specified domain period/error contracts and CLI/web adapters; the existing report wrappers preserve `_range`, `_first_day`, `_spending_range` and `_month_start` seams, while export callers import the shared adapters directly. MCP `get_spending` and `_month_start` delegate to the domain contract; unrelated `month_over_month` parsing remains untouched. Source inspection confirms existing domain period coverage functions are unchanged.

The original workspace had no tracked modifications and only unrelated untracked `.vscode/settings.json`, which was preserved. Verification ran in a fresh local clone at `/tmp/finances-47g-verify-UmDU0Y/checkout`, at the exact delivery commit, with the existing venv linked and excluded locally. The clone was clean before gates. Each Python invocation selected clone `src` through `PYTHONPATH`; `finances.__file__` resolved to `/tmp/finances-47g-verify-UmDU0Y/checkout/src/finances/__init__.py`. SHA-256 manifests for all 1,027 tracked files in the reviewed clone and original workspace matched after verification (`/tmp/phase47g-clone-manifest.sha256`, `/tmp/phase47g-workspace-manifest.sha256`). Thus this review applies to the exact tested bytes. The `.vscode` file is untracked and was not read or modified.

## Fresh independent acceptance

Ran the guide's gates sequentially in the isolated checkout with Python 3.12.16, pytest 9.1.1, pytest-xdist 3.8.0 and pytest-cov 7.1.0. Used four local workers and one coordinated coverage-producing job. Coder results recorded in progress are historical evidence; the following gates are fresh independent observations. Requested permission up front for the existing synthetic localhost-binding tests; the permitted run succeeded, with no failed sandbox attempt. No real statements, real database, Keychain, aggregator, network or dependency installation was used.

| Command | Fresh observation |
|---|---|
| `.venv/bin/python scripts/check.py --first core,cli,web,mcp --workers 4` | exit 0; selected-first `3168 passed in 54.27s`; full `4639 passed in 95.13s`; every section had zero failures/skips; no xfails or warnings summary; overall coverage 99.98%; lint, format and critical coverage passed; final line `All checks passed.` |
| `.venv/bin/python -m coverage report --include="*/finances/domain/periods.py,*/finances/cli/periods.py,*/finances/web/periods.py" --fail-under=100` | immediately after the check; exit 0; domain, CLI, web and TOTAL each 100%, zero missed lines and branches |
| `.venv/bin/python -m pytest tests/unit/test_period_selection.py tests/unit/test_period_adapters.py --no-cov` | exit 0; exactly `19 passed in 0.35s` |
| Scope, bytes and status | exact twelve-path baseline diff; only three new tests; given files identical; diff check clean; isolated checkout clean; all 1,027 tracked workspace/clone bytes matched |

Full check output is retained at `/tmp/phase47g-review-check.log`.

Full-run section table:

```text
Sections:
  migrations    184 passed    0 failed    0 skipped
  scripts       100 passed    0 failed    0 skipped
  web           888 passed    0 failed    0 skipped
  cli           460 passed    0 failed    0 skipped
  mcp           210 passed    0 failed    0 skipped
  parsers       903 passed    0 failed    0 skipped
  sync          284 passed    0 failed    0 skipped
  core         1610 passed    0 failed    0 skipped
```

The check's final ten lines:

```text
  core         1610 passed    0 failed    0 skipped
== critical coverage

Summary:
  lint: passed
  format: passed
  tests (core,cli,web,mcp): passed
  tests: passed
  critical coverage: passed
All checks passed.
```

## Requirements and deciding evidence

| Requirement | Deciding evidence and observation |
|---|---|
| R1 | Given `test_select_period`, `test_selection_errors`, and coder `test_domain_purity_and_immutability` cover the frozen `Period`, typed error code/message, immutable results and pure module boundary. Source imports no CLI, web, MCP or clock code and takes `today` explicitly. |
| R2 | Given conflict-first/incomplete cases and coder `test_presence_matrix` exercise all eight presence combinations and exact codes/messages. The web adapter calls shared preflight before `_day`; its given incomplete-before-date guard and the scratch mutation below prove the order. |
| R3 | Six given selection cases cover default leap February, explicit month/year boundaries, valid and reversed ranges; three given errors cover conflict precedence, incomplete endpoints and empty month. Coder tests add invalid numeric months and both partial directions. Source reuses `month_range`/`month_bounds`, preserves inclusive and reversed endpoints, and adds no date validation. |
| R4 | Given `test_first_day` plus coder `test_first_day_errors` cover default/explicit/error behavior. `test_defaults_and_delegation` spies on shared selection through CLI, web and MCP callers. |
| R5 | Given `test_cli_period_refusals` pins empty-month refusal, conflict/incomplete messages, `Exit(1)` and exact stderr. The compatibility matrix exercises actual CLI report and export endpoints; explicit selections avoid clock reads. The legacy report aliases remain available. |
| R6 | Given web refusal/empty-month guards pin error precedence, exact texts and empty default behavior. The public compatibility matrix checks actual report and export status/form errors, inclusive rows and CSV parity; bad-date cases verify `from` then `to` parsing. The route aliases remain available and export imports the shared adapter directly. |
| R7 | Given `test_mcp_bad_month_keeps_tool_error` and coder `test_actual_mcp_period_matrix`, `test_actual_month_start_caller`, `test_mcp_explicit_no_calendar_and_web_empty` and `test_schema_and_unmigrated_precedence` exercise the real in-memory MCP server, defaults, explicit/incomplete/reversed selections, ToolError, month-start translation, unchanged input schema/read-only metadata and schema precedence. No month argument is added. |
| R8 | Coder `test_public_report_export_inclusive_parity`, `test_public_refusal_matrix` and `test_public_bad_dates` use migrated synthetic data immediately before, on and after February endpoints. They pin inclusive report/export/CSV results, CLI exit/stderr, web status/error text and deferred reversed-range refusal. Full unchanged prior-suite acceptance also passed. |

The compatibility suite uses synthetic transactions at January 31, February 1, February 29 and March 1. Its default, explicit-month and explicit-range cases compare actual CLI spending/export and web report/export results, including exact CSV bytes and date labels. The MCP matrix invokes the in-memory server, not a socket. Existing schema-not-migrated precedence and read-only behavior remain covered. The supplied 19 cases plus 37 coder cases account for the increase from 4583 to 4639; the fresh full suite confirms the final count.

## Fresh scratch-only spot checks

Each mutation was applied in its own disposable local clone, with clone `src` import provenance confirmed before running the named given test. Reviewed source and tests were never modified. All five tests failed with exit 1 on the intended broken behavior:

| Mutation | Deciding given case | Broken observation |
|---|---|---|
| Reverse supplied endpoints in `select_period` | `test_select_period[reversed-deferred]` | Returned Jan 2 then Jan 3 instead of preserving Jan 3 then Jan 2. |
| Check incomplete before conflict | `test_selection_errors[conflict-first]` | Reported code `incomplete` instead of `conflict`. |
| Normalize empty CLI month to `None` | `test_cli_period_refusals[empty]` | Did not raise the required `Exit(1)`. |
| Parse web dates before structural preflight | `test_web_period_refusals[incomplete-before-date]` | Returned the `from` date error instead of `give both from and to`. |
| Hard-code default February to 28 days | `test_select_period[leap-default]` | Returned February 28 instead of February 29. |

Logs are retained at `/tmp/phase47g-spot-{reversed,conflict-order,cli-empty,web-order,leap}.log`. Each mutation is distinguished by its intended assertion, with no unrelated guard masking the result.

## Progress and verdict

The progress entry records the planning baseline, 19 given and 37 coder cases, 4639 result, scoped files, behavior-preservation decisions and coder evidence. Its test outcomes and 95-second timing are historical; the fresh independent run above took 95.13 seconds. No functional, baseline, scope or environment blocker remains. Phase 47g is PASS for the exact commit and reviewed bytes above. Only this review report was written; implementation, progress, phase documents and unrelated work were not changed. No commit or push was performed.
