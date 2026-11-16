# Review: Phase 47b

- Verdict: PASS
- Passed: 4371
- Findings: 0
- Approved deviations: None
- For the architect: Recommend four workers on this machine from the measured matrix; repeated migration setup merits a separately scoped profiling/design experiment.

## Findings

None.

Parts that needed a repair: None.

Built beyond the spec: None.

## Baseline, isolation, and reviewed bytes (2026-11-16)

Reviewed commit `2d476ac1f925a64600f44b6ebdffb5256b7e2b99` against predecessor `c8ec721fc3c62ab5750e091851cda3a528c87e01`. The predecessor commits Phase 47a's reassessment PASS, zero findings and 4,337 passing tests: N = 4337. Its owner-approved mixed-scope exception is recorded there. The Phase 47b spec and guide were already committed and have no diff between that predecessor and the implementation commit. No predecessor approval or planning-baseline blocker remains.

Read AGENTS.md, architecture, conventions, spec, guide, testing strategy, remediation design, handoff procedure, progress, implementation, tests and benchmark evidence. Original entry status was only `?? .vscode/settings.json`; tracked diff was empty. Preserved that unrelated file. Because the guide requires explicit isolation for a mixed tree, cloned the committed implementation into `/var/folders/2d/386g2_8d69915k8_pvkhdq3c0000gn/T/finances-47b-review-zyj3ar3q/checkout`, linked the existing venv, and excluded only that symlink locally. Isolated status was empty before and after verification. Every Python invocation there used `PYTHONPATH` selecting that clone's src; an explicit import check resolved `finances.__file__` inside it. All tracked clone files still matched the original workspace byte-for-byte before writing this report.

The committed change contains exactly nine permitted paths: scripts/check.py, pyproject.toml, tests/sections.toml, the two new unit test files, docs/testing.md, docs/phase-conventions.md, docs/testing-performance.md and docs/progress.md. No application code, migration, prior test or fixture changed. The given file is byte-for-byte identical to the spec block. Both new files are assigned to scripts. The only dependency declaration change is the authorized dev dependency `pytest-xdist>=3.6,<4`. The progress entry has the required fields, N/final/given counts and recommendation matching the evidence; its statements about no commit describe coder handoff history, not the present committed state.

Only this review was written in the original repository. No implementation, phase document, progress entry or unrelated work was changed; no commit or push was performed.

## Fresh independent gates

Ran sequentially from the isolated repository root with its existing `.venv/bin/python` and clone PYTHONPATH. Requested execution permission for the known synthetic localhost-binding requirement before the full check; the permitted run succeeded. This review had no failed sandbox run. The coder's earlier sandbox/DNS failures below are historical environment evidence, not fresh failures or implementation defects. No dependency installation was needed for review.

| Command | Fresh observation |
|---|---|
| `.venv/bin/python scripts/check.py --first scripts --workers 4 --durations 20` | exit 0; selected scripts: `100 passed in 2.45s`; full: `4371 passed in 116.70s (0:01:56)`; no failures, skips, xfails or warnings summary; `All checks passed.` |
| `.venv/bin/python -m coverage json -o /tmp/phase47b-review-fresh-coverage.json` | immediately after full check, exit 0; `Wrote JSON report to /tmp/phase47b-review-fresh-coverage.json` |
| `.venv/bin/python -m pytest tests/unit/test_check_parallel.py --no-cov` | exit 0; `7 passed in 1.04s` |

Full-run section table:

```text
Sections:
  migrations    184 passed    0 failed    0 skipped
  scripts       100 passed    0 failed    0 skipped
  web           888 passed    0 failed    0 skipped
  cli           460 passed    0 failed    0 skipped
  mcp           198 passed    0 failed    0 skipped
  parsers       853 passed    0 failed    0 skipped
  sync          284 passed    0 failed    0 skipped
  core         1404 passed    0 failed    0 skipped
```

Last ten check lines:

```text
  core         1404 passed    0 failed    0 skipped
== critical coverage

Summary:
  lint: passed
  format: passed
  tests (scripts): passed
  tests: passed
  critical coverage: passed
All checks passed.
```

