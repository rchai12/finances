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
