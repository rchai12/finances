# Architecture

## Purpose

A personal finance tool for one household (two people, several shared cards). It pulls transactions daily from a third-party aggregator (provisional) and imports monthly PDF statements as the audit (the record), computes balances, ranks spending by category and merchant, and finds specific places to cut back.

It is one platform inside a larger personal AI system. An overarching agent, running on a local model, delegates work to subagents (email, reminders, tasks, stock analysis). One of those subagents uses this app through an MCP server to analyze spending patterns and give advice. The app supplies the data, the reports, and the rule-based findings. It contains no LLM and does not produce advice itself.

Everything runs on one machine the household owns (a Mac Studio): the overarching agent, its subagents, the local model, and this app with its database. There is no cloud deployment.

The household reaches that machine remotely over a private, encrypted connection. The app itself is never published to the internet (see Privacy boundary).

It also works on its own through the `fin` CLI and a local web UI (from Phase 16a).

## Goals

- Raw financial data stays on the household's machine. The app's only outbound connection is to the aggregator.
- The agent gets typed tools that return real merchants and amounts, so its advice can be specific ("$118/mo at one bakery, up 2x since summer").
- Arithmetic is done here, in tested code, not by the model: balances, totals, trends, and findings come back from tools already computed.
- Every report has one implementation, shared by the CLI, the web UI, and the MCP server: its rules are pure functions in `domain`, and `analysis` loads the data and applies them.
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
| Daily feed | SimpleFIN Bridge, through the standard library's `urllib` | Built for individuals, read-only, about $15 a year; the app's only outbound connection |
| Agent interface (Phase 14, from 14a) | MCP server, official `mcp` Python SDK 2.x (`MCPServer`), stdio transport | Typed tools any agent framework can call; stdio opens no port |
| Web UI | FastAPI + Jinja2, bound to 127.0.0.1; Chart.js 4.4.6 for charts | Pages work without scripts; the only scripts are the site's own files (policy `script-src 'self'`): a pinned, hash-checked Chart.js in `static/vendor/` and `static/charts.js`, loaded only where a page draws charts (Phase 16k). No CDN, no inline script, no `eval` |
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
    domain/                     pure dataclasses, enums, money helpers, and every report's rules (no project imports)
    db/                         engine/session, ORM models, repositories, backups
    ingest/                     PDF text, statement model, reconciliation, dedup, import service
      parsers/                  one module per statement format (Capital One, BoA, Citi, Truist, Marcus)
    sync/                       SimpleFIN client and daily sync (the ONLY place with network)
    categorize/                 the categorize run and transfer pairing
    analysis/                   reports, search, insights, recurring, upcoming, forecast, net worth, refunds, health, budgets, the dashboard: load through db, apply domain rules
    views/                      display rows (text) built once for cli and web
    cli/                        Typer commands (thin)
    mcp_server/                 MCP tools for the agent on stdio (thin; from Phase 14a)
    web/                        FastAPI app (thin): app.py (application, security, clock hooks), routes/ (one router per area), shared page and form helpers, templates, static files, vendored Chart.js
  tests/
    fixtures/                   synthetic statement text and aggregator responses only
  data/                         gitignored: SQLite DB, real statement samples
```

### Dependency direction

```
cli, mcp_server, web  ──►  ingest, sync, categorize, analysis  ──►  db  ──►  domain
                                     └───────────────────────────────────►  domain