Fresh coverage measures 199 files at 99.98479434349578%; every critical module has zero missing lines and branches. Independently compared the fresh measured-file set and each file's missing-line and missing-branch-pair sets against the saved serial matrix report: exact equality. No invented application/script coverage target was imposed. Full fresh output is retained at `/tmp/phase47b-review-fresh.log` and exported coverage at the path above. No independent probe is specified.

## Inspected coder matrix and evidence reuse

The guide explicitly permits inspecting the coder serial/two/four-worker matrix instead of repeating serial and two-worker full acceptance when bytes/environment match and fresh evidence agrees. Applied that permission only to those historical matrix runs; the independent four-worker gate above was fresh.

Inspected `/tmp/finances-47b-evidence-c8ec721`: snapshot.json, collection helpers/inventories, benchmark.py, compare.py, all three complete logs, and each workers-W directory's timing.json, JUnit and original/exported coverage JSON. Independently recomputed comparisons rather than relying on comparison.json or test counts alone. The harness calls the unchanged runner and main injection interface, preserves reports after actual subprocess completion and records actual subprocess exit codes. All matrix commands and subprocesses exited 0; each full log ends `All checks passed.` and contains no warnings summary. Selected-first scripts has 100 passing cases in each run.

| Historical workers | Full passed | Command wall (s), documented | Main wall (s), saved timer | Pytest full step (s), log |
|---:|---:|---:|---:|---:|
| 1 | 4371 | 284.31 | 284.27 | 275.51 |
| 2 | 4371 | 162.60 | 162.54 | 154.63 |
| 4 | 4371 | 100.21 | 100.17 | 91.78 |

Both saved complete collection inventories contain the same ordered 4,371 node IDs. Independently converted node IDs to JUnit classname/name identities without splitting parameter text containing `::`; Counters match every full-run JUnit identity and multiplicity for all three runs. All testcase outcomes pass. Each immediate persistent coverage export matches its original pytest report. All three runs measure the same 199 files, identical missing-line and missing-branch sets and the same 99.98479434349578% coverage. Every critical module's missing sets are empty. The only missing lines are existing finances/__init__.py lines 5 and 6; no branches are missing. Fresh coverage agrees exactly.

Verified all five snapshot file hashes and the documented dirty source/test/config digest `529342c8032e08480cfda283eb9f6613da20cf4ad128a7fa7305a3c4f86cdb65` against current bytes. Also compared every tracked source/test/script/config file against the retained coder checkout, not merely those five changed paths. All matched. The entire installed distribution inventory matches snapshot.json, as do Python 3.12.16 and macOS-27.2.1-arm64-arm-64bit. Relevant packages include pytest 9.1.1, pytest-xdist 3.8.0, execnet 2.1.2, pytest-cov 7.1.0 and coverage 7.16.2. The same machine and linked venv are used; unchanged fixtures isolate settings, terminal variables, memory Keychain, temporary DBs and deterministic Hypothesis behavior. Import provenance is explicitly corrected for the review clone. No source/dependency/config/environment discrepancy or outcome/coverage disagreement requires repeating serial/two-worker checks under the guide.

The benchmark document records machine CPU/memory, exact commands and baseline, report retention, timing boundaries and package inventory. Its recommendation follows the rule: four workers are fastest and more than 10% faster than two; serial remains the default. The observed 2.84x speedup is measured guidance, not an acceptance promise. The fresh four-worker time differs from the historical timing without any identity/coverage discrepancy; background load was not controlled, as the document acknowledges. Setup/call/teardown examples are supported by the logged top-20 entries, and the document correctly limits its migration observation to a future profiling/design experiment rather than claiming aggregate migration cost or safe caching.

The coder recorded package-index DNS and ten sandbox localhost-bind errors, then successful permitted setup/baseline/matrix runs. These are resolved environment restrictions. No tests were dropped, weakened or edited to address them.

## Requirements and meaningful assertions

