# Roadmap

Each phase is sized for one focused coding session: a few modules, their tests, and a CLI command to exercise them. Every phase ends in a working, tested state.

**Input decision:** a third-party **aggregator** is the daily feed. Its rows are provisional. Monthly **PDF statements** are the audit and the record (see `docs/statement-formats.md`): each is reconciled against its own opening and closing balances, then upgrades the matching provisional rows in place. Statements also supply what the feed lacks, such as the cardholder on shared cards.

Status: Phases 1 and 2 are built. The specs for Phases 3 to 10 were written before the small-phase rules and before the agent redesign. Each is re-issued as lettered sub-phases, with a verification guide, before the coder receives it. Phases 11 and later are outlines.

**Build order:** 2 → 3 → 4 → 17a → 8 → 17b → 17c → 21 → 9 → 10 → 11 → 12 → 13 → 14 → 19 → 16 → 20. Phases 5 and 6 (more statement parsers) can be built any time after 4, when audit coverage for those banks is wanted.

| # | Phase | Outcome | Spec |
|---|---|---|---|
| 1 | Project skeleton | Installable package, config, logging, `fin doctor`, tests run | [phase-01](phases/phase-01-skeleton.md) |
| 2 | Database and accounts | **Done.** Money helpers, `accounts` schema + migration, repositories, `fin db upgrade`, `fin accounts add/list` | sub-phases below |
| 3 | Statement import core | PDF text, parser registry, reconciliation, dedup, `fin import statement/folder` | sub-phases below |
| 4 | Capital One parser | Multi-cardholder card statements, year wrap, interest and fee lines, declared section totals; the opt-in check of real statements | [phase-04](phases/phase-04-capital-one-parser.md) (re-issued for the current format) |
| 5 | BoA + Citi parsers | Two more card formats, and the shared `find_labeled_amount` helper | [phase-05](phases/phase-05-boa-citi-parsers.md) (re-issued for the current format) |
| 6 | Truist + Marcus parsers | Checking and savings statements: section-driven signs, checks, debit card details, running-balance signs; every kind of statement has a parser | [phase-06](phases/phase-06-deposit-parsers.md) (re-issued for the current format); repairs from the first run on real statements: [phase-06a](phases/phase-06a-real-statement-repairs.md) |
| 7 | *Removed* | Was "CSV import". The aggregator feed (Phase 17) replaces it. The old spec is kept as reference for Phases 8 and 17 | |
| 8 | Statements supersede feed rows | A statement upgrades the feed's rows in place and drops the ones it does not print; a late feed row is linked to its statement row; order of arrival does not matter | [phase-08](phases/phase-08-statements-supersede-feed.md) (re-issued for the aggregator feed) |
| 9 | Test hardening | Property-based, fuzz, golden snapshot, migration, and end-to-end workflow tests for the import pipeline | [phase-09](phases/phase-09-test-hardening.md) |
| 10 | Quality gates | Per-module coverage gates, mutation testing, `check.ps1`, pre-commit hooks, optional CI | [phase-10](phases/phase-10-quality-gates.md) |
| 11 | Categorization and transfers | Merchant normalization, categories, rules, own-account transfer matching | outline below |
| 12 | Core reports | Balances, net worth, spending by category/merchant/person, month-over-month | outline below |
| 13 | Insights engine | Recurring charges, spikes, frequent small purchases, findings list | outline below |
| 14 | Agent interface (MCP server) | Read-only MCP tools over stdio for the finance subagent: accounts, balances, transactions, reports, findings, data coverage | outline below |
| 15 | *Removed* | Was "LLM advice". Advice now comes from the external agent | |
| 16 | Local web UI | FastAPI dashboard on 127.0.0.1, statement upload, review of agent writes | outline below |
| 17 | Aggregator sync | Daily pull of transactions and balances into provisional rows; the only network code | [phase-17a](phases/phase-17a-feed-core.md) (feed core), [phase-17b](phases/phase-17b-simplefin-sync.md) (SimpleFIN client and sync), [phase-17c](phases/phase-17c-sync-commands.md) (links, commands, Keychain), [phase-17d](phases/phase-17d-user-agent.md) (a user agent Cloudflare accepts) |
| 18 | *Removed* | Was "Azure deployment". The app stays on the household's machine | |
| 19 | Agent write tools | MCP tools that write the interpretation layer only, tagged, reversible, with `fin review` | outline below |
| 20 | Remote access | Web UI login and hardening so the app can sit behind a private VPN | outline below |
| 21 | People and ownership | The household's people; each account owned by one person or joint; statement cardholder names mapped to people; every view filterable by person, bank, and card | outline below |

