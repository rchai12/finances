# Phase 10: Quality gates

## Goal

Make test quality measurable and enforced: stricter coverage for critical modules, mutation testing to show the tests actually catch bugs, a single check command, and git hooks. Optional CI for when the repo gets a remote.

## Read first

- `AGENTS.md`, `docs/testing.md` (especially "Critical modules")
- `docs/progress.md`

## Dependencies

Add dev: `cosmic-ray>=8`, `pre-commit>=3`

Why `cosmic-ray` and not `mutmut`: recent `mutmut` versions do not run natively on Windows. If `cosmic-ray` turns out to be unusable here, stop and report; the fallback is running `mutmut` inside WSL or Docker, which needs the user's decision.

## Deliverables

### 1. Per-module coverage gate (`scripts/check_coverage.py`)

- Reads `coverage.json` (`pytest --cov-report=json`).
- Fails if overall branch coverage < 85% or any module listed in `docs/testing.md` "Critical modules" (keep the list in one place: `scripts/critical_modules.txt`, and reference it from `testing.md`) is below 95%.
- Prints a short table: module, coverage, threshold, pass/fail.

### 2. Mutation testing (`scripts/mutation.ps1`, `mutation/cosmic-ray.toml`)

- Targets the modules in `scripts/critical_modules.txt`.
- Test command: only `tests/unit` and `tests/golden` with `-x -q -p no:cacheprovider` and **without** coverage (speed). Per-mutant timeout around 30 seconds.
- Session database under `data/mutation/` (gitignored, since it is under `data/`).
- The script runs init → exec → report and prints: total mutants, killed, survived, survival rate per module.
- **Threshold**: survival rate ≤ 15% per critical module. For each surviving mutant, either add a test that kills it or record it in `docs/mutation-exceptions.md` with a one-line reason (e.g. "equivalent mutant: `<=` vs `<` on a value that can never be equal"). Keep exceptions rare.
- Not part of normal `pytest` runs; run before tagging a version, and after changing a critical module.

### 3. One check command (`scripts/check.ps1`)

Runs in order, stopping at the first failure:
1. `ruff check .`
2. `ruff format --check .`
3. `pytest --cov-report=json` (unit, integration, e2e, golden)
4. `python scripts/check_coverage.py`
5. If `data/samples/` exists: the real-sample tests

Also provide `scripts/check.sh` with the same steps for Linux/WSL (the future cloud container).

### 4. Pre-commit hooks (`.pre-commit-config.yaml`)

- `ruff` (lint, with `--fix` off) and `ruff-format --check`.
- A local hook running `pytest tests/unit -q -x --no-cov` (fast).
- A local **privacy guard** hook: blocks the commit if any staged file is under `data/`, or has extension `.pdf`, `.csv`, `.ofx`, `.qfx` outside `tests/fixtures/`, or if a staged text file contains a run of 12 or more digits outside `tests/fixtures/` (likely an account number). Known synthetic numbers used in docs (e.g. the examples in `docs/statement-formats.md`) go in `scripts/privacy_allowlist.txt`, one exact string per line; do not exempt whole folders. Write it as a small Python script in `scripts/` with its own unit tests.
- Document `pre-commit install` in the root `README.md`.

### 5. Optional CI (`.github/workflows/ci.yml`)

Only matters once the repo has a GitHub remote. Windows and Ubuntu, Python 3.11 and 3.12: install, `ruff`, `pytest`, `check_coverage.py`, with `CI=1` (deterministic Hypothesis). **Never** runs real-sample tests (no data in CI) and never uses secrets. Mutation testing is not run in CI.

### 6. Fill the gaps

Run the gates. Raise coverage and kill surviving mutants in the critical modules until the thresholds pass. List what was added in `docs/progress.md`.

## Acceptance criteria

```powershell
.\scripts\check.ps1          # passes
.\scripts\mutation.ps1       # survival rate <= 15% for every critical module (or documented exceptions)
pre-commit run --all-files   # passes
```
Also demonstrate the privacy guard: staging a dummy `data/test.csv` (force-added) or a file containing `123456789012` is blocked. Then unstage and delete the dummy file.

Append your entry to `docs/progress.md`.
