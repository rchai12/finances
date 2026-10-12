# Progress log

Coding agents append one entry per phase, newest at the bottom.

Template:

```
## Phase N: <name> (YYYY-MM-DD)
- Built:
- Deviations from spec (and why):
- Follow-ups / known issues:
```

## Phase 1: Project skeleton (2026-10-01)
- Built: installable `finances` 0.1.0 package, `FIN_` settings, redacting log filter, `fin --version`, `fin doctor`, and tests.
- Deviations from spec (and why): `.gitignore` also ignores `data/samples/`, uppercase statement extensions, and `*.sqlite3`, so real exports stay untracked even if Git's ignore matching is case-sensitive. Ruff format excludes `docs/` so `ruff format --check .` does not rewrite phase specs.
- Follow-ups / known issues: tests now live in `tests/unit/` (`test_config.py`, `test_log.py`) and `tests/e2e/` (`test_cli.py`), matching `docs/testing.md`.

## Phase 2a: Coverage gate and shared fixture (2026-10-12)
- Built: pyproject.toml with pytest-cov>=5 dependency, tests/conftest.py with tmp_settings fixture, and tests/unit/test_diagnostics.py with five tests. TOTAL coverage: 93.70%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2b: Tests for Phase 1 gaps (2026-10-12)
- Built: three tests for untested Phase 1 branches (`mask_url` with a port, `mask_url` with an IPv6 host, `fin doctor` exit code 1), and the final newline of `pyproject.toml`. 16 tests pass. TOTAL coverage: 98.43%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2c: format_cents (2026-10-12)
- Built: `format_cents` in `src/finances/domain/money.py`, and `tests/unit/test_money.py`. 30 tests pass. `money.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2d: parse_money (2026-10-12)
- Built: `parse_money` in `src/finances/domain/money.py`, with the full money tests in `tests/unit/test_money.py`. 89 tests pass. `money.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2e: AccountType and Account (2026-10-12)
- Built: `AccountType` and `Account` in `src/finances/domain/models.py`, and `tests/unit/test_models.py`. 102 tests pass. `models.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2f: validate_last4 (2026-10-12)
- Built: `validate_last4` in `src/finances/domain/models.py`, with its tests in `tests/unit/test_models.py`. 122 tests pass. `models.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None
