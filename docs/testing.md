# Testing strategy

Applies to every phase. Phase specs list the specific tests; this file sets the rules and the layers.

## Layers

| Layer | Location / marker | What it covers | Runs |
|---|---|---|---|
| Unit | `tests/unit/` | Pure functions: money, dates, parsers on text, matcher, reconciliation, fingerprints, rules | Every `pytest` run; keep fast (the historical < 10 s aspiration is not a measured gate) |
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
7. Name new tests for the behavior they check, in the appropriate layer; keep module context in filenames such as `test_<module>.py`. Existing `*_more.py` files remain valid. A bug fix does not require renaming unrelated tests or duplicating a whole workflow in every layer; front-end regression cases remain useful.
8. When deliberately moving tests, record an exact old-to-new node map and update section patterns and imports. Preserve every case and assertion.
9. **Shared helpers live in `tests/support.py`** (from Phase 13c): running `fin` and reading its tables (`run`, `table_rows`, `plain_lines`, `failed_cleanly`) and reading web pages (`Page`, `page`, `post`, `texts`). New tests import them instead of copying them; older tests keep their copies until they are next changed.

## View import guard

The view guard scans Python imports recursively, including imports nested in functions. It rejects database, sync, keyring and SQLAlchemy imports except the exact result type `LinkRun` from `finances.sync.runner` in the root `sync.py` view. Imports of analysis result types in backup and transfer views are also allowed. Importing a service result type creates coupling; it does not by itself establish that a view performs IO. Move a result type when its service/view contract next changes.

This AST guard checks declared import dependencies; it does not execute code or sandbox dynamic Python, and the `LinkRun` exception does not prove arbitrary calling code is IO-free.

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
- `domain/shared.py` (a share in cents and who owes whom; added in Phase 29a)

## Commands

Every command names the virtual environment's interpreter (`AGENTS.md`, "Running commands"). On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python`.

```zsh
.venv/bin/python scripts/check.py                  # everything a phase must pass: lint, format, tests, critical coverage
.venv/bin/python scripts/check.py --real-samples   # the same, then the real statements (opt-in, counts only)
.venv/bin/python scripts/check.py --first web     # the web section first; the full check only once it passes
.venv/bin/python scripts/check.py --section web   # one section alone, no coverage (names in tests/sections.toml)
.venv/bin/python -m pytest                         # the tests alone, with coverage
```

A phase names its sections, and its check is `check.py --first <its sections>`: their tests run first, and the full run only once they pass. A full run prints a table of the eight sections after the tests, with a rerun command beside any section that failed. A new test file belongs in the section of the code it tests: add a pattern to `tests/sections.toml` when `core` would take it otherwise.

To have lint and format checked before every commit, run `scripts/install-git-hooks.sh` once; `scripts/uninstall-git-hooks.sh` removes the hook.

### Focused development and local workers

Use focused files without coverage while developing:
`.venv/bin/python -m pytest tests/unit/test_check_parallel_behavior.py --no-cov`.
`check.py --section scripts` also runs without coverage. Add `--workers 2` or
`--workers 4` to opt into that many local pytest subprocess workers using the
load scheduler; `--workers 1` is the serial default. Only positive integers are
accepted, never `auto`. `--durations 20` reports the slowest setup, call and
teardown items; its nonnegative integer default is 0 (no timing flag).

Both options apply to section, selected-first and full synthetic pytest steps.
They do not parallelize lint, format, critical coverage inspection, real-sample
checks or separate acceptance invocations. `--first scripts` still runs the
selected section before the complete suite; it does not replace full acceptance.
Run the phase's required full checks at handoff, and run independent verification
separately. See [measured performance](testing-performance.md) for the machine's
worker recommendation and benchmark limitations.

Run one coordinated coverage-producing job per checkout at a time: pytest-cov
combines all local workers in that job, and later coverage commands consume its
persistent data. Concurrent runs in one checkout can overwrite that evidence.
Separate checkouts keep separate artifacts but share a machine-wide worker
budget: agree a bounded total before starting concurrent agents; do not assign
all cores to each agent. Inspect fixed shared filenames and ports before a new
parallel test arrangement. Infrastructure failures need explicit resolution;
never drop tests or weaken assertions to accommodate workers.

Source, test, dependency or configuration changes require fresh applicable gates.
A scope/document-only reassessment can reuse explicitly identified prior evidence
only with owner-authorized narrowing and matching tested bytes and relevant
environment. There is no automatic PASS, and a coder's results never substitute
for independent verifier evidence.
