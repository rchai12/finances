# Verify Phase 2a: Coverage gate and shared fixture

Spec: `docs/phases/phase-02a-coverage-gate.md`

Do not modify any file in the repository. Report findings only. The work under review is normally uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The spec gives all three files verbatim, so most of this guide is comparison, not judgment.

## 1. Gates

Activate the virtual environment first, then run each command on its own line.

| Command | Expected |
|---|---|
| `python -m pip install -e ".[dev]"` | succeeds |
| `python -m ruff check .` | `All checks passed!` |
| `python -m ruff format --check .` | no files would be reformatted |
| `python -m pytest` | exit code 0, exactly `13 passed`, 0 skipped, 0 xfailed, and the line `Required test coverage of 85.0% reached. Total coverage: 93.70%` |

In the coverage table, `src/finances/diagnostics.py` must show 100%. `config.py` at 90% (lines 38 and 40 missing) and `cli/main.py` at 94% (line 39 missing) are expected here; Phase 2b covers them.

## 2. Scope audit

- `git status --short` lists exactly: `pyproject.toml`, `tests/conftest.py`, `tests/unit/test_diagnostics.py`, `docs/progress.md`. Report every other path as a finding.
- `git diff HEAD -- src` is empty. Any change under `src/`, even an unused import, is a FAIL.
- `git diff HEAD -- tests/unit/test_config.py tests/unit/test_log.py tests/e2e` is empty.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | `pyproject.toml` | compare the file with the R1 block in the spec | identical apart from trailing whitespace |
| R1 | diff is minimal | `git diff HEAD -- pyproject.toml` | the only changes are the added `"pytest-cov>=5",` line, the added `addopts` line, and the added `[tool.coverage.report]` section with its two settings |
| R2 | `tests/conftest.py` | compare with the R2 block | identical apart from trailing whitespace |
| R3 | `tests/unit/test_diagnostics.py` | compare with the R3 block | identical apart from trailing whitespace |
| R4 | nothing bent to fit | read both test files | every test requests `tmp_settings`; the version test patches `finances.diagnostics.sys` with a `SimpleNamespace` and never assigns or patches `sys.version_info`; no `skip`, `xfail`, or `assert True` |
| R5 | counts | gate output from section 1 | exactly `13 passed`, total coverage `93.70%` |

For each comparison, report every differing line with its line number.

## 4. Independent probes

These confirm the gate is real and the fixture isolates tests. They change nothing tracked in the repository.

| Probe | Command | Pass when |
|---|---|---|
| Gate fails when coverage is low | `python -m pytest tests/unit/test_log.py` | `2 passed`, then `FAIL Required test coverage of 85.0% not reached`, and a non-zero exit code |
| New tests alone | `python -m pytest tests/unit/test_diagnostics.py --no-cov` | `5 passed` |
| Reversed folder order | `python -m pytest tests/e2e tests/unit --no-cov` | `13 passed` |
| Tests do not touch the real data dir | note what `data/` holds (it may not exist), run `python -m pytest`, check again | nothing in `data/` was created or modified |

## 5. Project rules that apply to this phase

- **No coverage exclusions.** `git grep -n -E "pragma: no cover|exclude_lines|exclude_also|omit" -- pyproject.toml src tests` returns nothing.
- **No network.** `git grep -n -E "import (requests|httpx|urllib3|socket|aiohttp)" -- tests` returns nothing.
- **No real data.** `git status --short` shows no file under `data/` and no `.pdf`, `.csv`, or `.ofx` file.

## 6. Progress log

`docs/progress.md` ends with an entry headed `## Phase 2a: Coverage gate and shared fixture (YYYY-MM-DD)`, with "Built", "Deviations", and "Follow-ups" filled in and the total coverage recorded. A deviation that changes any of the three files is a FAIL. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`
