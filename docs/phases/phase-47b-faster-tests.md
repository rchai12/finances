# Phase 47b: faster test execution

## Goal

Run the existing acceptance suite across a bounded number of local worker processes,
with useful timing output and measured guidance for this machine. Preserve test
coverage and independent verification.

**Owner decisions (2026-11-15):** prioritize testing speed as 47b, split only if
needed, and move the remaining audit phases later.
**Architect decisions:** one bounded phase; opt-in workers, serial default;
measure before fixture optimization. No template-database cache or evidence-cache
implementation in this phase.

## Read first

AGENTS.md, docs/architecture.md, docs/testing.md, docs/phase-conventions.md,
docs/audit-remediation-design.md, scripts/check.py, tests/unit/test_check_script.py,
tests/unit/test_sections.py (if present), tests/sections.toml, tests/conftest.py.

## Starting state and checked facts

Predecessor: **47a approved and committed**. Its current progress records
4,337 passing tests, but its latest original-workspace review is FAIL for mixed
scope, not a functional defect. Do not begin implementation until that finding
is resolved. Record the actual predecessor full-suite count as N; 4,337 is the
expected count, not permission to ignore a different reviewed baseline.
**Sections: scripts.** Migration remains 0026_proposal_findings.py.

check.py executes subprocesses serially; --first repeats selected tests before
the full run. pytest config enables branch coverage by default. pytest-cov 7.1.0
is installed; pytest-xdist is absent. db_engine migrates a fresh database per test;
its contribution to runtime has not been measured. The 47a review reports the
full tests step at 273.50 seconds; this is context, not a benchmark guarantee.

