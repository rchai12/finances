# Rules for AI coding agents

This file applies to every phase. Read it, then `docs/architecture.md`, then the phase spec you were assigned.

## Scope discipline

- Implement **only** the phase you were assigned. Do not build features from later phases, even if it seems convenient.
- If the spec is ambiguous, pick the simplest option that satisfies the acceptance criteria and record the decision in `docs/progress.md`.
- If the spec seems wrong or impossible, stop and explain instead of improvising a large workaround.
- Do not add dependencies that the phase spec does not list. If you believe one is needed, stop and ask.
- When finished, append an entry to `docs/progress.md`: phase number, date, what was built, any deviations from the spec, and any follow-ups.

## Running commands

- The project's interpreter is `.venv/bin/python`. Every command names it: `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check .`, `.venv/bin/fin doctor`.
- Never type `python`, `python3`, `ruff`, or `pytest` on their own. On this machine `python` does not exist, `python3` is a different interpreter without the project's packages, and a bare `ruff` is a different installation.
- Do not activate the virtual environment. Each command runs in a new shell, so activation is lost before the next command.
- `.venv/` already exists. It is gitignored, so `git status` and `git ls-files` do not show it. Do not create another virtual environment and do not reinstall packages unless the phase spec has a step for it.
- If a command prints `command not found` or `No module named ...`, it was not typed as written. Stop and fix the command; do not skip the step.
- On Windows the same commands start with `.\.venv\Scripts\python`.
- Before reporting a phase, run `.venv/bin/python scripts/check.py`. It must end with `All checks passed.`

## Privacy rules (non-negotiable)

1. **No network calls** anywhere except inside `src/finances/sync/` (the aggregator client, Phase 17), which contacts only the configured aggregator. No telemetry, analytics, crash reporting, or update checks. The MCP server (Phase 14) uses the stdio transport only and never opens a port; the web UI (Phase 16) binds to 127.0.0.1 only, and remote access is provided outside the app by a private VPN. This app never calls an LLM.
2. **Never commit financial data.** `data/` is gitignored. Do not create real-looking data outside `tests/fixtures/`.
3. **Tests use synthetic data only.** Invented merchants (e.g. "ACME COFFEE", "FOOBAR GROCERY"), invented amounts, no real names, no realistic account numbers.
4. **Do not log transaction descriptions, amounts, balances, or account numbers** at INFO level or above. DEBUG is allowed but must never be the default.
5. Error messages may reference a file line number and field name. Avoid echoing whole raw rows.
6. **Real statements live in `data/samples/`** (gitignored). You may run the opt-in real-sample check against them (`.venv/bin/python -m pytest tests/real_samples/check_real_samples.py --no-cov -rA`) and the layout report (`.venv/bin/python tests/real_samples/describe_layout.py`, which prints counts and yes-or-no answers only), but **never print, log, copy, or quote their contents**, and never derive fixtures from them by copying text. Those tests assert only pass/fail and counts. If a real sample fails, report which check failed (e.g. "reconciliation off by N cents, 23 lines parsed") and debug using the synthetic layouts in `docs/statement-formats.md`.

## Money and signs

- Money is always an **integer number of cents** (`int`). Never use `float` for money, in code, the DB, or tests.
- Parse money strings with `decimal.Decimal`, then convert to cents.
- **Sign convention: amounts are from the account holder's perspective.**
  - Money leaving you (purchase, payment, fee) is **negative**.
  - Money coming to you (paycheck, refund, interest) is **positive**.
  - Credit card balances you owe are **negative**.
- Single currency (USD) is assumed. Store `currency` on accounts, as three capital letters, but do not implement conversion.

## Architecture rules

- Layering (see `docs/architecture.md`): `domain` imports nothing from this project. `cli`, `mcp_server`, and `web` are thin and contain no business logic.
- MCP tools are read-only until Phase 19. From then on a tool may write only what its spec lists, and never an amount, date, balance, account, import, deletion, or sync.
- Business logic (ingest, sync, categorize, analysis) must be callable without a CLI and testable without a real database where practical.
- Database access goes through SQLAlchemy 2.0 style code in `src/finances/db/`. No dialect-specific SQL.
- Every text value written fits its column. SQLite does not enforce `String(n)` lengths, so check or cut each value before it is stored: refuse what a person typed (with a message naming the limit), cut what came from a statement or the feed.
- Every schema change ships as an Alembic migration. Never edit a migration that a previous phase already shipped.
- All configuration comes from `finances.config.get_settings()` (environment variables with prefix `FIN_`). No hardcoded paths, no secrets in code. The aggregator token lives in the OS keyring only.
- Use `pathlib.Path`. Development and deployment happen on macOS; code must also run on Windows.

## Code style

- Python 3.11+, type hints on all public functions.
- `ruff check .` and `ruff format --check .` must pass.
- Prefer small, pure functions. Docstrings only where the intent is not obvious.
- `pytest` must pass, including all tests from previous phases.

## Testing

Follow `docs/testing.md`: put tests in the right layer (`tests/unit`, `tests/integration`, `tests/e2e`), keep them deterministic and offline, keep coverage above the configured threshold, and add a failing-first test for every bug fix. If you add code to a module listed under "Critical modules", cover every branch.
