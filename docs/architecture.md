# Architecture

## Purpose

A personal finance tool for one household (two people, several shared cards). It imports monthly PDF statements (the record) and CSV exports (provisional, covering the time since the last statement) from banks and card issuers, computes balances, ranks spending by category and merchant, finds specific places to cut back, and optionally asks a frontier LLM for advice using a privacy-preserving summary.

It runs locally first. It is structured so it can later move to Azure with minimal change.

## Goals

- Raw financial data never leaves the user's machine unless the user deliberately deploys to the cloud.
- The LLM only ever receives an aggregated, pseudonymized payload that the user can preview before sending.
- Targeted, merchant-level advice ("$118/mo at an independent bakery, up 2x since summer").
- Small, readable codebase that the owner can audit.

## Non-goals (for now)

- Bank scraping or stored bank credentials. Data arrives as PDF statements and CSV exports the user downloads.
- OCR. All current statements contain extractable text.
- Third-party aggregators (Plaid, etc.).
- Multi-user, multi-currency, investments, taxes, budgeting envelopes.

## Tech stack

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Strong data tooling, readable |
| CLI | Typer + Rich | Simple commands, nice tables |
| Config | pydantic-settings, env vars prefixed `FIN_` | Same mechanism works locally and in Azure |
| DB access | SQLAlchemy 2.0 | Portable between SQLite and PostgreSQL / Azure SQL |
| Migrations | Alembic | Versioned schema, needed once a cloud DB exists |
| Local DB | SQLite file in `data/` | Zero setup |
| PDF text | `pypdf` (layout extraction mode) | Pure Python; keeps statement columns aligned where `pdftotext` scrambles them |
| Web UI (later) | FastAPI + Jinja2 + HTMX | One deployable container, little JavaScript |
| LLM (later) | Provider interface, first implementation Anthropic API | Swappable |
| Tests / lint | pytest, ruff | Standard |

## Package layout

```
finances/
  AGENTS.md, CLAUDE.md          rules for coding agents
  pyproject.toml
  docs/                         architecture, phase specs, progress log
  migrations/                   Alembic
  src/finances/
    config.py                   Settings, get_settings()
    log.py                      logging setup + redaction filter
    domain/                     pure dataclasses, enums, money helpers (no project imports)
    db/                         engine/session, ORM models, repositories
    ingest/                     PDF text, statement model, reconciliation, dedup, import service
      parsers/                  one module per statement format (Capital One, BoA, Citi, Truist, Marcus)
    categorize/                 categories, rules engine, merchant normalization
    analysis/                   reports and insights (pure functions over domain objects)
    privacy/                    pseudonymization, coarsening, PII checks, payload builder
    advice/                     LLM provider interface + implementations (ONLY place with network)
    cli/                        Typer commands (thin)
    web/                        FastAPI app (thin, later)
  tests/
    fixtures/                   synthetic CSV/OFX files only
  data/                         gitignored: SQLite DB, user profiles, payload previews
```

### Dependency direction

```
cli, web  ──►  ingest, categorize, analysis, privacy, advice  ──►  db  ──►  domain
                         └──────────────────────────────────────────────►  domain
```

- `domain` depends on nothing in the project.
- `analysis` and `privacy` operate on domain objects, not ORM rows, so they are testable without a database.
- `advice` receives a finished payload from `privacy`. It never reads the database directly.

## Data flow

```
 PDF statement ─► text ─► detect format ─► bank parser ─► reconcile (must balance to the cent)
                                                              │
                                                              ▼
                                                   transactions + balance snapshot (DB)
                                                              ▲
 CSV export ─► detect profile ─► parse ─► daily balance check ┘  (source = csv, provisional;
                                                                 a later statement upgrades
                                                                 these rows in place)
                               │
                               ▼
                         categorize (rules)  ◄── user rules / manual overrides
                               │
                               ▼
                         analysis: balances, spending by category,
                         per-merchant stats, recurring charges, insights
                               │                         │
                               ▼                         ▼
                         reports (CLI/web)        privacy: pseudonymize + coarsen
                                                         │
                                                         ▼
                                                  payload preview file  (user reviews)
                                                         │  explicit confirm
                                                         ▼
                                                  advice: LLM API ─► response
                                                         │
                                                         ▼
                                                  re-hydrate tokens locally ─► shown to user
```

## Privacy boundary

Everything left of the LLM call stays local. The payload sent to the LLM:

- contains category totals, trends, and per-merchant behavior stats;
- names only well-known national brands (from an allowlist); every other merchant becomes a token like `M07` plus a generic type ("independent bakery");
- coarsens time (week or month, "weekday mornings"), rounds amounts to whole dollars;
- excludes sensitive categories (medical, legal, religious, political) entirely;
- uses fresh tokens on every run so runs cannot be linked;
- must pass an automated PII check (digit runs, emails, phone numbers, user blocklist) and be written to a preview file before it can be sent.

The token-to-name mapping never leaves the machine.

## Data model (overview)

Details are in the phase specs. Core tables:

- `accounts`: one row per bank account or card account, matched to statements by last 4 digits.
- `import_batches`: one row per imported file; for statements also the period, opening/closing balance, and whether it reconciled.
- `transactions`: one row per transaction, with posted and transaction dates, section, card last4, and cardholder; deduplicated by a fingerprint.
- `balance_snapshots`: balance of an account as of a date (from each statement, or entered manually).
- `categories`, `category_rules`, `merchants` (Phase 11).

### Statement parsing design

- Each format is a `StatementParser` with `detect(first_page_text)` and `parse(pages_text) -> ParsedStatement`. Parsers work on **text**, so tests use synthetic text fixtures and never need real PDFs.
- **Reconciliation is the safety net**: opening balance + sum of parsed lines must equal the closing balance exactly, and declared section totals must match. A statement that does not reconcile is not imported (unless explicitly overridden and flagged).
- Statement dates often omit the year; a shared helper infers it from the statement period (handles December to January).
- Real statements in `data/samples/` are used only by opt-in tests that report pass/fail, never content.

Transfers between the household's own accounts (card payments from checking, moves between checking and savings) must be excluded from spending, or spending is double-counted. Phase 11 handles this.

## Cloud migration path

The local design already isolates what changes in the cloud:

| Concern | Local | Azure (later) |
|---|---|---|
| Config | `.env` / env vars | Container App env vars |
| Secrets (LLM key, DB password) | `.env` (gitignored) | Key Vault + managed identity |
| Database | SQLite | PostgreSQL or Azure SQL (decide in Phase 17) |
| File uploads | read from local path | upload through web UI, processed in memory or Blob Storage |
| Auth | none (bound to 127.0.0.1) | Container Apps built-in auth with Entra ID, single allowed user |
| Hosting | `fin` CLI / local uvicorn | Azure Container Apps (free monthly grant) |

Rules that keep this cheap: config only from env, no dialect-specific SQL, web layer thin, no local-filesystem assumptions inside business logic (pass file contents or file-like objects, not paths, to parsers).

### Open decision for later

Whether the cloud copy holds raw transactions or only processed summaries. Decide before Phase 18.
