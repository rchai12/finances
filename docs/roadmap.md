# Roadmap

Each phase is sized for one focused coding session: a few modules, their tests, and a CLI command to exercise them. Every phase ends in a working, tested state.

**Input decision:** a third-party **aggregator** is the daily feed. Its rows are provisional. Monthly **PDF statements** are the audit and the record (see `docs/statement-formats.md`): each is reconciled against its own opening and closing balances, then upgrades the matching provisional rows in place. Statements also supply what the feed lacks, such as the cardholder on shared cards.

Status: the specs for Phases 2 to 10 were written before the small-phase rules and before the agent redesign. Each is re-issued as lettered sub-phases, with a verification guide, before the coder receives it. Phases 11 and later are outlines.

**Build order:** 2 → 3 → 4 → 17 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 19 → 16 → 20. Phases 5 and 6 (more statement parsers) can be built any time after 4, when audit coverage for those banks is wanted.

| # | Phase | Outcome | Spec |
|---|---|---|---|
| 1 | Project skeleton | Installable package, config, logging, `fin doctor`, tests run | [phase-01](phases/phase-01-skeleton.md) |
| 2 | Database and accounts | Money helpers, `accounts` schema + migration, repositories, `fin db upgrade`, `fin accounts add/list` | sub-phases below |
| 3 | Statement import core | PDF text, parser registry, reconciliation, dedup, `fin import statement/folder` | [phase-03](phases/phase-03-statement-import-core.md) |
| 4 | Capital One parser | Multi-cardholder card statements, year wrap | [phase-04](phases/phase-04-capital-one-parser.md) |
| 5 | BoA + Citi parsers | Two more card formats | [phase-05](phases/phase-05-boa-citi-parsers.md) |
| 6 | Truist + Marcus parsers | Checking/savings; all PDF samples import | [phase-06](phases/phase-06-deposit-parsers.md) |
| 7 | *Removed* | Was "CSV import". The aggregator feed (Phase 17) replaces it. The old spec is kept as reference for Phases 8 and 17 | |
| 8 | Statements supersede provisional rows | In-place upgrade of aggregator rows by a reconciled statement; order of arrival does not matter | draft written for CSV: [phase-08](phases/phase-08-statement-supersedes-csv.md), to be re-issued |
| 9 | Test hardening | Property-based, fuzz, golden snapshot, migration, and end-to-end workflow tests for the import pipeline | [phase-09](phases/phase-09-test-hardening.md) |
| 10 | Quality gates | Per-module coverage gates, mutation testing, `check.ps1`, pre-commit hooks, optional CI | [phase-10](phases/phase-10-quality-gates.md) |
| 11 | Categorization and transfers | Merchant normalization, categories, rules, own-account transfer matching | outline below |
| 12 | Core reports | Balances, net worth, spending by category/merchant/person, month-over-month | outline below |
| 13 | Insights engine | Recurring charges, spikes, frequent small purchases, findings list | outline below |
| 14 | Agent interface (MCP server) | Read-only MCP tools over stdio for the finance subagent: accounts, balances, transactions, reports, findings, data coverage | outline below |
| 15 | *Removed* | Was "LLM advice". Advice now comes from the external agent | |
| 16 | Local web UI | FastAPI dashboard on 127.0.0.1, statement upload, review of agent writes | outline below |
| 17 | Aggregator sync | Daily pull of transactions and balances into provisional rows; the only network code | outline below |
| 18 | *Removed* | Was "Azure deployment". The app stays on the household's machine | |
| 19 | Agent write tools | MCP tools that write the interpretation layer only, tagged, reversible, with `fin review` | outline below |
| 20 | Remote access | Web UI login and hardening so the app can sit behind a private VPN | outline below |

Phase numbers are stable. A removed phase keeps its number, and a phase that is too large for one coding session is split into lettered sub-phases (`2a`, `2b`, ...), never renumbered.

## Sub-phases

Verification guides have the same file name under `verification/`.

