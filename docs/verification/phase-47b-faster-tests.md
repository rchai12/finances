# Verify Phase 47b: faster test execution

Spec: docs/phases/phase-47b-faster-tests.md. Follow phase-conventions.md and its
report format. Only write docs/reviews/phase-47b-faster-tests.md.

## 1. Baseline and gates

Confirm 47a is approved/committed and this spec/guide match the committed planning
baseline. Inventory tracked and untracked changes before writing the report.
A mixed tree requires explicit isolation; report baseline defects separately.
N comes from the approved predecessor, expected 4337. Sections: scripts.

First run `.venv/bin/python scripts/check.py --first scripts --workers 4 --durations 20`
and immediately `.venv/bin/python -m coverage json -o /tmp/finances-47b-review-coverage.json`.
Use a fresh path if it exists. Require All checks passed., at least N+7 full-step
passes, no failed/skipped/xfailed tests or warnings; all section rows pass and all
critical coverage gates pass. Then run the given-file command in the spec:
exactly 7 passed. Inspect coder's serial/2/4-worker matrix logs, coverage-set
comparisons, inventory matching and timings. Independently rerun serial and
2-worker full checks only if the matrix evidence is missing, does not match
reviewed bytes/environment, or disagrees with fresh results. This explicit
matrix-evidence reuse reduces duplicate benchmarks; it does not replace your
fresh independent full 4-worker acceptance run.

No new application module coverage target: scripts are outside finances coverage.
Do not demand an invented 100% script coverage command. Current overall and
critical application coverage requirements remain in force.

## 2. Scope and given files

Use the spec's exact table plus this report. New tests match the embedded block;
all earlier tests and fixtures remain unchanged. Inspect pyproject.toml for only
the authorized dev dependency. Confirm two new files belong to scripts, not core.

## 3. Requirement checklist

| Requirement | Deciding evidence |
|---|---|
| R1 | given invalid worker matrix, positive cases, no command launched on invalid input |
| R2 | given two/four steps and section forwarding; coder serial-section and real-sample cases |
| R3 | given section duration; coder full/first and zero/invalid durations |
| R4 | coder exit/crash/coverage failure cases; old check-script tests unchanged; fresh summary |
| R5 | real serial/2/4 full-run identity and coverage comparison plus fresh 4-worker run |
| R6 | reproducible timing/version/environment/bytes evidence and preserved per-run coverage |
| R7 | measured recommendation and setup/call/teardown evidence, no unmeasured fixture claim |
| R8 | exact documented development/rerun rules, retained independent verification |
| R9 | local workers, explicit worker budget, no test exclusions or conflicting coverage jobs |

## 4. Probe

None. The actual full-suite worker matrix is the integration experiment. A mocked
runner proves command construction only. Serial vs parallel counts alone are
insufficient: inspect JUnit identities/multiplicities and missing coverage sets.

## 5. Coder tests and spot checks

Every Tests to write case requires an asserting test. Mutations run only in a
scratch copy; source under review stays unchanged.

| Exact mutation | Deciding given case | Correct | Broken |
|---|---|---|---|
| steps ignores workers and omits -n | test_workers_reach_both_test_steps[two] | -n 2 in both test commands | absent flag fails |
| section path drops --durations | test_section_forwards_workers_and_durations | --durations=20 | absent flag fails |
| main replaces invalid-worker diagnostic with generic invalid input | test_invalid_workers_are_usage_errors[zero] | required text | wrong text fails |

Trace flags to their launched commands, including --first and --real-samples.
Reasonable variations: private parsing/command helpers, temporary logs outside
repo, lower recommended worker count when measured faster. Serial default is
required. No fixed speedup is required; no weakening tests to manufacture one.

## 6. Out of scope and progress

No fixture/template DB cache, Hypothesis reduction, test deletion, runtime change,
auto result reuse, or new application dependency. Progress format is unchanged;
counts and benchmark recommendation match evidence. Report environment/plugin
failures distinctly from application failures. Never turn an incomplete parallel
run into PASS through its smaller count. Write the standard PASS/FAIL header and
requirement/location/expected/observed findings.
