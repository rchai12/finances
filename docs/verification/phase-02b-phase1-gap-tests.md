# Verify Phase 2b: Tests for Phase 1 gaps

Spec: `docs/phases/phase-02b-phase1-gap-tests.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The spec gives both test files verbatim, so most of this guide is comparison, not judgment.

## 1. Gates

Activate the virtual environment first, then run each command on its own line.

| Command | Expected |
|---|---|
| `python -m ruff check .` | `All checks passed!` |
| `python -m ruff format --check .` | `15 files already formatted` |
| `python -m pytest` | exit code 0, exactly `16 passed`, 0 skipped, 0 xfailed, and the line `Required test coverage of 85.0% reached. Total coverage: 98.43%` |

In the coverage table, `src/finances/config.py`, `src/finances/cli/main.py`, and `src/finances/diagnostics.py` must each show 100%. The only expected gap is `src/finances/__init__.py` lines 5-6.

## 2. Scope audit

- `git status --short` lists exactly: `docs/progress.md`, `pyproject.toml`, `tests/e2e/test_cli.py`, `tests/unit/test_config.py`. Report every other path as a finding.
- `git diff HEAD -- src tests/conftest.py tests/unit/test_diagnostics.py tests/unit/test_log.py` is empty. Any change under `src/` is a FAIL.
- `git diff HEAD -- tests` contains no removed line (a line starting with `-`, other than the `---` file headers). Existing tests must be untouched.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | `tests/unit/test_config.py` | compare the file with the R1 block in the spec | identical apart from trailing whitespace |
| R2 | `tests/e2e/test_cli.py` | compare the file with the R2 block | identical apart from trailing whitespace |
| R3 | `pyproject.toml` newline | run the command below this table | prints `True` |
| R3 | `pyproject.toml` otherwise unchanged | `git diff HEAD -- pyproject.toml` | the only change is the last line gaining its newline (the diff shows the same text removed and added, with `\ No newline at end of file` on the removed side) |
| R4 | nothing bent to fit | `git diff HEAD -- tests` | only the three new tests are added; no added `import`, `skip`, `xfail`, or `assert True` |
| R5 | counts | gate output from section 1 | exactly `16 passed`, total coverage `98.43%` |

`python -c "from pathlib import Path; print(Path('pyproject.toml').read_bytes().endswith(b'\n'))"`

For each comparison, report every differing line with its line number.

## 4. Independent probes

| Probe | Command | Pass when |
|---|---|---|
| Config tests alone | `python -m pytest tests/unit/test_config.py --no-cov` | `6 passed` |
| CLI tests alone | `python -m pytest tests/e2e/test_cli.py --no-cov` | `3 passed` |
| Reversed folder order | `python -m pytest tests/e2e tests/unit --no-cov` | `16 passed` |
| The new CLI test does not leak its patch | `python -m pytest "tests/e2e/test_cli.py::test_doctor_exits_1_when_a_check_fails" "tests/e2e/test_cli.py::test_doctor_creates_data_dir" --no-cov` | `2 passed` |
| The package still installs | `python -m pip install -e ".[dev]"` | succeeds |

## 5. Project rules that apply to this phase

- **No coverage exclusions.** `git grep -n -E "pragma: no cover|exclude_lines|exclude_also|omit" -- pyproject.toml src tests` returns nothing.
- **Synthetic data only.** The only credentials in the new tests are `user` and `secret`, and the only hosts are `host` and `[::1]`.

## 6. Progress log

`docs/progress.md` ends with the entry given in step 5 of the spec's work order, with a real date in place of `YYYY-MM-DD`. Earlier entries, including Phase 2a, are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

## If the verdict is FAIL

A repair sent back to the coder is either the instruction to replace a whole file with a block from the spec, or a single command to run. Do not describe an edit in a sentence.
