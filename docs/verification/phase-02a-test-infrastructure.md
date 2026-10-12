# Verify Phase 2a: Test infrastructure and coverage gate

Spec: `docs/phases/phase-02a-test-infrastructure.md`

Do not modify any file in the repository. Report findings only. The work under review is normally uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

## 1. Gates

Run each command on its own line.

| Command | Expected |
|---|---|
| `pip install -e ".[dev]"` | succeeds |
| `ruff check .` | no problems |
| `ruff format --check .` | no files would be reformatted |
| `pytest` | exit code 0, at least 16 tests passed, 0 skipped, 0 xfailed, coverage table printed, `TOTAL` at least 85% |

Record the test count and the `TOTAL` percentage in your report.

## 2. Scope audit

- `git status --short` lists only: `pyproject.toml`, `tests/conftest.py`, `tests/unit/test_diagnostics.py`, `tests/unit/test_config.py`, `tests/e2e/test_cli.py`, `docs/progress.md`. Report every other path.
- `git diff HEAD -- src` is empty. Any change under `src/` is a FAIL.
- `git diff HEAD -- tests/unit/test_config.py tests/e2e/test_cli.py tests/unit/test_log.py` contains no removed lines (lines starting with `-`, other than the `---` file header). Existing tests must be untouched.
- `git diff HEAD -- pyproject.toml` changes only: one added line in the `dev` list, one added `addopts` line, and the new `[tool.coverage.report]` section. No change to `dependencies`, `[tool.ruff]`, or the build system.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | dev dependency | read `pyproject.toml` | `dev` list contains `"pytest-cov>=5"`, `"pytest>=8"`, `"ruff>=0.5"` and nothing else |
| R2 | pytest options | read `pyproject.toml` | `testpaths = ["tests"]` and `addopts` equals `"--import-mode=importlib --cov=finances --cov-branch --cov-report=term-missing"` character for character |
| R3 | coverage gate | read `pyproject.toml` | `[tool.coverage.report]` has `fail_under = 85` and `show_missing = true`; there is no `omit`, `exclude_lines`, or `exclude_also` setting anywhere |
| R4 | fixture | read `tests/conftest.py` | one fixture named `tmp_settings`; it deletes the four `FIN_` variables, calls `monkeypatch.chdir(tmp_path)`, sets `FIN_DATA_DIR` to `tmp_path / "data"`, clears the settings cache before the `yield` and after it, and yields `get_settings()` |
| R5 | diagnostics tests | read `tests/unit/test_diagnostics.py` | the five tests named in the spec exist, each requests `tmp_settings`, and each makes the assertions in the spec table |
| R5 | version patch | search the test file for `version_info` | the only patch target is the `sys` attribute of `finances.diagnostics`; `sys.version_info` itself is never assigned or patched |
| R6 | config tests | read `tests/unit/test_config.py` | `test_mask_url_keeps_port` and `test_mask_url_ipv6_host` exist and compare with `==` against the exact strings in the spec |
| R7 | CLI test | read `tests/e2e/test_cli.py` | `test_doctor_exits_1_when_a_check_fails` patches `finances.cli.main.run_checks`, asserts exit code 1 and `"Probe"` in stdout |
| R8 | coverage reached honestly | `git grep -n "pragma: no cover"` | no matches outside `docs/` |

## 4. Independent probes

These confirm the gate is real and the fixture isolates tests. They change nothing in the repository.

| Probe | Command | Pass when |
|---|---|---|
| Gate fails when coverage is low | `pytest tests/unit/test_log.py` | tests pass but the run exits non-zero with a message that total coverage is below 85 |
| A single new test can be selected | `pytest tests/unit/test_diagnostics.py::test_python_version_too_old --no-cov` | 1 passed |
| Tests do not write to the real data dir | note whether `data/` exists and what it holds, run `pytest`, check again | `pytest` neither creates `data/` nor adds or modifies a file in it (`data/samples/` may already exist) |
| Order independence | `pytest tests/e2e tests/unit --no-cov` | all pass with the folders in this reversed order |

If `pytest` leaves a `.coverage` file in the repository root, delete it before the scope audit; it is a tool artifact, not a finding.

## 5. Test quality

- No test contains `assert True`, a bare `pytest.raises(Exception)`, `pytest.skip`, `skip`, or `xfail`.
- `test_python_version_too_old` asserts the whole tuple `("Python version", False, "3.10.0 FAIL")`, not only the boolean.
- `test_data_dir_unwritable` builds the unwritable path by placing the data dir under a regular file. It does not use `chmod` (which behaves differently on Windows) and does not mock `Path.mkdir`.
- All values are synthetic. The only URL credentials are `user` and `secret`.

## 6. Project rules that apply to this phase

- **No network.** `git grep -n -E "import (requests|httpx|urllib3|socket|aiohttp)" -- tests` returns nothing.
- **No real data.** `git status --short` shows no file under `data/` and no `.pdf`, `.csv`, or `.ofx` file.
- **Right layer** (`docs/testing.md`): diagnostics and config tests in `tests/unit/`, the CLI test in `tests/e2e/`.

## 7. Progress log

`docs/progress.md` ends with an entry headed `## Phase 2a: Test infrastructure and coverage gate (YYYY-MM-DD)` that records the `TOTAL` coverage. If it lists extra tests added under R8, confirm each exists and sits in the test file matching its module. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`