Official references: [xdist local workers](https://pytest-xdist.readthedocs.io/en/latest/distribution.html)
and [pytest-cov distributed coverage](https://pytest-cov.readthedocs.io/en/stable/xdist.html).
Use local subprocess workers and the load scheduler; no remote workers or network
execution. A coordinated pytest-cov run aggregates worker coverage.

## Scope

| Path | What changes |
|---|---|
| scripts/check.py | worker and duration options, existing execution paths |
| pyproject.toml | development dependency only |
| tests/sections.toml | assign the two new test files to scripts |
| tests/unit/test_check_parallel.py | new: given below |
| tests/unit/test_check_parallel_behavior.py | new: coder tests below |
| docs/testing.md | options, focused development loop, concurrency budget |
| docs/phase-conventions.md | optional worker/duration flags; bounded rerun clarification |
| docs/testing-performance.md | new: benchmark evidence and selected worker recommendation |
| docs/progress.md | implementation entry |

Existing tests remain unchanged. In particular test_check_script.py pins exact
serial commands and summary suffixes. Do not remove these pins to accommodate flags.

## Out of scope

Application code, migrations, fixture scope/caching, Hypothesis example reductions,
test removal/renaming, automatic affected-test selection, result caching, remote
execution, changing the serial default, or weakening any coverage/verdict gate.

## Dependencies

Add `pytest-xdist>=3.6,<4` to the dev optional dependencies. This spec authorizes
installing that dependency and its required dependencies into the existing venv,
using `.venv/bin/python -m pip install 'pytest-xdist>=3.6,<4'`. Do not reinstall
all project packages or create a venv. If network/package access is unavailable,
report that environment blocker; never silently fall back to serial execution.

## Design and requirements

- **R1.** Add `--workers W`, default 1, accepting positive integers only.
  Zero, negative, noninteger, and `auto` values exit 2 before launching a command;
  the diagnostic includes `--workers must be a positive integer`.
- **R2.** Extend `steps(python, coverage_json, *, real_samples, first=None,
  workers=1, durations=0)` retaining its existing result type. With workers > 1,
  append `-n W --dist load` to the selected-first and full pytest commands.
  Apply the same flags in --section mode. With 1 omit both flags, preserving
  existing serial commands. Do not parallelize lint/format, coverage inspection,
  real-sample checks, or separate acceptance invocations.
- **R3.** Add `--durations K`, default 0. Accept nonnegative integers; other values
  exit 2 before commands and include `--durations must be a nonnegative integer`.
  A positive value appends `--durations=K` to selected-first, full, and section
  pytest commands. Zero omits it. Real-sample commands remain unchanged.
- **R4.** Preserve fail-fast step ordering, summary suffixes, interpreter/cwd,
  section tallies, temporary JSON/JUnit reports, persistent coverage data used by
  subsequent coverage commands, and real-sample opt-in behavior. A worker crash,
  collection failure or plugin failure must fail acceptance; never reinterpret
  it as a successful smaller run. Missing/malformed coverage cannot produce PASS.
- **R5.** All tests still run, with the same identities and outcomes, under serial,
  2-worker and 4-worker full runs. Keep overall coverage >=85% and every listed
  critical line/branch covered. No new skips/xfails or warnings. Do not replace
  these gates with test-count agreement alone.
- **R6.** Benchmark the final implementation sequentially at 1, 2 and 4 workers,
  with `--durations 20`. Record total command wall time and pytest-reported full
  tests-step time, counts, actual package/Python versions, machine CPU/memory,
  exact commands/revision and a digest of dirty source/test/config contents.
  Save each coverage JSON before the next run and compare measured file sets,
  missing line sets and missing branch sets, not execution counts. Normalize only
  absolute root prefixes. Document any difference; do not waive R5.
- **R7.** In docs/testing-performance.md record the slowest setup/call/teardown
  items from timing output and whether repeated migration setup merits a later
  fixture design. Choose the fastest measured worker count as a recommendation;
  if differences are within 10%, recommend the lower count. Report an inconclusive
  comparison honestly and repeat only the affected pair if needed. Speedup is
  measured, never a guaranteed acceptance ratio. The default remains 1.
- **R8.** Document the development loop: focused files/--section with --no-cov,
  then required full acceptance at handoff and independent verification. Keep
  --first semantics. Source/test/dependency/config changes require fresh applicable
  gates. A scope/document-only reassessment may reuse explicit prior evidence
  only when the owner authorizes narrowing and tested bytes and relevant
  environment match. No automatic PASS or cross-coder/verifier result reuse.
- **R9.** Document one coordinated coverage run per checkout at a time. Multiple
  checkouts have separate coverage artifacts and share a machine-wide worker
  budget; do not give each agent all cores. Inspect existing tests for fixed
  shared filenames/ports before the first parallel run. Resolve infrastructure
  failures explicitly; any required existing-test repair outside Scope returns
  to the architect. Never weaken assertions or silently drop unsafe tests.

Private helpers are coder-owned. No new public application API. Argparse validation
may be implemented with a private converter; direct steps() callers supply valid
integers. Current main(argv=None, run=run_command) injection remains compatible.

## Given tests

Seven collected cases in one file, unchanged when copied. The default-serial case
is a characterization guard. The other six fail on the current runner for missing
kwargs/options or the missing specific validation diagnostic. They were linted,
formatted and run in an isolated clone; no feature or stub implementation was made.

`tests/unit/test_check_parallel.py`

```python
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def check():
    path = Path(__file__).resolve().parents[2] / "scripts/check.py"
    spec = importlib.util.spec_from_file_location("parallel_check_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("workers", [2, 4], ids=["two", "four"])
def test_workers_reach_both_test_steps(check, tmp_path, workers):
    steps = check.steps(
        "/py",
        tmp_path / "coverage.json",
        real_samples=True,
        first=["scripts"],
        workers=workers,
    )
    tests = [step.command for step in steps if step.name.startswith("tests")]
    assert len(tests) == 2
    for command in tests:
        assert command[command.index("-n") + 1] == str(workers)
        assert command[command.index("--dist") + 1] == "load"
    assert "-n" not in steps[-1].command


def test_default_stays_serial(check, tmp_path):
    steps = check.steps("/py", tmp_path / "coverage.json", real_samples=False)
    for step in steps:
        if step.command:
            assert "-n" not in step.command
            assert not any(arg.startswith("--durations") for arg in step.command)


@pytest.mark.parametrize("value", ["0", "-1", "auto"], ids=["zero", "negative", "auto"])
def test_invalid_workers_are_usage_errors(check, value, capsys):
    calls = []
    with pytest.raises(SystemExit) as stopped:
        check.main(["--workers", value], run=lambda cmd, cwd: calls.append(cmd) or 0)
    assert stopped.value.code == 2
    assert calls == []
    assert "--workers must be a positive integer" in capsys.readouterr().err


def test_section_forwards_workers_and_durations(check):
    calls = []
    assert (
        check.main(
            ["--section", "scripts", "--workers", "2", "--durations", "20"],
            run=lambda cmd, cwd: calls.append(cmd) or 0,
        )
        == 0
    )
    assert len(calls) == 1
    command = calls[0]
    assert command[command.index("-n") + 1] == "2"
    assert command[command.index("--dist") + 1] == "load"
    assert "--durations=20" in command
    assert "--no-cov" in command
```

## Tests to write

In tests/unit/test_check_parallel_behavior.py (scripts section), use recording fake
runners and synthetic report data, without launching nested full suites:

- R1/R3: positive workers accepted; durations -1 and text refused with diagnostic
  and zero calls; explicit zero durations adds no flag.
- R2/R3: full and --first commands carry both flags with workers=4,durations=20;
  --section workers=1 stays serial; real samples never acquire either flag.
- R4: first-step failure prevents full tests; pytest exit 1 and simulated worker
  crash exit 3 prevent critical coverage and return nonzero. Missing/malformed
  coverage must fail rather than print All checks passed.
- R4: synthetic multi-section JUnit tallies remain correct; interpreter, root and
  final summary suffix stay unchanged with flags enabled.

No given migration, earlier-test diff or independent probe. Real parallel isolation
and coverage aggregation are established by the acceptance matrix, not mocks.

## Rules for this phase

No runtime network or real data. Synthetic suite only. Install is a development
setup operation, not app network behavior. Keep tests/conftest.py unchanged.
Standard phase conventions apply except the explicit scripts-only coverage
exception: scripts/check.py is outside --cov=finances; no artificial 100% application
module target is added. Existing critical and overall gates remain mandatory.

## Acceptance

After dependency setup, run these full checks **sequentially** with logs and actual
exit codes preserved (do not hide failures through a tail/tee pipeline):

1. `.venv/bin/python scripts/check.py --first scripts --workers 1 --durations 20`
2. Immediately preserve that run's data with `.venv/bin/python -m coverage json -o /tmp/finances-47b-serial-coverage.json`.
3. `.venv/bin/python scripts/check.py --first scripts --workers 2 --durations 20`
4. Immediately `.venv/bin/python -m coverage json -o /tmp/finances-47b-two-coverage.json`.
5. `.venv/bin/python scripts/check.py --first scripts --workers 4 --durations 20`
6. Immediately `.venv/bin/python -m coverage json -o /tmp/finances-47b-four-coverage.json`.
7. `.venv/bin/python -m pytest tests/unit/test_check_parallel.py --no-cov`: exactly 7 passed.

Each full check ends All checks passed.; every section has zero failures; tests
step has at least N+7 passes with no skips/xfails/warnings. Record coder tests in
addition. Compare complete node-id collections once serial and once with xdist
loaded (collection stays controller-local); use the actual full-run JUnit case
identities/multiplicities to prove each worker matrix run executed that inventory.
Preserve JUnit reports outside the repo by copying from the injected runner when
needed in a temporary invocation harness; do not change default cleanup behavior.
Use unique temporary folders instead of the example /tmp filenames if they exist.
Inspect both new tests' section assignments. Scope is exactly the table; verifier
may additionally write docs/reviews/phase-47b-faster-tests.md. No new search gate.

## Report

Use phase-conventions.md format, headed Phase 47b: faster test execution. Record
N and final count, benchmark document, worker recommendation and blockers. No
commit/push. The finalized spec and predecessor must be committed before coding.
