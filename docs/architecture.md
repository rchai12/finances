# Architecture

## Purpose

A personal finance tool for one household (two people, several shared cards). It pulls transactions daily from a third-party aggregator (provisional) and imports monthly PDF statements as the audit (the record), computes balances, ranks spending by category and merchant, and finds specific places to cut back.

It is one platform inside a larger personal AI system. An overarching agent, running on a local model, delegates work to subagents (email, reminders, tasks, stock analysis). One of those subagents uses this app through an MCP server to analyze spending patterns and give advice. The app supplies the data, the reports, and the rule-based findings. It contains no LLM and does not produce advice itself.

Everything runs on one machine the household owns (a Mac Studio): the overarching agent, its subagents, the local model, and this app with its database. There is no cloud deployment.

The household reaches that machine remotely over a private, encrypted connection. The app itself is never published to the internet (see Privacy boundary).

It also works on its own through the `fin` CLI and, later, a local web UI.

## Goals

- Raw financial data stays on the household's machine. The app's only outbound connection is to the aggregator.
- The agent gets typed tools that return real merchants and amounts, so its advice can be specific ("$118/mo at one bakery, up 2x since summer").
- Arithmetic is done here, in tested code, not by the model: balances, totals, trends, and findings come back from tools already computed.
- Every report is a pure function with one implementation, shared by the CLI, the web UI, and the MCP server.
- Small, readable codebase that the owner can audit.

## Non-goals (for now)

- Bank scraping or stored bank passwords. The app holds only an aggregator access token, in the macOS Keychain.
- CSV import. The aggregator feed replaces it.
- OCR. All current statements contain extractable text.
- An LLM call, prompt, or advice text inside this app. That belongs to the agent.
- Cloud deployment.
- Multi-user, multi-currency, investments, taxes, budgeting envelopes.

## Tech stack

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Strong data tooling, readable |
| CLI | Typer + Rich | Simple commands, nice tables |
| Config | pydantic-settings, env vars prefixed `FIN_` | One typed settings object, no hardcoded paths |
| DB access | SQLAlchemy 2.0 | Typed queries, no dialect-specific SQL |
| Migrations | Alembic | Versioned schema; upgrades never lose imported data |
| Local DB | SQLite file in `data/` | Zero setup |
| PDF text | `pypdf` (layout extraction mode) | Pure Python; keeps statement columns aligned where `pdftotext` scrambles them |
| Daily feed (later) | Third-party aggregator, provider not yet chosen | No manual downloads; the app's only outbound connection |
| Agent interface (later) | MCP server, official `mcp` Python SDK, stdio transport | Typed tools any agent framework can call; stdio opens no port |
| Web UI (later) | FastAPI + Jinja2 + HTMX, bound to 127.0.0.1 | Little JavaScript |
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
    sync/                       aggregator client and daily sync (ONLY place with network; later)
    categorize/                 categories, rules engine, merchant normalization
    analysis/                   reports and insights (pure functions over domain objects)
    cli/                        Typer commands (thin)
    mcp_server/                 MCP tools for the agent (thin, later)
    web/                        FastAPI app (thin, later)
  tests/
    fixtures/                   synthetic statement text and aggregator responses only
  data/                         gitignored: SQLite DB, real statement samples
```

### Dependency direction

```
cli, mcp_server, web  ──►  ingest, sync, categorize, analysis  ──►  db  ──►  domain
                                     └───────────────────────────────────►  domain
```

- `domain` depends on nothing in the project.
- `analysis` operates on domain objects, not ORM rows, so it is testable without a database.
- `cli`, `mcp_server`, and `web` are three thin front ends over the same functions. None of them imports another.

## Data flow

```
 PDF statement ─► text ─► detect format ─► bank parser ─► reconcile (must balance to the cent)
                                                              │
                                                              ▼
                                                   transactions + balance snapshot (DB)
                                                              ▲
 Aggregator ─► daily sync ─► dedup ───────────────────────────┘  (source = aggregator, provisional;
                                                                 a later statement upgrades
                                                                 these rows in place)
                               │
                               ▼
                         categorize (rules)  ◄── user rules / manual overrides
                               │
                               ▼
                         analysis: balances, spending by category,
                         per-merchant stats, recurring charges, insights
                               │
              ┌────────────────┼─────────────────┐
              ▼                ▼                 ▼
          fin CLI       MCP server (stdio)    web UI (127.0.0.1)
                               │
                               ▼
                    finance subagent (local model)
                               │
                               ▼
                    overarching agent ─► user