| # | Sub-phase | Outcome | Spec |
|---|---|---|---|
| 2a | Test infrastructure and coverage gate | `pytest-cov`, 85% branch gate, `tmp_settings` fixture, Phase 1 gaps tested | [phase-02a](phases/phase-02a-test-infrastructure.md) |
| 2b | Money helpers | `parse_money`, `format_cents` | [phase-02b](phases/phase-02b-money-helpers.md) |
| 2c | Account model, ORM, engine | `AccountType`, `Account`, `accounts` ORM table, engine and `session_scope` | to be written after 2b is built |
| 2d | Alembic and first migration | `0001` creates `accounts`; `upgrade_to_head`; `db_session` fixture | to be written |
| 2e | Account repositories | create, get by name, find by last4, list | to be written |
| 2f | `fin db upgrade` | Command plus the `fin doctor` schema check | to be written |
| 2g | `fin accounts add/list` | The two commands | to be written |

Phase 2 now creates only the `accounts` table. `import_batches`, `transactions`, and `balance_snapshots` each arrive with their own migration in the Phase 3 sub-phase that first uses them, so their columns can account for the aggregator feed.

Testing rules for every phase are in [testing.md](testing.md). Each later phase adds its critical modules to the coverage and mutation gates from Phase 10.

## Outlines

### Phase 11: Categorization and transfers
- Tables: `categories` (with `is_sensitive`, `is_transfer`, `is_income` flags), `category_rules` (pattern, match type, priority), `merchants` (display name, kind: national_chain / local / p2p / unknown).
- Seed a default category tree (Groceries, Dining, Coffee & Dessert, Subscriptions & Digital, Shopping, Travel, Gas, Parking, Utilities & Internet, Health*, Insurance, Entertainment, Gaming, Fees & Interest, Transfers, Income...). *sensitive.
- Merchant normalization tuned to the formats seen: strip processor prefixes (`SQ *`, `TST*`, `PP*`, `PAYPAL *`, `SP `, `GOOGLE *`, `AMAZON MKTPL*<id>`), store numbers (`#1234`), phone numbers, run-together city+state suffixes, debit-card prefixes (`DEBIT CARD PURCHASE`, `DEBIT CARD RECURRING PYMT`), and embedded `MM-DD` dates.
- **Transfer matching** (important: the samples are full of them): card payments (`CAPITAL ONE MOBILE PYMT`, `PAYMENT FROM CHK`, autopay) and bank-to-bank transfers. Pair an outflow in one account with an inflow of the same amount in another account within N days; also keyword rules for transfers to untracked accounts (e.g. a CD). Paired and keyword transfers are excluded from spending.
- Refunds and reversals (credits from a merchant) net against that merchant's spending.
- Use the merchant name and category supplied by the aggregator as low-priority hints (useful, but e.g. own-account savings transfers are labeled "Investments").
- Transfer matching must use amount and date, not card numbers in descriptions (they do not match; see formats doc).
- Rule engine: highest priority wins; manual overrides are never overwritten.
- CLI: `fin categorize`, `fin rules add/list`, `fin uncategorized`, `fin tx set-category`, `fin transfers review`.

### Phase 12: Core reports
- Pure functions in `analysis/` returning dataclasses (reused by the web UI).
- Balances per account from latest statement snapshot; net worth (cash minus card debt).
- Spending by category and by merchant for a month or range, using `transaction_date` when present; spending by cardholder (household of two).
- Month-over-month change. Statement periods do not align with calendar months; reports use calendar months and say when a month is only partly covered.

### Phase 13: Insights engine
- Per-merchant stats: visits per month, average ticket, trend vs 3-month baseline, time-of-week pattern.
- Recurring charge detection (similar amount, regular interval), including many charges to the same digital merchant (e.g. app store billing) grouped together.
- Findings with type, severity, estimated monthly savings: spike, frequent small purchases, subscription overlap, price increase, interest charged, fees charged.
- All local and rule-based. `fin insights`.

