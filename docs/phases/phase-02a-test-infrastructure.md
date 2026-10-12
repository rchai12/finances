# Phase 2a: Test infrastructure and coverage gate

## Goal

Branch coverage is measured on every `pytest` run and the run fails below 85%. A shared `tmp_settings` fixture exists for later phases. The untested branches left by Phase 1 get tests. **No production code changes in this phase.**

## Read first

- `AGENTS.md`
- `docs/testing.md`
- `docs/progress.md`
- `src/finances/config.py`, `src/finances/diagnostics.py`, `src/finances/cli/main.py`
- `tests/unit/test_config.py`, `tests/e2e/test_cli.py`

## Starting state

- `finances.config`: `Settings`, `get_settings()` (cached with `lru_cache`), `mask_url(url: str) -> str`.
- `finances.diagnostics`: `run_checks(settings: Settings) -> list[tuple[str, bool, str]]`, returning four checks in this order: `"Python version"`, `"Environment"`, `"Data dir"`, `"Database URL"`. The module does `import sys`.
- `finances.cli.main`: Typer `app`; the `doctor` command calls `run_checks` (imported into `finances.cli.main`) and exits 1 if any check is not ok.
- 8 tests exist, in `tests/unit/test_config.py`, `tests/unit/test_log.py`, and `tests/e2e/test_cli.py`. Branch coverage of the existing code is about 90%.

## Files

| Path | Action |
|---|---|
| `pyproject.toml` | modify |
| `tests/conftest.py` | create |
| `tests/unit/test_diagnostics.py` | create |
| `tests/unit/test_config.py` | modify (add tests only) |
| `tests/e2e/test_cli.py` | modify (add tests only) |

Do not create or modify any other file, except `docs/progress.md`. Do not change anything under `src/`.

## Out of scope

Money helpers, database, SQLAlchemy, Alembic, any new CLI command, `tests/integration/`. Do not rewrite or delete existing tests. Do not use `# pragma: no cover`.

## Dependencies

Add to the `dev` list in `pyproject.toml`: `pytest-cov>=5`. Nothing else.

## Requirements

**R1.** In `pyproject.toml`, `[project.optional-dependencies] dev` contains `"pytest-cov>=5"` in addition to the existing entries.

**R2.** In `pyproject.toml`, `[tool.pytest.ini_options]` is exactly:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib --cov=finances --cov-branch --cov-report=term-missing"
```

**R3.** `pyproject.toml` has this new section:

```toml
[tool.coverage.report]
fail_under = 85
show_missing = true
```

**R4.** `tests/conftest.py` contains exactly one fixture, `tmp_settings`:

```python
from collections.abc import Iterator

import pytest

from finances.config import Settings, get_settings

_ENV_KEYS = ("FIN_ENVIRONMENT", "FIN_DATA_DIR", "FIN_DATABASE_URL", "FIN_LOG_LEVEL")


@pytest.fixture
def tmp_settings(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[Settings]:
    """Settings whose data dir is under tmp_path, with no .env file in reach."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FIN_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()
```

**R5.** `tests/unit/test_diagnostics.py` contains these five tests. Each takes the `tmp_settings` fixture (and `tmp_path` or `monkeypatch` where the row uses them).

| Test name | Arrange | Assert |
|---|---|---|
| `test_python_version_ok` | `checks = run_checks(tmp_settings)` | `checks[0][0] == "Python version"`, `checks[0][1] is True`, `"FAIL" not in checks[0][2]` |
| `test_python_version_too_old` | `V = collections.namedtuple("V", "major minor micro")`; `monkeypatch.setattr(finances.diagnostics, "sys", types.SimpleNamespace(version_info=V(3, 10, 0)))`; then `checks = run_checks(tmp_settings)` | `checks[0] == ("Python version", False, "3.10.0 FAIL")` |
| `test_data_dir_ok` | `checks = run_checks(tmp_settings)` | `checks[2][0] == "Data dir"`, `checks[2][1] is True`, `checks[2][2].endswith(" OK")`, `tmp_settings.data_dir.is_dir()`, and `(tmp_settings.data_dir / ".fin_write_probe").exists() is False` |
| `test_data_dir_unwritable` | `blocker = tmp_path / "blocker"`; `blocker.write_text("")`; `settings = Settings(data_dir=blocker / "data")`; `checks = run_checks(settings)` | `checks[2][1] is False` and `checks[2][2].endswith(" FAIL")` |
| `test_database_url_is_masked` | `settings = Settings(data_dir=tmp_path, database_url="postgresql://user:secret@host/db")`; `checks = run_checks(settings)` | `checks[3][0] == "Database URL"`, `"secret" not in checks[3][2]`, `"***" in checks[3][2]` |

Do not patch the real `sys.version_info`. Patch the `sys` name inside `finances.diagnostics` as shown.

**R6.** Add these two tests to `tests/unit/test_config.py`, leaving the existing tests and fixture unchanged:

| Test name | Assert |
|---|---|
| `test_mask_url_keeps_port` | `mask_url("postgresql://user:secret@host:5432/db") == "postgresql://user:***@host:5432/db"` |
| `test_mask_url_ipv6_host` | `mask_url("postgresql://user:secret@[::1]:5432/db") == "postgresql://user:***@[::1]:5432/db"` |

**R7.** Add this test to `tests/e2e/test_cli.py`, leaving the existing tests unchanged:

`test_doctor_exits_1_when_a_check_fails(monkeypatch, tmp_settings)`: `monkeypatch.setattr("finances.cli.main.run_checks", lambda settings: [("Probe", False, "bad FAIL")])`; invoke `["doctor"]`; assert `result.exit_code == 1` and `"Probe" in result.stdout`.

**R8.** `pytest` exits 0 and the coverage report shows `TOTAL` at 85% or higher. If it is lower after R1 to R7, add tests for the lines listed under `Missing` in the report, in the test file that matches the module, and list each added test in `docs/progress.md`. Do not lower `fail_under`, exclude files from coverage, or edit `src/`.

## Acceptance criteria

Run each command on its own line:

```
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
```

- `ruff check .` and `ruff format --check .` report no problems.
- `pytest` exits 0, runs at least 16 tests, prints a coverage table, and `TOTAL` is at least 85%.
- `git status --short` shows `src/` untouched.

## Done

Append the entry to `docs/progress.md` using its template, with the heading `## Phase 2a: Test infrastructure and coverage gate (YYYY-MM-DD)`. Record the `TOTAL` coverage percentage.