```

## Agent interface

The MCP server is how the agent reaches this app. Details are in the Phase 14 and 19 specs; the rules are fixed here.

- **Transport is stdio.** The agent launches `fin mcp serve` as a child process. No port is opened, so nothing else on the machine or network can connect.
- **Read tools come first** (Phase 14): accounts, balances, transactions, reports, findings, and data coverage (which periods each account has, how old the newest data is, and which periods are statement-audited).
- **Write tools come later** (Phase 19) and touch only the interpretation layer: a transaction's category, proposed rules and merchant aliases, transfer-pair confirmations, the status of a finding, and an advice log. The ledger is immutable to the agent: no tool changes an amount, date, balance, or account, imports or deletes anything, triggers a sync, or overrides reconciliation.
- **Every agent write** is tagged as made by the agent, never overwrites a value the user set by hand, and can be undone. The user reviews agent writes with `fin review`. Rules and aliases stay proposals until the user approves them.
- **Tools are thin.** Each one validates its arguments, calls one function in `analysis`, `categorize`, or `db`, and returns the result. A tool contains no business logic.
- **Results are plain data:** money as integer cents, dates as ISO strings, the sign convention from `AGENTS.md`, and a hard cap on rows per call with paging.
- **Results carry raw data** (merchant names, amounts, cardholder names, last 4 digits). Full account numbers are never stored, so they are never returned.

## Privacy boundary

Raw financial data stays on the household's machine, with one known exception upstream.

- **Aggregator.** The aggregator company sees every transaction it delivers. This is accepted in exchange for not importing by hand, and nothing in this app can reduce it. The aggregator is the app's only outbound connection; all of that code lives in `src/finances/sync/`. Nothing else in the app touches the network, and the app sends the aggregator nothing except its credentials and sync requests.
- **Agent.** The MCP server hands raw data to whatever process launched it. That is acceptable only because the agent runs on a **local model** on the same machine. The app cannot check this. If the finance subagent, or the overarching agent that reads its answers, is ever moved to a hosted model, raw data leaves the machine through the agent, and this design must be revisited first.
- **Remote access.** The app never listens on a public interface: the MCP server uses stdio and the web UI binds to 127.0.0.1. Remote access is provided outside the app, by an encrypted private network between the household's own devices (a WireGuard-based mesh VPN such as Tailscale) that forwards to the loopback port. A tunnel service that decrypts traffic on its own servers is not used, since it would see the data. The web UI still requires a login (Phase 20), so reaching the port is not enough.
- **Logs.** Tool arguments and results, and aggregator responses, are never logged at INFO or above (`AGENTS.md` privacy rule 4).

## Data model (overview)

Details are in the phase specs. Core tables:

- `accounts`: one row per bank account or card account, matched to statements by last 4 digits.
- `statements`: one row per imported statement file, with its period, opening and closing balance, and row counts. Only reconciled statements are stored.
- `transactions`: one row per transaction, with posted and transaction dates, section, card last4, and cardholder; deduplicated by a fingerprint.
- `balance_snapshots`: balance of an account as of a date (from each statement, and from each aggregator pull).
- `feed_items`: which aggregator transaction a stored transaction came from, so the same feed row is never stored twice and a pending row can be replaced in place (Phase 17a).
- `feed_pulls`: one row per applied aggregator feed, with counts, the reported balance, and the balance drift (Phase 17a).
- `categories`, `category_rules`, `merchants` (Phase 11).

`transactions.source` records where a row came from: `aggregator` rows are provisional, and a reconciled statement upgrades them in place to `statement`, keeping their ids so categories and notes survive. A posted feed row inside a statement's period that the statement does not print is dropped, and a feed row that arrives after its statement is linked to the statement's row instead of being stored again (Phase 8). Rows are paired by exact amount and by posted dates at most five days apart.

### Statement parsing design

- Each format is a `StatementParser` with `detect(first_page_text)` and `parse(pages_text) -> ParsedStatement`. Parsers work on **text**, so tests use synthetic text fixtures and never need real PDFs.
- **Reconciliation is the safety net**: opening balance + sum of parsed lines must equal the closing balance exactly, and declared section totals must match. A statement that does not reconcile is not imported (unless explicitly overridden and flagged).
- Statement dates often omit the year; a shared helper infers it from the statement period (handles December to January).
- Real statements in `data/samples/` are used only by opt-in tests that report pass/fail, never content.

Transfers between the household's own accounts (card payments from checking, moves between checking and savings) must be excluded from spending, or spending is double-counted. Phase 11 handles this.

## Open decisions

- **Aggregator provider.** Must cover Capital One, Bank of America, Citi, Truist, and Marcus, be available to an individual, and ideally report pending versus posted and a per-card identifier. Decide before Phase 17 is specified. Phase 17 comes early in the build order, so this is the next decision needed.
- **Remote access method.** The default above is a mesh VPN with the app on loopback. Confirm before Phase 20.