```

- `domain` depends on nothing in the project. The rules (what counts as spending, a transfer candidate, a recurring series, a finding, a budget's progress, a data-health problem) live here as pure functions and are tested without a database.
- `analysis` takes a `Session`, loads through `db`, applies the `domain` rules, and returns domain objects and plain data (integer cents, dates). It never formats text. It is tested on a temporary migrated database.
- `views` turns analysis results into display text for `cli` and `web` (Phase 22). `mcp_server` does **not** use `views`: the agent's tools return plain data, so they wrap `analysis` and `db` directly.
- `cli`, `mcp_server`, and `web` are three thin front ends over the same functions. None of them imports another, except that `fin web serve` and `fin mcp serve` import the app or server they start.
- **`views` only format** (Phases 36b and 36c): they take what `analysis` returns and never open the database, the Keychain, or the network; a test on the source enforces it. `analysis` may call `categorize`'s read functions (such as `transfer_suggestions`), since both sit in one tier.
- **Today's date** for anything a person reads (the current month, "today", days since) is the machine's local date, read through one function (Phase 31). Stored timestamps (feed pulls, imports) are UTC.

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
- **Read tools come first** (Phase 14). Built (14a): `list_accounts`, `get_balances`, `get_net_worth`, each reading through a session that cannot write. Built (14b): `list_transactions`, `get_spending`, `month_over_month`. Built (14c): `get_insights`, `get_recurring`, `get_upcoming`, `get_forecast`, `get_budgets`. Built (14d): the work queues `list_uncategorized`, `list_categories`, `list_rules`, `list_transfers`, `list_transfer_suggestions`. Built (14e): `data_coverage` (which periods each account has, how old the newest data is, and which periods are statement-audited) and `find_merchants`. The read tools of Phase 14 are complete.
- **The agent recommends; it does not act.** Write tools (Phase 19; built for categories, transfers, rules, and merchant aliases in 19a to 19e; finding status once findings have one) store only **proposals** (a category, a transfer or not a transfer, a rule, a merchant alias, a finding's status) and the agent's own advice log. A proposal changes nothing until a person accepts it with `fin review` or the web UI. The ledger is untouchable by the agent: no tool changes an amount, date, balance, or account, imports or deletes anything, triggers a sync, or overrides reconciliation.
- **Tools are thin.** Each one validates its arguments, calls one function in `analysis`, `categorize`, or `db`, and returns the result. A tool contains no business logic.
- **Results are plain data:** money as integer cents, dates as ISO strings, the sign convention from `AGENTS.md`, and a hard cap on rows per call with paging.
- **Results carry raw data** (merchant names, amounts, cardholder names, last 4 digits). Full account numbers are never stored, so they are never returned.

## Privacy boundary

Raw financial data stays on the household's machine, with one known exception upstream.

- **Aggregator.** The aggregator company (SimpleFIN Bridge, and the data provider behind it) sees every transaction it delivers. This is accepted in exchange for not importing by hand, and nothing in this app can reduce it. The aggregator is the app's only outbound connection; all of that code lives in `src/finances/sync/`. Nothing else in the app touches the network, and the app sends the aggregator nothing except its credentials and sync requests.
- **Agent.** The MCP server hands raw data to whatever process launched it. That is acceptable only because the agent runs on a **local model** on the same machine. The app cannot check this. If the finance subagent, or the overarching agent that reads its answers, is ever moved to a hosted model, raw data leaves the machine through the agent, and this design must be revisited first.
- **Remote access.** The app never listens on a public interface: the MCP server uses stdio and the web UI binds to 127.0.0.1. Remote access is provided outside the app, by an encrypted private network between the household's own devices (a WireGuard-based mesh VPN such as Tailscale) that forwards to the loopback port. A tunnel service that decrypts traffic on its own servers is not used, since it would see the data. A login for the web UI is planned (Phase 20) and not built yet: until then, anyone who can reach the loopback port through the private network can use the site, so that network must include only the household's own devices.
- **Logs.** Tool arguments and results, and aggregator responses, are never logged at INFO or above (`AGENTS.md` privacy rule 4).

## Data model (overview)

Details are in the phase specs. Core tables:

- `accounts`: one row per bank account or card account, matched to statements by last 4 digits.
- `statements`: one row per imported statement file, with its period, opening and closing balance, and row counts. Only reconciled statements are stored.
- `transactions`: one row per transaction, with posted and transaction dates, section, card last4, and cardholder; deduplicated by a fingerprint.
- `balance_snapshots`: balance of an account as of a date (from each statement, and from each aggregator pull).
- `feed_items`: which aggregator transaction a stored transaction came from, so the same feed row is never stored twice and a pending row can be replaced in place (Phase 17a).
- `feed_pulls`: one row per applied aggregator feed, with counts, the reported balance, and the balance drift (Phase 17a).
- `feed_seen_accounts`: every aggregator account a sync has received under a link, mapped or not, with the days first and last seen and whether the household chose not to track it, so new accounts can be offered for setup (Phase 16d).
- `categories` (groups and categories in one table, with transfer, income, and sensitive flags), `category_rules`, `transaction_categories` (each transaction's category and whether a rule or a person set it) (Phase 11a).
- `transaction_tags` and `transaction_notes`: a person's labels on a transaction (many) and one note; deleted with a feed transaction (Phase 28c); shown on a transaction's page, and search filters by tag (Phase 28f).
- `transaction_splits`: the parts of a split transaction, each with signed cents and a category, adding up to it exactly (`domain/splits.py`, critical); a split transaction counts as decided by a person (Phase 28d); reports grouped by category and search count its parts, analyses of charges at a merchant the whole transaction (Phase 28e).
- `merchant_aliases`: a cleaned merchant name merged into another, one step long; reports group by the merged name and a rule matches either name (Phase 28a).
- `transfer_pairs` and `transfer_rejections`: an outflow and an inflow that are one transfer, and pairs the household said are not (Phase 11c).
- `people`, `account_owners`, `cardholder_aliases`: who owns each account and who each statement cardholder name is (Phase 21).
- `feed_accounts`: which SimpleFIN account, under which named link, feeds which of ours (Phase 17c).
- `budgets`: a monthly target per category or group (Phase 26a).
- `audit_log`: one row per change a person makes (and, from 34b, statement imports and backup restores and deletions): when (UTC), who, the action, the record, and short text before and after; written in the same transaction as the change and never edited (Phase 34a).
- `proposals` and `advice_log`: the agent's suggestions (a kind, the transaction (for a rule, an example it matches), the second transaction of a transfer proposal, the proposed value, a rule's pattern, match, and priority, an alias's merchant to merge, its reason, open, accepted, or declined) and its own notes; the only tables an MCP tool writes (Phases 19a, 19c, and 19d).
- `sync_failures`: the last failed sync of each SimpleFIN link, with its time (UTC) and a short message, so `fin health` and the dashboard can say why a sync failed (Phase 33).

Backups are files, not tables: checked SQLite copies in `FIN_BACKUP_DIR` (Phase 24).

`transactions.source` records where a row came from: `aggregator` rows are provisional, and a reconciled statement upgrades them in place to `statement`, keeping their ids so categories and notes survive. A posted feed row inside a statement's period that the statement does not print is dropped, and a feed row that arrives after its statement is linked to the statement's row instead of being stored again (Phase 8). Rows are paired by exact amount and by posted dates at most five days apart. A whole statement, or a whole pull, is paired at once: the most pairs possible, then the most pairs on the same side of a statement period's first and last day, then the fewest days apart, so the order rows arrive or are listed in changes nothing (Phase 9). Two limits are accepted: a feed row dated inside an imported statement's period that the statement does not print is not stored, even when it belongs to a neighbouring statement not yet imported; and a feed row and a statement line of the same amount at most five days apart, with nothing else to pair with, count as one purchase even across a period's edge.

The command line and the web show the same views. `finances.views` builds each view's rows once, as plain text in small dataclasses (Phase 22); `cli` renders them with Rich and `web` with Jinja, and neither builds rows of its own.

### Statement parsing design

- Each format is a `StatementParser` with `detect(first_page_text)` and `parse(pages_text) -> ParsedStatement`. Parsers work on **text**, so tests use synthetic text fixtures and never need real PDFs.
- **Reconciliation is the safety net**: opening balance + sum of parsed lines must equal the closing balance exactly, and declared section totals must match. A statement that does not reconcile is not imported (unless explicitly overridden and flagged).
- Statement dates often omit the year; a shared helper infers it from the statement period (handles December to January).
- Real statements in `data/samples/` are used only by opt-in tests that report pass/fail, never content.

Transfers between the household's own accounts (card payments from checking, moves between checking and savings) must be excluded from spending, or spending is double-counted. Phase 11c pairs them, and every report leaves pairs and transfer categories out (Phase 12a).

## People

The household has two people and several shared cards. Every account is owned by one person or is joint, and every purchase can be attributed to a person: the cardholder printed on the statement when there is one, otherwise the account's owner. Reports and the agent's tools can filter and group by person, bank, and card. This is a view, not access control: both people see everything (Phase 21).

Each person may have their own SimpleFIN subscription, since one person's bank logins are not the other's. The app therefore keeps several named SimpleFIN links, each with its own access URL in the Keychain, and maps each SimpleFIN account under a link to one of ours (Phase 17c; Phase 17b shipped with a single, unnamed link).

## Open decisions

- **Aggregator provider: decided, SimpleFIN Bridge** (Phase 17b). Still to confirm by linking: that all five banks connect, and the sign SimpleFIN gives a card balance (the drift check of Phase 17a will show a wrong sign). SimpleFIN reports pending transactions but no per-card identifier, so the cardholder on shared cards still comes from statements. As understood, SimpleFIN Bridge gets its bank connections from a larger aggregator, so two companies see the transactions.
- **Remote access method.** The default above is a mesh VPN with the app on loopback. Confirm before Phase 20.