| Requirement | Deciding tests / inspected behavior |
|---|---|
| R1 | Given `test_invalid_workers_are_usage_errors[zero/negative/auto]`; coder `test_positive_workers_accepted`, `test_invalid_options_launch_nothing` assert accepted flags, usage exit 2, exact diagnostics and zero launched commands. |
| R2 | Given `test_workers_reach_both_test_steps[two/four]`, `test_default_stays_serial`, `test_section_forwards_workers_and_durations`; coder `test_flags_reach_first_and_full_only`, `test_section_can_time_serial_tests` check full/first/section forwarding and unchanged real-sample commands. Trace through `_pytest_options`, `steps`, `_run_one_section`, main and actual subprocess runner confirms only local load workers. |
| R3 | Coder `test_invalid_options_launch_nothing`, `test_explicit_zero_durations_omits_flag`, `test_flags_reach_first_and_full_only` and given section case assert validation and flag presence/absence. |
| R4 | Coder `test_failed_first_prevents_full_tests`, `test_pytest_failure_or_worker_crash_stops_coverage[1/2/3/4]`, `test_missing_or_malformed_coverage_fails`, `test_invalid_coverage_counts_cannot_pass` and `test_parallel_reports_root_interpreter_cleanup_and_summary` assert fail-fast behavior, refusal of PASS, tallies, cwd/interpreter, report cleanup and exact suffix. Existing serial pins are unchanged and pass. Critical coverage malformed-data handling fails closed. |
| R5 | Complete historical collection/JUnit identity/multiplicity/outcome and coverage-set comparisons, plus fresh independent four-worker full run and matching coverage. No omissions, skips, xfails or warnings. |
| R6 | Sequential historical matrix logs/timers, original and exported coverage, full version snapshot and byte comparisons; fresh results agree on functional/coverage evidence. |
| R7 | Timing table and actual slowest setup/call/teardown entries support four-worker selection and appropriately bounded fixture follow-up. |
| R8 | Testing and conventions document focused no-coverage development, unchanged --first semantics, full handoff and independent checks, fresh gates on code/config/dependency changes, and narrowly authorized reassessment reuse. No automatic result caching or PASS path added. |
| R9 | One fresh coverage job in the isolated checkout; four workers total for this review; documentation specifies machine-wide budget and one coordinated coverage run per checkout. Existing temporary file/database isolation and port-0 localhost fixtures were inspected; full matrix demonstrates actual isolation. No existing-test repair was needed. |

There are seven given and 27 coder cases: 4337 + 7 + 27 = 4371. Assertions check command construction, errors, persisted report lifecycle and gate outcomes, rather than merely running lines. No fixture cache, property-example reduction, test deletion, application change, remote worker or runtime dependency was introduced.

## Scratch-only mutation checks

Copied scripts/tests/config into disposable scratch directories, left reviewed source unchanged, and ran each exact named given case with `--no-cov`. Each mutation was independent:

| Mutation | Deciding given case | Fresh broken result |
|---|---|---|
| steps ignores workers and omits -n | `test_workers_reach_both_test_steps[two]` | exit 1 at required flag lookup: `ValueError: '-n' is not in list` |
| section path drops --durations | `test_section_forwards_workers_and_durations` | exit 1, assertion for `--durations=20` fails |
| generic invalid-worker diagnostic | `test_invalid_workers_are_usage_errors[zero]` | exit 1, required diagnostic assertion fails |

Unmodified given cases pass in the fresh seven-case run. A first scratch harness expectation incorrectly required AssertionError for the omitted worker flag; the test actually detects it via ValueError at its flag lookup. Corrected only that external harness expectation and reran all three checks successfully. This was a verification-harness issue, not a source or test defect. Scratch directories cleaned up normally; logs are `/tmp/phase47b-review-mutation-{workers,durations,diagnostic}.log`.

## Result

PASS for the exact reviewed commit and bytes above. No remaining baseline, environment, scope or implementation blocker. Historical matrix evidence is retained as coder evidence; fresh independent acceptance, coverage export, given cases and mutation observations are identified separately. Only this review is delivered.
