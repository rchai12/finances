# Testing strategy

Applies to every phase. Phase specs list the specific tests; this file sets the rules and the layers.

## Layers

| Layer | Location / marker | What it covers | Runs |
|---|---|---|---|
| Unit | `tests/unit/` | Pure functions: money, dates, parsers on text, matcher, reconciliation, fingerprints, rules | Every `pytest` run; must be fast (< 10 s total) |
| Integration | `tests/integration/` | Repositories, migrations, import services against a freshly migrated temp SQLite DB | Every `pytest` run |
| End-to-end | `tests/e2e/` | Multi-step CLI workflows (accounts → sync → statement) through Typer's `CliRunner` | Every `pytest` run |
| Property-based | inside unit/integration, using `hypothesis` (Phase 9); the profile in `tests/conftest.py` makes every run use the same examples and keep no example database | Invariants over generated inputs: money, dates, reconciliation, fingerprints, pairing, damaged statements and SimpleFIN answers, and statements and feed pulls in any order | Every `pytest` run (bounded examples) |
| Real samples | `tests/real_samples/check_real_samples.py`, run by naming the file | Every PDF in `data/samples/` is read, recognized, parsed, and reconciled; the output is sample numbers, parser names, counts, and differences in cents only | Manually, on the machine that holds the statements. Never part of the normal run, never in CI |
| Mutation | not yet | Whether the tests catch deliberate bugs in critical modules | A later phase |

## Rules

1. **Synthetic data only** in committed tests (AGENTS.md rules 3 and 6).
2. **No network** in any test. MCP server tests use the SDK's in-memory client, never a subprocess or socket. Aggregator tests use a fake client with synthetic responses.
3. **Deterministic**: no dependence on today's date, dict ordering, file system order, or randomness. Hypothesis runs under the profile in `tests/conftest.py` (`derandomize=True`, no example database), so every run uses the same examples; no test sets its own seed or database.
4. **Every bug fix adds a test** that fails before the fix.
5. **Integration tests use migrations**, never `metadata.create_all`, so migrations are always exercised.
6. **Coverage**: branch coverage is measured on every run. Overall `fail_under = 85`. Every line and every branch of each critical module must be covered; `scripts/check.py` checks it.
7. Tests for a module live in the matching layer folder, named `test_<module>.py`.
8. **Shared helpers live in `tests/support.py`** (from Phase 13c): running `fin` and reading its tables (`run`, `table_rows`, `plain_lines`, `failed_cleanly`) and reading web pages (`Page`, `page`, `post`, `texts`). New tests import them instead of copying them; older tests keep their copies until they are next changed.

## Critical modules

Bugs here silently corrupt money data, so every line and every branch of each must be covered by tests. The list lives in `scripts/critical_modules.txt`, which `scripts/check.py` reads; a phase that adds a critical module adds it there and here.

- `domain/money.py`
- `ingest/parsers/helpers.py` (year inference, amount parsing)
- `ingest/reconcile.py`
- `ingest/dedup.py`
- `domain/matching.py` (pairing feed rows with statement lines)
- `sync/service.py` (applying a feed, balance drift)
- `sync/simplefin.py` (reading SimpleFIN's answers)
- `domain/feed_setup.py` (guessing how to set up a new SimpleFIN account)
- `analysis/people.py` (whose money a transaction is)
- `db/backup.py` (copying, checking, and restoring the database)
- `domain/transfers.py` (transfer candidates and clear pairs; added in Phase 36a)
- `domain/spending.py` (kinds, spending lines, refunds; added in Phase 36a)
- `domain/splits.py` (parts that add up to a transaction; added in Phase 28d)

## Commands

Every command names the virtual environment's interpreter (`AGENTS.md`, "Running commands"). On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python`.

```zsh
.venv/bin/python scripts/check.py                  # everything a phase must pass: lint, format, tests, critical coverage
.venv/bin/python scripts/check.py --real-samples   # the same, then the real statements (opt-in, counts only)
.venv/bin/python -m pytest                         # the tests alone, with coverage
```

To have lint and format checked before every commit, run `scripts/install-git-hooks.sh` once; `scripts/uninstall-git-hooks.sh` removes the hook.