Phase numbers are stable. A removed phase keeps its number, and a phase that is too large for one coding session is split into lettered sub-phases (`2a`, `2b`, ...), never renumbered.

## Sub-phases

Verification guides have the same file name under `verification/`.

| # | Sub-phase | Outcome | Spec |
|---|---|---|---|
| 2a | Coverage gate and shared fixture | `pytest-cov`, 85% branch gate, `tmp_settings` fixture, diagnostics tests | [phase-02a](phases/phase-02a-coverage-gate.md) |
| 2b | Tests for Phase 1 gaps | `mask_url` with a port and an IPv6 host; `fin doctor` exit code 1 | [phase-02b](phases/phase-02b-phase1-gap-tests.md) |
| 2c | `format_cents` | Integer cents to display text; the coder writes the body against given tests | [phase-02c](phases/phase-02c-format-cents.md) |
| 2d | `parse_money` | Money text to integer cents; the coder writes the body against given tests | [phase-02d](phases/phase-02d-parse-money.md) |
| 2e | `AccountType` and `Account` | The account enum and frozen dataclass in `domain/models.py` | [phase-02e](phases/phase-02e-account-model.md) |
| 2f | `validate_last4` | Accepts `None` or exactly four ASCII digits | [phase-02f](phases/phase-02f-validate-last4.md) |
| 2g | `accounts` table and `to_account` | SQLAlchemy dependency, seven ORM columns, and the row-to-`Account` conversion. A deliberately larger phase, to find the coder's limit | [phase-02g](phases/phase-02g-accounts-table.md) |
| 2h | `get_engine` and `session_scope` | Opens the SQLite database with foreign keys on for every connection; commit-or-rollback session scope. Harder logic at 2g's size, with library facts but no recipe | [phase-02h](phases/phase-02h-engine-and-session.md) |
| 2i | The first migration | Alembic dependency, given `env.py`, and migration `0001` whose `upgrade` and `downgrade` the coder writes; tests compare the migrated database with the ORM class | [phase-02i](phases/phase-02i-first-migration.md) |
| 2j | Running migrations from code | `head_revision`, `upgrade_to_head`, `current_revision` in `db/migrate.py`, plus `db_url` and `db_engine` test fixtures. Three Code steps | [phase-02j](phases/phase-02j-run-migrations.md) |
| 2k | `get_account_by_name` and `create_account` | The first two repository functions in `db/repositories.py`, tested against a migrated temporary database. First spec with a per-module 100% coverage step | [phase-02k](phases/phase-02k-create-and-get-account.md) |
| 2l | `find_accounts_by_last4` and `list_accounts` | The other two account repository functions | [phase-02l](phases/phase-02l-find-and-list-accounts.md) |
| 2m | The database and account commands | `fin db upgrade`, `fin accounts add`, `fin accounts list`, and the "Database schema" line in `fin doctor`. Two planned sub-phases joined into one (32 steps, four Code steps) to speed things up. This finishes Phase 2 | [phase-02m](phases/phase-02m-cli-commands.md) |

From 2c on, the spec gives the tests and the steps, and the coder writes the implementation. Sub-phases began at one unit of code each and have grown as the coder proved able: two or three units from 2g, four in 2m. That step-by-step format is kept as the `local-coder-specs` skill.

Phase 2 now creates only the `accounts` table. `import_batches`, `transactions`, and `balance_snapshots` each arrive with their own migration in the Phase 3 sub-phase that first uses them, so their columns can account for the aggregator feed.

### Phase 3 sub-phases

3a was specified for the small local model that built Phase 2. From 3b the coder is a more capable agent, so the remaining work is planned as three larger sub-phases instead of seven. Their size is a starting point and will be adjusted from the results.

| # | Sub-phase | What it delivers | Spec |
|---|---|---|---|
| 3a | Statement model and parsing helpers | `Section`, `StatementLine`, `ParsedStatement`; `parse_amount`, `infer_year`, `parse_month_day` | [phase-03a](phases/phase-03a-statement-model-and-helpers.md) |
| 3b | Statement checks and reading | `reconcile` with `ReconcileResult` (opening balance plus lines must equal closing, to the cent; declared section totals must match); `fingerprint_lines` for deduplication; `extract_pages` (adds `pypdf`); the parser registry (`register`, `unregister`, `registered_parsers`, `detect_parser`); test fixtures that build real PDFs | [phase-03b](phases/phase-03b-statement-checks-and-reading.md) |
| 3c | Storing and importing statements | Domain and ORM classes for `statements`, `transactions`, and `balance_snapshots`; migration `0002`; eight repository functions; `import_statement` (read, recognize, match an account, reconcile, deduplicate, store) and `import_folder`; a fake bank parser for tests | [phase-03c](phases/phase-03c-storing-and-importing-statements.md) |
| 3d | Import commands | `fin import statement`, `fin import folder`, `fin statements list`, `fin transactions list`, and one shared database check for all commands | [phase-03d](phases/phase-03d-import-commands.md). Independent of Phase 4; either can be built first |
| 3e | Table width | One `print_table` function for all five tables: fitted to a terminal, one line per row everywhere else. Replaces the fixed 200-column consoles from 3d | [phase-03e](phases/phase-03e-table-width.md). Independent of Phase 5; either can be built first |

