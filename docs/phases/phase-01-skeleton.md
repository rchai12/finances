# Phase 1: Project skeleton

## Goal

An installable Python package with configuration, safe logging, a `fin` CLI with `--version` and `doctor`, and a passing test and lint setup. No database, no financial logic.

## Read first

- `AGENTS.md`
- `docs/architecture.md` (package layout, config approach)

## In scope

- Git repository and `.gitignore`
- `pyproject.toml`, src layout, editable install
- `config.py`, `log.py`
- CLI entry point `fin` with `--version` and `doctor`
- Tests and ruff configuration

## Out of scope

Database, models, importing, any financial logic. Do not create empty placeholder modules for later phases.

## Dependencies

Runtime: `typer>=0.12`, `rich>=13`, `pydantic>=2.6`, `pydantic-settings>=2.2`
Dev (optional extra `dev`): `pytest>=8`, `ruff>=0.5`

## Deliverables

### 1. Repository files

- Run `git init` if the folder is not already a repository.
- `.gitignore` must include at least:
  ```
  .venv/
  __pycache__/
  *.pyc
  .pytest_cache/
  .ruff_cache/
  *.egg-info/
  .env
  data/
  *.db
  *.sqlite
  # financial statements and exports anywhere except test fixtures
  *.pdf
  *.PDF
  *.csv
  *.ofx
  *.qfx
  !tests/fixtures/**
  ```
- `.env.example` documenting every setting with safe defaults (no secrets).
- `README.md`: one-paragraph description, Windows PowerShell setup steps (create venv, activate, `pip install -e ".[dev]"`), and how to run tests.

### 2. `pyproject.toml`

- Project name `finances`, `requires-python = ">=3.11"`, src layout (`src/finances`).
- Console script: `fin = "finances.cli.main:app"`.
- Version `0.1.0`, exposed as `finances.__version__` (read via `importlib.metadata`, falling back to `"0.0.0"` if not installed).
- Ruff config: line length 100, target py311, enable rule sets `E, F, I, B, UP`.
- Pytest config: `testpaths = ["tests"]`.

### 3. `src/finances/config.py`

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FIN_", env_file=".env", extra="ignore")

    environment: Literal["local", "cloud"] = "local"
    data_dir: Path = Path("data")
    database_url: str | None = None     # if None, derived from data_dir
    log_level: str = "INFO"

    @property
    def effective_database_url(self) -> str: ...
        # if database_url is set, return it
        # else f"sqlite:///{(data_dir / 'finances.db').resolve().as_posix()}"

def get_settings() -> Settings: ...   # cached with functools.lru_cache
```

- Provide a way for tests to reset the cache (`get_settings.cache_clear()` is fine).
- Provide `mask_url(url: str) -> str` that replaces any password in a database URL with `***`.

### 4. `src/finances/log.py`

- `setup_logging(level: str) -> None` configures the root logger with a simple format (`time level name: message`), output to stderr.
- `RedactingFilter(logging.Filter)` attached to the handler. It rewrites the final formatted message, replacing:
  - any run of 6 or more digits (spaces or dashes allowed between digits) with `[REDACTED-NUM]`;
  - email addresses with `[REDACTED-EMAIL]`.
- This is a safety net only. AGENTS.md rule 4 still applies.
- Name the module `log.py`, not `logging.py` (would shadow the stdlib).

### 5. `src/finances/cli/main.py`

- Typer `app` with:
  - `fin --version`: prints `finances 0.1.0` and exits.
  - `fin doctor`: prints a Rich table of checks:
    | Check | Result |
    |---|---|
    | Python version | e.g. `3.11.9` (fail if < 3.11) |
    | Environment | `local` / `cloud` |
    | Data dir | resolved path; creates it if missing; `OK` if writable, `FAIL` otherwise |
    | Database URL | masked via `mask_url` |
  - Exit code 0 if all checks pass, 1 otherwise.
- Logging is set up once in the Typer callback using `get_settings().log_level`.
- Keep `main.py` thin. Put the check logic in `src/finances/diagnostics.py` as a function returning a list of `(name, ok: bool, detail: str)`; the CLI only renders it.

## Tests (`tests/`)

- `test_config.py`
  - defaults: environment `local`, derived SQLite URL ends with `data/finances.db`.
  - env override: setting `FIN_DATA_DIR` and `FIN_DATABASE_URL` via `monkeypatch` changes the values (clear the cache).
  - `mask_url("postgresql://user:secret@host/db")` hides `secret`; URL without password is unchanged.
- `test_log.py`
  - the filter redacts `"card 4111 1111 1111 1111"` and `"acct 12345678"` and `"me@example.com"`.
  - the filter leaves `"imported 12 rows"` unchanged (fewer than 6 digits).
- `test_cli.py` (Typer `CliRunner`)
  - `--version` output contains `0.1.0`.
  - `doctor` with `FIN_DATA_DIR` pointed at `tmp_path` exits 0 and creates the directory.

## Acceptance criteria

From a fresh clone on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
fin --version
fin doctor
```

All succeed. `git status` shows no `data/` directory or `.env` file being tracked.

Append your entry to `docs/progress.md`.
