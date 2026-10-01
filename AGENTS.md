# Rules for AI coding agents

This file applies to every phase. Read it, then `docs/architecture.md`, then the phase spec you were assigned.

## Scope discipline

- Implement **only** the phase you were assigned. Do not build features from later phases, even if it seems convenient.
- If the spec is ambiguous, pick the simplest option that satisfies the acceptance criteria and record the decision in `docs/progress.md`.
- If the spec seems wrong or impossible, stop and explain instead of improvising a large workaround.
- Do not add dependencies that the phase spec does not list. If you believe one is needed, stop and ask.
- When finished, append an entry to `docs/progress.md`: phase number, date, what was built, any deviations from the spec, and any follow-ups.

## Privacy rules (non-negotiable)

1. **No network calls** anywhere except inside `src/finances/advice/` (LLM, Phase 15) and `src/finances/connectors/` (aggregators, a future phase). Both run only on an explicit user command or a configured schedule. No telemetry, analytics, crash reporting, or update checks.
2. **Never commit financial data.** `data/` is gitignored. Do not create real-looking data outside `tests/fixtures/`.
3. **Tests use synthetic data only.** Invented merchants (e.g. "ACME COFFEE", "FOOBAR GROCERY"), invented amounts, no real names, no realistic account numbers.
4. **Do not log transaction descriptions, amounts, balances, or account numbers** at INFO level or above. DEBUG is allowed but must never be the default.
5. Error messages may reference a file line number and field name. Avoid echoing whole raw rows.
6. **Real statements live in `data/samples/`** (gitignored). You may run the opt-in real-sample tests against them (`FIN_REAL_SAMPLES=1 pytest -m real_samples`), but **never print, log, copy, or quote their contents**, and never derive fixtures from them by copying text. Those tests assert only pass/fail and counts. If a real sample fails, report which check failed (e.g. "reconciliation off by N cents, 23 lines parsed") and debug using the synthetic layouts in `docs/statement-formats.md`.

## Money and signs

- Money is always an **integer number of cents** (`int`). Never use `float` for money, in code, the DB, or tests.
- Parse money strings with `decimal.Decimal`, then convert to cents.
- **Sign convention: amounts are from the account holder's perspective.**
  - Money leaving you (purchase, payment, fee) is **negative**.
  - Money coming to you (paycheck, refund, interest) is **positive**.
  - Credit card balances you owe are **negative**.
- Single currency (USD) is assumed. Store `currency` on accounts but do not implement conversion.

## Architecture rules

- Layering (see `docs/architecture.md`): `domain` imports nothing from this project. `cli` and `web` are thin and contain no business logic.
- Business logic (ingest, categorize, analysis, privacy) must be callable without a CLI and testable without a real database where practical.
- Database access goes through SQLAlchemy 2.0 style code in `src/finances/db/`. No dialect-specific SQL. The app must stay portable to PostgreSQL / Azure SQL.
- Every schema change ships as an Alembic migration. Never edit a migration that a previous phase already shipped.
- All configuration comes from `finances.config.get_settings()` (environment variables with prefix `FIN_`). No hardcoded paths, no secrets in code.
- Use `pathlib.Path`. Development happens on Windows; code must also run on Linux (the eventual cloud container).

## Code style

- Python 3.11+, type hints on all public functions.
- `ruff check .` and `ruff format --check .` must pass.
- Prefer small, pure functions. Docstrings only where the intent is not obvious.
- `pytest` must pass, including all tests from previous phases.

## Testing

Follow `docs/testing.md`: put tests in the right layer (`tests/unit`, `tests/integration`, `tests/e2e`), keep them deterministic and offline, keep coverage above the configured threshold, and add a failing-first test for every bug fix. If you add code to a module listed under "Critical modules", cover every branch.