3c joins the storage layer and the import service, which were planned separately: the service is the only user of the new repositories. The commands stay in 3d because they are a thin layer over finished functions.

Changes from the original Phase 3 draft, made for the aggregator design and for simplicity:

- The table of imported files is named `statements`, not `import_batches`. With CSV import gone, a statement is the only kind of file imported; aggregator pulls get their own record in Phase 17.
- `transactions` gains a pending flag and keeps an external id, so aggregator rows fit without a redesign. Its `source` is `statement` or `aggregator`.
- `transactions` stores one description (as printed, whitespace collapsed). The separate normalized description waits for Phase 11, which defines merchant normalization.
- `find_labeled_amount` moves to Phase 4, where the first real parser shows what it needs.
- The opt-in real-sample test harness also moves to Phase 4. It cannot do anything until a parser exists, and it should be written on the machine that holds `data/samples/`.
- There is no way to import a statement that does not reconcile. The draft had an override flag; it can be added if a real statement ever needs it, and until then an unreconciled statement always means a parser mistake.
- Fingerprints use one scheme for every line (account, posted date, amount, normalized description, card digits, reference, and an occurrence number). The draft had a second scheme for lines with a reference number; with CSV import gone it had no purpose, and four-digit reference numbers are not unique.
- `infer_year` also tries the year after the period ends, so a row dated in early January is found on a statement that closes in late December.

Testing rules for every phase are in [testing.md](testing.md). Each later phase adds its critical modules to the coverage and mutation gates from Phase 10.

## Outlines

### Phase 21: People and ownership
- Decided with the owner: separation by person is for **views and reports**, not privacy between the two people; both see everything.
- Table `people` (name). Each account is owned by one person or is **Joint**, kept in its own table so the `accounts` table and its tests stay as they are.
- Statement cardholder names (`JANE DOE` on a shared card) map to people through an alias table. A purchase belongs to the cardholder's person when the statement names one, otherwise to the account's owner, otherwise to Joint.
- Commands: `fin people add/list`, `fin people alias --person NAME --cardholder "TEXT"`, `fin accounts set-owner --account NAME --owner PERSON|joint`; `fin accounts list` and `fin transactions list` gain an owner or person column and a `--person` filter.
- SimpleFIN links (17c) stay independent labels: a link is whose SimpleFIN subscription it is, not who owns each account in it.

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
- Spending by category and by merchant for a month or range, using `transaction_date` when present; spending by person (Phase 21: the cardholder's person when the statement names one, otherwise the account's owner, otherwise Joint), by bank, and by card.
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
  - `list_transactions` (filters: account, bank, card, person, date range, category, merchant, text; hard row cap with paging)
  - `spending_by_category`, `spending_by_merchant`, `spending_by_person`, `month_over_month`
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
- **17a, the feed core, is specified** and needs no provider: a provider-neutral `AccountFeed` (transactions, removed ids, a balance) is stored by `apply_feed` as provisional rows, with pending rows replaced in place, statement-confirmed rows left alone, and balance drift recorded per pull in `feed_pulls`. The provider's transaction id lives in `feed_items`, not on `transactions`. It unblocks Phase 8.
- **17b, the SimpleFIN client and sync, is specified**: claiming a setup token, one request for every account's last 30 days with holds, reading both protocol versions, mapping SimpleFIN accounts to ours (`feed_accounts`), and `run_sync`. All network code is one function in `sync/transport.py`.
- **17c, links and commands**: several named SimpleFIN links, one per person's subscription (migration `0005` adds `feed_accounts.link`; the same SimpleFIN id under two links becomes two mappings; existing signatures gain `link` as a keyword with a default, so 17b's tests keep passing); requests that refuse redirects, so the access credentials can only reach the access URL's host (a follow-up Grok raised in 17b); `fin sync link --link NAME` (asks for the setup token, stores the access URL in the macOS Keychain with `keyring`, one entry per link), `fin sync accounts`, `fin sync map`, `fin sync run`, `fin sync status`, `fin sync unlink`; a `launchd` example for a daily run. The upgraded and dropped counts of Phase 8 in `fin import statement` may move to a small follow-up if 17c is too large.
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
