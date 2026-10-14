# Testing strategy

Applies to every phase. Phase specs list the specific tests; this file sets the rules and the layers.

## Layers

| Layer | Location / marker | What it covers | Runs |
|---|---|---|---|
| Unit | `tests/unit/` | Pure functions: money, dates, parsers on text, matcher, reconciliation, fingerprints, rules | Every `pytest` run; must be fast (< 10 s total) |
| Integration | `tests/integration/` | Repositories, migrations, import services against a freshly migrated temp SQLite DB | Every `pytest` run |
| End-to-end | `tests/e2e/` | Multi-step CLI workflows (accounts → sync → statement) through Typer's `CliRunner` | Every `pytest` run |
| Property-based | inside unit/integration, using `hypothesis` (Phase 9) | Invariants over generated inputs | Every `pytest` run (bounded examples) |
| Golden (snapshot) | `tests/golden/` (Phase 9) | Full parser output for each synthetic fixture compared to a stored expected JSON | Every `pytest` run |
| Real samples | `tests/real_samples/check_real_samples.py`, run by naming the file | Every PDF in `data/samples/` is read, recognized, parsed, and reconciled; the output is sample numbers, parser names, counts, and differences in cents only | Manually, on the machine that holds the statements. Never part of the normal run, never in CI |
| Mutation | `cosmic-ray` (Phase 10), not pytest | Whether the tests actually catch bugs in critical modules | Manually / before tagging a release |

## Rules

1. **Synthetic data only** in committed tests (AGENTS.md rules 3 and 6).
2. **No network** in any test. MCP server tests use the SDK's in-memory client, never a subprocess or socket. Aggregator tests use a fake client with synthetic responses.
3. **Deterministic**: no dependence on today's date, dict ordering, file system order, or randomness (seed Hypothesis via its database or `derandomize=True` in CI).
4. **Every bug fix adds a test** that fails before the fix.
5. **Integration tests use migrations**, never `metadata.create_all`, so migrations are always exercised.
6. **Coverage**: branch coverage is measured from Phase 2. Overall `fail_under = 85`. From Phase 10, critical modules must reach 95% (see below).
7. Tests for a module live in the matching layer folder, named `test_<module>.py`.

## Critical modules

Bugs here silently corrupt money data, so they get the strictest gates (95% branch coverage, mutation-tested from Phase 10). Each later phase that adds a critical module adds it to this list and to the mutation config.

- `domain/money.py`
- `ingest/parsers/helpers.py` (year inference, amount parsing)
- `ingest/reconcile.py`
- `ingest/dedup.py`, `ingest/matching.py`, `ingest/merge.py`
- `sync/service.py` (applying a feed, balance drift)
- Later: aggregator row mapping (Phase 17b), transfer matching (Phase 11), spending aggregation (Phase 12)

## Commands

Every command names the virtual environment's interpreter (`AGENTS.md`, "Running commands"). On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python`.

```zsh
.venv/bin/python -m pytest                         # unit + integration + e2e + golden, with coverage
.venv/bin/python -m pytest tests/real_samples/check_real_samples.py --no-cov -rA   # real statements, opt-in
```

Phase 10 adds one script that runs everything a commit needs, and a mutation run on the critical modules.
