# Phase 2a: Coverage gate and shared fixture

## Goal

Every test run measures branch coverage and fails below 85%. A shared `tmp_settings` fixture exists for later phases, and `diagnostics.py` is fully tested. **This phase changes no production code.** All three files are given below in full; the work is to create them exactly and make the checks pass.

## Read first

- `AGENTS.md`
- `docs/testing.md`
- `docs/progress.md`

## Starting state

- 8 tests exist, in `tests/unit/test_config.py`, `tests/unit/test_log.py`, and `tests/e2e/test_cli.py`.
- `tests/conftest.py` and `tests/unit/test_diagnostics.py` may exist from an earlier attempt. If they do, replace their whole content with the blocks below.

## Files

| Path | Action |
|---|---|
| `pyproject.toml` | replace whole content |
| `tests/conftest.py` | create (or replace whole content) |
| `tests/unit/test_diagnostics.py` | create (or replace whole content) |

Do not create or modify any other file, except `docs/progress.md`.

## Out of scope

- Anything under `src/`. Do not edit, add, or "tidy" production code, not even an import.
- `tests/unit/test_config.py`, `tests/unit/test_log.py`, `tests/e2e/test_cli.py`. Phase 2b adds tests there.
- Money helpers, database code, CLI commands.

## Dependencies

One new development dependency: `pytest-cov>=5`. It is already in the `pyproject.toml` block below.

## Requirements

**R1.** `pyproject.toml` has exactly this content:

```toml
[project]
name = "finances"
version = "0.1.0"
description = "Local personal-finance tools for one household."
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "rich>=13",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "ruff>=0.5",
    "pytest-cov>=5",
]

[project.scripts]
fin = "finances.cli.main:app"

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"
extend-exclude = ["docs"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib --cov=finances --cov-branch --cov-report=term-missing"

[tool.coverage.report]
fail_under = 85
show_missing = true
```

**R2.** `tests/conftest.py` has exactly this content:

```python
from collections.abc import Iterator
from pathlib import Path

import pytest

from finances.config import Settings, get_settings

_ENV_KEYS = ("FIN_ENVIRONMENT", "FIN_DATA_DIR", "FIN_DATABASE_URL", "FIN_LOG_LEVEL")


@pytest.fixture
def tmp_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Settings]:
    """Settings whose data dir is under tmp_path, with no .env file in reach."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FIN_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()
```

**R3.** `tests/unit/test_diagnostics.py` has exactly this content:

```python
import collections
import types
from pathlib import Path

import pytest

import finances.diagnostics
from finances.config import Settings
from finances.diagnostics import run_checks

Version = collections.namedtuple("Version", "major minor micro")


def test_python_version_ok(tmp_settings: Settings) -> None:
    checks = run_checks(tmp_settings)
    assert checks[0][0] == "Python version"
    assert checks[0][1] is True
    assert "FAIL" not in checks[0][2]


def test_python_version_too_old(monkeypatch: pytest.MonkeyPatch, tmp_settings: Settings) -> None:
    fake_sys = types.SimpleNamespace(version_info=Version(3, 10, 0))
    monkeypatch.setattr(finances.diagnostics, "sys", fake_sys)
    checks = run_checks(tmp_settings)
    assert checks[0] == ("Python version", False, "3.10.0 FAIL")


def test_data_dir_ok(tmp_settings: Settings) -> None:
    checks = run_checks(tmp_settings)
    assert checks[2][0] == "Data dir"
    assert checks[2][1] is True
    assert checks[2][2].endswith(" OK")
    assert tmp_settings.data_dir.is_dir()
    assert not (tmp_settings.data_dir / ".fin_write_probe").exists()


def test_data_dir_unwritable(tmp_settings: Settings, tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    checks = run_checks(Settings(data_dir=blocker / "data"))
    assert checks[2][1] is False
    assert checks[2][2].endswith(" FAIL")


def test_database_url_is_masked(tmp_settings: Settings, tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, database_url="postgresql://user:secret@host/db")
    checks = run_checks(settings)
    assert checks[3][0] == "Database URL"
    assert "secret" not in checks[3][2]
    assert "***" in checks[3][2]
```

**R4.** Copy the three blocks unchanged. Do not rename a test, drop a parameter, change an import, or change a value. These tests pass against the existing code. If one fails, the copy is wrong: compare it with the block again. Do not edit `src/` to make a test pass.

**R5.** `python -m pytest` ends with `13 passed` and the line `Required test coverage of 85.0% reached. Total coverage: 93.70%`.

## Work order

Activate the virtual environment first, so `python` is the project's interpreter. Run each command on its own line. Do not start a step until the check of the previous step passes.

1. Replace `pyproject.toml` with the R1 block.
   Check: `python -m pip install -e ".[dev]"` finishes without an error.
2. Create `tests/conftest.py` from the R2 block.
   Check: `python -m pytest --no-cov` ends with `8 passed`.
3. Create `tests/unit/test_diagnostics.py` from the R3 block.
   Check: `python -m pytest tests/unit/test_diagnostics.py --no-cov` ends with `5 passed`.
4. Run `python -m ruff format .` and then `python -m ruff check --fix .`.
   Check: `git status --short` still lists only the three files of this phase. If the formatter changed another file, undo that change.
5. Append the entry to `docs/progress.md` using its template, with the heading `## Phase 2a: Coverage gate and shared fixture (YYYY-MM-DD)` and today's date. Under "Built", record the total coverage percentage.

## Before you stop

Every item must be true. If one is not, fix it and run the whole list again.

- [ ] `python -m ruff check .` prints `All checks passed!`
- [ ] `python -m ruff format --check .` reports no file to reformat
- [ ] `python -m pytest` ends with `13 passed` (exactly 13: the 8 existing plus 5 new)
- [ ] The `python -m pytest` output contains `Required test coverage of 85.0% reached`
- [ ] `git status --short` lists exactly these four paths and nothing else: `pyproject.toml`, `tests/conftest.py`, `tests/unit/test_diagnostics.py`, `docs/progress.md`
- [ ] `git diff HEAD -- src` prints nothing
- [ ] `docs/progress.md` ends with the `## Phase 2a: Coverage gate and shared fixture` entry, with all three template lines filled in
