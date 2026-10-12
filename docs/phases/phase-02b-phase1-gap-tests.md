# Phase 2b: Tests for Phase 1 gaps

## Goal

Three branches of the Phase 1 code have no test: `mask_url` with a port, `mask_url` with an IPv6 host, and `fin doctor` exiting with code 1. This phase adds one test for each, and adds the final newline that `pyproject.toml` is missing. **This phase changes no production code.** Both test files are given below in full: the existing tests, unchanged, followed by the new ones.

## Read first

- `AGENTS.md`
- `docs/progress.md`

## Starting state

- Phase 2a is done and committed. `git status --short` prints nothing.
- `python -m pytest` ends with `13 passed` and total coverage `93.70%`.
- `pyproject.toml` is correct except that its last line has no newline character after it.

## Files

| Path | Action |
|---|---|
| `tests/unit/test_config.py` | replace whole content |
| `tests/e2e/test_cli.py` | replace whole content |
| `pyproject.toml` | run one command (step 3). Do not edit it by hand |

Do not create or modify any other file, except `docs/progress.md`.

## Out of scope

- **Anything under `src/`.** Do not edit, add, or tidy production code, not even an import.
- `tests/conftest.py`, `tests/unit/test_diagnostics.py`, `tests/unit/test_log.py`.
- **Git commands that discard work:** never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`. They undo correct work in other files. A mistake in one file is fixed by editing that file.

## Dependencies

None new.

## Requirements

**R1.** `tests/unit/test_config.py` has exactly this content:

```python
from pathlib import Path

import pytest

from finances.config import get_settings, mask_url

_ENV_KEYS = ("FIN_ENVIRONMENT", "FIN_DATA_DIR", "FIN_DATABASE_URL", "FIN_LOG_LEVEL")


@pytest.fixture(autouse=True)
def _clear_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults() -> None:
    settings = get_settings()
    assert settings.environment == "local"
    assert settings.effective_database_url.endswith("data/finances.db")


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIN_DATA_DIR", "custom-data")
    monkeypatch.setenv("FIN_DATABASE_URL", "postgresql://user:secret@host/db")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.data_dir == Path("custom-data")
    assert settings.effective_database_url == "postgresql://user:secret@host/db"


def test_mask_url_hides_password() -> None:
    masked = mask_url("postgresql://user:secret@host/db")
    assert "secret" not in masked
    assert "***" in masked


def test_mask_url_without_password_is_unchanged() -> None:
    url = "sqlite:///data/finances.db"
    assert mask_url(url) == url


def test_mask_url_keeps_port() -> None:
    masked = mask_url("postgresql://user:secret@host:5432/db")
    assert masked == "postgresql://user:***@host:5432/db"


def test_mask_url_ipv6_host() -> None:
    masked = mask_url("postgresql://user:secret@[::1]:5432/db")
    assert masked == "postgresql://user:***@[::1]:5432/db"
```

**R2.** `tests/e2e/test_cli.py` has exactly this content:

```python
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import get_settings

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_doctor_creates_data_dir(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "fin-data"
    monkeypatch.setenv("FIN_DATA_DIR", str(data_dir))
    get_settings.cache_clear()

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert data_dir.is_dir()
    get_settings.cache_clear()


def test_doctor_exits_1_when_a_check_fails(monkeypatch, tmp_settings) -> None:
    monkeypatch.setattr(
        "finances.cli.main.run_checks",
        lambda settings: [("Probe", False, "bad FAIL")],
    )

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "Probe" in result.stdout
```

**R3.** `pyproject.toml` ends with a newline character, and nothing else in it changes.

**R4.** Do not rename a test, drop a parameter, change an import, or change a value in the two blocks. These tests pass against the existing code. If one fails, the copy is wrong: replace the whole file with the block again. Do not edit `src/` to make a test pass.

**R5.** `python -m pytest` ends with `16 passed` and the line `Required test coverage of 85.0% reached. Total coverage: 98.43%`.

## Work order

Activate the virtual environment first, so `python` is the project's interpreter. Run each command on its own line. Do not start a step until every check of the previous step passes.

A block copied from this spec may end without a final newline. That is why each step runs the formatter on the file it just wrote: `ruff format` adds the newline. Never skip it.

1. Replace the whole content of `tests/unit/test_config.py` with the R1 block. Then run:
   `python -m ruff format tests/unit/test_config.py`
   Checks:
   - `python -m ruff format --check tests/unit/test_config.py` prints `1 file already formatted`
   - `python -m pytest tests/unit/test_config.py --no-cov` ends with `6 passed`
2. Replace the whole content of `tests/e2e/test_cli.py` with the R2 block. Then run:
   `python -m ruff format tests/e2e/test_cli.py`
   Checks:
   - `python -m ruff format --check tests/e2e/test_cli.py` prints `1 file already formatted`
   - `python -m pytest tests/e2e/test_cli.py --no-cov` ends with `3 passed`
3. Add the final newline to `pyproject.toml` by running this one command. Do not open the file in an editor.
   `python -c "from pathlib import Path; p = Path('pyproject.toml'); b = p.read_bytes(); p.write_bytes(b if b.endswith(b'\n') else b + b'\n')"`
   Check: `python -c "from pathlib import Path; print(Path('pyproject.toml').read_bytes().endswith(b'\n'))"` prints `True`
4. Run `python -m ruff check .`
   Check: it prints `All checks passed!`
5. Add this entry at the end of `docs/progress.md`, after one blank line. Copy it, and replace `YYYY-MM-DD` with today's date. If you did anything this spec did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 2b: Tests for Phase 1 gaps (YYYY-MM-DD)
- Built: three tests for untested Phase 1 branches (`mask_url` with a port, `mask_url` with an IPv6 host, `fin doctor` exit code 1), and the final newline of `pyproject.toml`. 16 tests pass. TOTAL coverage: 98.43%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None
```

## Before you stop

Every item must be true. If one is not, fix it by editing that file, then run the whole list again.

- [ ] `python -m ruff check .` prints `All checks passed!`
- [ ] `python -m ruff format --check .` prints `15 files already formatted`
- [ ] `python -m pytest` ends with `16 passed` (exactly 16: the 13 from Phase 2a plus 3 new)
- [ ] The `python -m pytest` output contains `Total coverage: 98.43%`
- [ ] `git status --short` lists exactly these four paths and nothing else: `docs/progress.md`, `pyproject.toml`, `tests/e2e/test_cli.py`, `tests/unit/test_config.py`
- [ ] `git diff HEAD -- src` prints nothing
- [ ] `docs/progress.md` ends with the `## Phase 2b: Tests for Phase 1 gaps` entry
