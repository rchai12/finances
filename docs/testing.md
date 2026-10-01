# Testing strategy

Applies to every phase. Phase specs list the specific tests; this file sets the rules and the layers.

## Layers

| Layer | Location / marker | What it covers | Runs |
|---|---|---|---|
| Unit | `tests/unit/` | Pure functions: money, dates, parsers on text, matcher, reconciliation, fingerprints, rules | Every `pytest` run; must be fast (< 10 s total) |
| Integration | `tests/integration/` | Repositories, migrations, import services against a freshly migrated temp SQLite DB | Every `pytest` run |
| End-to-end | `tests/e2e/` | Multi-step CLI workflows (accounts → statement → CSV → statement) through Typer's `CliRunner` | Every `pytest` run |
| Property-based | inside unit/integration, using `hypothesis` (Phase 9) | Invariants over generated inputs | Every `pytest` run (bounded examples) |
| Golden (snapshot) | `tests/golden/` (Phase 9) | Full parser output for each synthetic fixture compared to a stored expected JSON | Every `pytest` run |
| Real samples | marker `real_samples`, opt-in via `FIN_REAL_SAMPLES=1` | Every file in `data/samples/` detects, parses, reconciles | Manually, locally only. Never in CI |
| Mutation | `cosmic-ray` (Phase 10), not pytest | Whether the tests actually catch bugs in critical modules | Manually / before tagging a release |
| PostgreSQL | marker `postgres` (Phase 17) | Integration suite against PostgreSQL | When cloud work begins |

## Rules

1. **Synthetic data only** in committed tests (AGENTS.md rules 3 and 6).
2. **No network** in any test. A test that needs the LLM uses a fake provider.
3. **Deterministic**: no dependence on today's date, dict ordering, file system order, or randomness (seed Hypothesis via its database or `derandomize=True` in CI).
4. **Every bug fix adds a test** that fails before the fix.
5. **Integration tests use migrations**, never `metadata.create_all`, so migrations are always exercised.
6. **Coverage**: branch coverage is measured from Phase 2. Overall `fail_under = 85`. From Phase 10, critical modules must reach 95% (see below).
7. Tests for a module live in the matching layer folder, named `test_<module>.py`.

## Critical modules

Bugs here silently corrupt money data, so they get the strictest gates (95% branch coverage, mutation-tested from Phase 10). Each later phase that adds a critical module adds it to this list and to the mutation config.

- `domain/money.py`
- `ingest/parsers/helpers.py` (year inference, amount parsing)
- `ingest/reconcile.py`, `ingest/csv_balance.py`
- `ingest/dedup.py`, `ingest/matching.py`, `ingest/merge.py`
- Later: transfer matching (Phase 11), spending aggregation (Phase 12), privacy PII checker and pseudonymizer (Phase 14)

## Commands

```powershell
pytest                                   # unit + integration + e2e + golden, with coverage
$env:FIN_REAL_SAMPLES=1; pytest -m real_samples; Remove-Item Env:FIN_REAL_SAMPLES
.\scripts\check.ps1                      # everything a commit needs (Phase 10)
.\scripts\mutation.ps1                   # mutation run on critical modules (Phase 10)
```
