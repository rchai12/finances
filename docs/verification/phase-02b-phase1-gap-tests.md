# Verify Phase 2b: Tests for Phase 1 gaps

Spec: `docs/phases/phase-02b-phase1-gap-tests.md`

Do not modify any file in the repository. Report findings only. The work under review is normally uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The spec gives the three tests verbatim, so most of this guide is comparison, not judgment.

## 1. Gates

Activate the virtual environment first, then run each command on its own line.

| Command | Expected |
|---|---|
| `python -m ruff check .` | `All checks passed!` |
| `python -m ruff format --check .` | no files would be reformatted |
| `python -m pytest` | exit code 0, exactly `16 passed`, 0 skipped, 0 xfailed, and the line `Required test coverage of 85.0% reached. Total coverage: 98.43%` |

In the coverage table, `src/finances/config.py`, `src/finances/cli/main.py`, and `src/finances/diagnostics.py` must each show 100%. The only expected gap is `src/finances/__init__.py` lines 5-6.

## 2. Scope audit

- `git status --short` lists exactly: `tests/unit/test_config.py`, `tests/e2e/test_cli.py`, `docs/progress.md`. Report every other path as a finding.
- `git diff HEAD -- src pyproject.toml tests/conftest.py tests/unit/test_diagnostics.py tests/unit/test_log.py` is empty.
- `git diff HEAD -- tests` contains no removed line (a line starting with `-`, other than the `---` file headers). Existing tests must be untouched.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | config tests | `git diff HEAD -- tests/unit/test_config.py` | the added lines are the R1 block from the spec, at the end of the file, and nothing else is added |
| R2 | CLI test | `git diff HEAD -- tests/e2e/test_cli.py` | the added lines are the R2 block from the spec, at the end of the file, and nothing else is added |
| R3 | no new import | the same two diffs | no added line starts with `import` or `from` |
| R4 | nothing bent to fit | read the three new tests | the two `mask_url` tests compare with `==` against the full expected string; the CLI test patches `finances.cli.main.run_checks` and asserts `exit_code == 1`; no `skip`, `xfail`, or `assert True` |
| R5 | counts | gate output from section 1 | exactly `16 passed`, total coverage `98.43%` |

For each comparison, report every differing line with its line number.

## 4. Independent probes

| Probe | Command | Pass when |
|---|---|---|
| Config tests alone | `python -m pytest tests/unit/test_config.py --no-cov` | `6 passed` |
| CLI tests alone | `python -m pytest tests/e2e/test_cli.py --no-cov` | `3 passed` |
| Reversed folder order | `python -m pytest tests/e2e tests/unit --no-cov` | `16 passed` |
| The new CLI test does not leak its patch | `python -m pytest tests/e2e/test_cli.py::test_doctor_exits_1_when_a_check_fails tests/e2e/test_cli.py::test_doctor_creates_data_dir --no-cov` | `2 passed` |

## 5. Project rules that apply to this phase

- **No coverage exclusions.** `git grep -n -E "pragma: no cover|exclude_lines|exclude_also|omit" -- pyproject.toml src tests` returns nothing.
- **Synthetic data only.** The only credentials in the new tests are `user` and `secret`, and the only hosts are `host` and `[::1]`.

## 6. Progress log

`docs/progress.md` ends with an entry headed `## Phase 2b: Tests for Phase 1 gaps (YYYY-MM-DD)`, with "Built", "Deviations", and "Follow-ups" filled in and the total coverage recorded. Earlier entries, including Phase 2a, are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`