### Phase 14: Agent interface (MCP server)
- New package `src/finances/mcp_server/`; new dependency: the official `mcp` Python SDK. `fin mcp serve` runs the server on **stdio only** (no HTTP transport, no port).
- Read-only tools, each a thin wrapper over one existing function in `analysis` or `db`:
  - `list_accounts`, `get_balances`, `get_net_worth`
  - `list_transactions` (filters: account, date range, category, merchant, cardholder, text; hard row cap with paging)
  - `spending_by_category`, `spending_by_merchant`, `spending_by_cardholder`, `month_over_month`
  - `list_findings` (the Phase 13 insights), `merchant_stats`
  - `data_coverage`: per account, the periods covered, the date of the newest data, which periods are statement-audited, and any sync drift, so the agent can say when its answer rests on stale or partial months
- Results: integer cents, ISO dates, holder-perspective signs, raw merchant and cardholder names. Tool descriptions state the sign convention and units, since the agent reads them.
- The server opens the database read-only where the dialect allows it, and no tool calls a write repository function.
- Tool arguments and results are never logged at INFO or above.
- Tests drive the server through the SDK's in-memory client against a migrated temp database. No subprocess, no socket.
- Depends on Phases 12 and 13. Will be specified as several sub-phases (server skeleton plus one tool, then tool groups).

### Phase 15: removed
The app no longer calls an LLM. The finance subagent of the overarching agent produces advice from the Phase 14 tools.

### Phase 16: Local web UI
- FastAPI + Jinja2 + HTMX, bound to 127.0.0.1.
- Dashboard, transactions with category editing, insights; statement upload page that calls the same import service; sync status and a re-link prompt when a bank connection breaks; the `fin review` queue of agent writes.

### Phase 17: Aggregator sync
- Blocked on the provider choice (`architecture.md`, Open decisions).
- All network code in `src/finances/sync/`, behind a small `FeedClient` protocol so tests use a fake client and recorded synthetic responses. No test touches the network.
- Access token in the macOS Keychain (via `keyring`), never in the database, `.env`, or logs. `fin sync link` stores it; `fin sync run` pulls; `fin sync status` shows the last successful pull per account and any connection that needs re-linking.
- Rows are inserted with `source = aggregator`, provisional, deduplicated on the provider's transaction id. Pending transactions are stored as pending and replaced when they post; they are excluded from spending until then.
- Balance check after each pull: the stored balance plus new posted rows must equal the balance the provider reports, otherwise the account is flagged as drifted and the agent's `data_coverage` tool reports it.
- Scheduling is outside the app (a `launchd` job calling `fin sync run`). The agent cannot trigger a sync.
- Will be specified as several sub-phases (client protocol and fake, token storage, row mapping, sync service, CLI).

### Phase 18: removed
No cloud deployment. If the app ever moves off the household's machine, the privacy boundary in `architecture.md` must be redesigned first.

### Phase 19: Agent write tools
- Depends on Phases 11, 13, and 14. Rules are fixed in `architecture.md`, Agent interface.
- Schema: an origin column (`user` / `rule` / `agent`) wherever a category, alias, or transfer pairing is stored; a `finding_status` table; an `advice_log` table; an `agent_changes` journal holding the previous value of everything the agent changed.
- Tools, in the order they are built: `set_category` (uncategorized or agent-set transactions only), `set_finding_status`, `log_advice` / `list_advice`, `confirm_transfer_pair`, `propose_rule`, `propose_merchant_alias`.
- A tool refuses to overwrite a `user` value. Proposals have no effect until approved.
- `fin review` lists agent changes and proposals; accept, reject, or undo each. The web UI gets the same queue.
- No tool for amounts, dates, balances, accounts, imports, deletions, sync, or reconciliation overrides.

### Phase 20: Remote access
- The app still binds to 127.0.0.1 only. The VPN that forwards to it is configured outside the repository; this phase ships the runbook, not the VPN.
- Web UI login for a single household: password hash from configuration, signed session cookie with `Secure`, `HttpOnly`, `SameSite=Strict`, idle timeout, lockout after repeated failures.
- CSRF tokens on every state-changing request; allowed-host check so only the configured VPN hostname and localhost are served.
- `fin doctor` fails if the web UI is configured to bind to anything other than loopback.
