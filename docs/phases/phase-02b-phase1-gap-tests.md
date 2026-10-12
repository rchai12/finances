# Phase 2b: Tests for Phase 1 gaps

## Goal

Three branches of the Phase 1 code have no test: `mask_url` with a port, `mask_url` with an IPv6 host, and `fin doctor` exiting with code 1. This phase adds one test for each. **This phase changes no production code.** The tests are given below in full; the work is to append them exactly and make the checks pass.

## Read first

- `AGENTS.md`
- `docs/progress.md`
- `tests/unit/test_config.py`, `tests/e2e/test_cli.py` (the two files you will append to)

## Starting state

- Phase 2a is done: `python -m pytest` ends with `13 passed` and total coverage `93.70%`.
- `tests/conftest.py` provides the `tmp_settings` fixture.
- `tests/unit/test_config.py` already imports `mask_url`. `tests/e2e/test_cli.py` already defines `runner` and imports `app`.

## Files

| Path | Action |
|---|---|
| `tests/unit/test_config.py` | append two tests at the end |
| `tests/e2e/test_cli.py` | append one test at the end |

Do not create or modify any other file, except `docs/progress.md`.

## Out of scope

- Anything under `src/`.
- The existing tests, imports, and fixtures in these two files. Do not edit, move, or delete a single existing line.
- `tests/conftest.py`, `tests/unit/test_diagnostics.py`, `pyproject.toml`.

## Dependencies

None new.

## Requirements

**R1.** Append exactly this to the end of `tests/unit/test_config.py`, separated from the last existing test by two blank lines:

```python
def test_mask_url_keeps_port() -> None:
    masked = mask_url("postgresql://user:secret@host:5432/db")
    assert masked == "postgresql://user:***@host:5432/db"


def test_mask_url_ipv6_host() -> None:
    masked = mask_url("postgresql://user:secret@[::1]:5432/db")
    assert masked == "postgresql://user:***@[::1]:5432/db"
```

**R2.** Append exactly this to the end of `tests/e2e/test_cli.py`, separated from the last existing test by two blank lines:

```python
def test_doctor_exits_1_when_a_check_fails(monkeypatch, tmp_settings) -> None:
    monkeypatch.setattr(
        "finances.cli.main.run_checks",
        lambda settings: [("Probe", False, "bad FAIL")],
    )

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "Probe" in result.stdout
```

**R3.** Add no import. Both files already import everything these tests use.

**R4.** Copy the blocks unchanged. These tests pass against the existing code. If one fails, the copy is wrong: compare it with the block again. Do not edit `src/` to make a test pass.

**R5.** `python -m pytest` ends with `16 passed` and the line `Required test coverage of 85.0% reached. Total coverage: 98.43%`. In the coverage table, `src/finances/config.py` and `src/finances/cli/main.py` both show `100%`.

## Work order

Activate the virtual environment first, so `python` is the project's interpreter. Run each command on its own line. Do not start a step until the check of the previous step passes.

1. Append the R1 block to `tests/unit/test_config.py`.
   Check: `python -m pytest tests/unit/test_config.py --no-cov` ends with `6 passed`.
2. Append the R2 block to `tests/e2e/test_cli.py`.
   Check: `python -m pytest tests/e2e/test_cli.py --no-cov` ends with `3 passed`.
3. Run `python -m ruff format .` and then `python -m ruff check --fix .`.
   Check: `git status --short` lists only the two files of this phase. If the formatter changed another file, undo that change.
4. Append the entry to `docs/progress.md` using its template, with the heading `## Phase 2b: Tests for Phase 1 gaps (YYYY-MM-DD)` and today's date. Under "Built", record the total coverage percentage.

## Before you stop

Every item must be true. If one is not, fix it and run the whole list again.

- [ ] `python -m ruff check .` prints `All checks passed!`
- [ ] `python -m ruff format --check .` reports no file to reformat
- [ ] `python -m pytest` ends with `16 passed` (exactly 16: the 13 from Phase 2a plus 3 new)
- [ ] In the coverage table, `src/finances/config.py` and `src/finances/cli/main.py` show `100%`
- [ ] `git status --short` lists exactly these three paths and nothing else: `tests/unit/test_config.py`, `tests/e2e/test_cli.py`, `docs/progress.md`
- [ ] `git diff HEAD -- tests` shows only added lines (no line starting with a single `-`)
- [ ] `docs/progress.md` ends with the `## Phase 2b: Tests for Phase 1 gaps` entry, with all three template lines filled in
