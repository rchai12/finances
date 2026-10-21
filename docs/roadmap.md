# Roadmap

Each phase is sized for one focused coding session: a few modules, their tests, and a CLI command to exercise them. Every phase ends in a working, tested state.

**Input decision:** a third-party **aggregator** is the daily feed. Its rows are provisional. Monthly **PDF statements** are the audit and the record (see `docs/statement-formats.md`): each is reconciled against its own opening and closing balances, then upgrades the matching provisional rows in place. Statements also supply what the feed lacks, such as the cardholder on shared cards.

Status (2026-10-16): built and verified, in the build order below, up to and including Phase 26b. Each phase's spec is in `docs/phases/`, its verification guide in `docs/verification/`, its review in `docs/reviews/`, and its result in `docs/progress.md`. Phases after 26b are outlines until specified.

**Build order:** 2 → 3 → 4 → 17a → 8 → 17b → 17c → 21 → 16a → 16b → 9 → 16c → 16d → 10 → 22 → 23 → 11 → 12 → 13 → 16e → 24 → 24b → 16f → 16j → 16g → 25 → 16h → 16i → 16k → 13d → 26a → 26b → 31 → 32 → 33 → 27 → 14 → 19 → 28 → 29 → 30 → 16 → 20. Phases 5 and 6 (more statement parsers) can be built any time after 4, when audit coverage for those banks is wanted.

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
| 9 | Test hardening | Property and fuzz tests over money, dates, parsers, SimpleFIN answers, web forms, and statements and feed pulls in any order; the bugs they found fixed (pairing that lost or doubled equal purchases near a period's edge, text longer than its column, any text as a currency, a SimpleFIN answer that crashed the reader); the migration chain and log hygiene tested | [phase-09](phases/phase-09-test-hardening.md) (re-issued for the current format) |
| 10 | Quality gates | One check command (`scripts/check.py`: lint, format, tests, full coverage of the critical modules, optional real samples) and a pre-commit hook for lint and format; mutation testing and CI left for later | [phase-10](phases/phase-10-quality-gates.md) (re-issued, slim) |
| 11 | Categorization and transfers | Merchant normalization, categories, rules, own-account transfer matching | [phase-11a](phases/phase-11a-categories-and-rules.md) (categories, merchants, rules; terminal), [phase-11b](phases/phase-11b-categories-on-the-web.md) (the same on the web), [phase-11c](phases/phase-11c-transfers.md) (transfers between own accounts; terminal), [phase-11d](phases/phase-11d-transfers-on-the-web.md) (the same on the web) |
| 12 | Core reports | Balances, net worth, spending by category/merchant/person, month-over-month | [phase-12a](phases/phase-12a-spending.md) (spending; terminal), [phase-12b](phases/phase-12b-balances-and-months.md) (balances, net worth, month over month; terminal), [phase-12c](phases/phase-12c-reports-on-the-web.md) (a Reports page on the web) |
| 13 | Insights engine | Recurring charges, spikes, frequent small purchases, findings list | [phase-13a](phases/phase-13a-recurring-charges.md) (recurring charges; terminal), [phase-13b](phases/phase-13b-findings-and-merchant-stats.md) (findings and merchant stats; terminal), [phase-13c](phases/phase-13c-insights-on-the-web.md) (an Insights page on the web) |
| 14 | Agent interface (MCP server) | Read-only MCP tools over stdio for the finance subagent: accounts, balances, transactions, reports, findings, data coverage | outline below |
| 15 | *Removed* | Was "LLM advice". Advice now comes from the external agent | |
| 16 | Local web UI | FastAPI dashboard on 127.0.0.1, statement upload, review of agent writes | outline below |
| 17 | Aggregator sync | Daily pull of transactions and balances into provisional rows; the only network code | [phase-17a](phases/phase-17a-feed-core.md) (feed core), [phase-17b](phases/phase-17b-simplefin-sync.md) (SimpleFIN client and sync), [phase-17c](phases/phase-17c-sync-commands.md) (links, commands, Keychain), [phase-17d](phases/phase-17d-user-agent.md) (a user agent Cloudflare accepts) |
| 18 | *Removed* | Was "Azure deployment". The app stays on the household's machine | |
| 19 | Agent write tools | MCP tools that write the interpretation layer only, tagged, reversible, with `fin review` | outline below |
| 20 | Remote access | Web UI login and hardening so the app can sit behind a private VPN | outline below |
| 21 | People and ownership | The household's people; each account owned by one person or joint; statement cardholder names mapped to people; every view filterable by person, bank, and card | [phase-21](phases/phase-21-people-and-ownership.md) |
| 22 | Shared view rows | A clean-up with no behaviour change: `finances.views` builds each view's rows once for the command line and the web; `fin sync run` uses `run_links`; setup offers move out of the web page | [phase-22](phases/phase-22-shared-view-rows.md) |
| 23 | Shared rules | A clean-up with no behaviour change: one home for text cutting and column limits (`domain/text.py`, used by the ORM), typed-input checks moved into the repositories, small shared helpers | [phase-23](phases/phase-23-shared-rules.md) |
| 24 | Backups | `fin backup`: a consistent copy of the database, the last N kept, each one checked; restore; a scheduled run | [phase-24](phases/phase-24-backups.md) |
| 24b | Backups on the web | A Backups page: back up now, the list, delete, and restore, with confirmation and the current database always set aside | [phase-24b](phases/phase-24b-backups-on-the-web.md) |
| 25 | Data health | Warnings for stale accounts, SimpleFIN links that need relinking, months without a statement, balance drift, and an old or missing backup; shown on the dashboard | [phase-25](phases/phase-25-data-health.md) (terminal; shown on the 16h dashboard) |
| 26 | Budgets | A monthly target per category or group, progress, and an over-budget finding | [phase-26a](phases/phase-26a-budgets.md) (storage, rules, `fin budgets`, the finding), [phase-26b](phases/phase-26b-budgets-on-the-web.md) (the Budgets page and the dashboard block) |
| 27 | Looking ahead | Upcoming bills from recurring charges, recurring income, a 30-day cash-flow forecast per account, and net worth over time | outline below |
| 28 | Categorizing extras | Split transactions, tags and notes, merging merchants, and a preview before saving a rule | outline below |
| 29 | Shared expenses | Mark a joint expense paid by one person as shared, and keep a running balance of who owes whom | outline below |
| 30 | Year-end and export | Yearly totals by category with tax-relevant groups pulled out, and CSV export | outline below |
| 31 | Tidy | No behaviour change except the date: one local `today()` for every page and command; the remaining duplication (`fin statements list` cells, `_print_rows`, the budget amount message, the backup list) shared | [phase-31](phases/phase-31-tidy.md) |
| 32 | Split the web app | No behaviour change: `web/app.py` split into one router module per area, with the shared checks and rendering in one place | [phase-32](phases/phase-32-split-the-web-app.md) |
| 33 | Sync resilience | The daily sync retries when SimpleFIN cannot be reached, scheduled runs leave timestamped log lines, and the last failed sync is stored so `fin health` and the dashboard can say why | outline below |

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
- **Split and decided (2026-10-14).** 11a: a two-level category tree seeded by migration, merchant cleaning, rules (highest priority wins; manual choices never overwritten; adding or deleting a rule re-runs the rules over past transactions), and the terminal commands. 11b: the same on the web. 11c: transfers, paired automatically when one match is clear and offered for confirmation when not, plus keyword rules for transfers to untracked accounts. Specified (2026-10-14): 11c pairs an outflow with the same amount in another account at most 5 days away, automatically when neither side has another candidate; the rest wait for `fin transfers review`; unpairing or rejecting is remembered. Transfers to untracked accounts need nothing new: an 11a rule gives them a category in the Transfers group, which Phase 12 treats as a transfer. 11d puts transfers on the web. Refunds netting moves to Phase 12, where spending is added up. SimpleFIN supplies no categories, so there is no aggregator hint.
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
- **Split and decided (2026-10-14).** 12a: spending for a month or range, grouped by category, group, merchant, person, account, bank, or card. Transfers (paired, or in a transfer category) are left out; income (an income category) is totalled apart; refunds net against their line; money in without a category is totalled on its own line until categorized; pending is left out; the day bought decides the month. 12b: balances from the newest snapshot, net worth, month over month with partly covered months marked. 12c: the web pages.

### Phase 13: Insights engine
- Per-merchant stats: visits per month, average ticket, trend vs 3-month baseline, time-of-week pattern.
- Recurring charge detection (similar amount, regular interval), including many charges to the same digital merchant (e.g. app store billing) grouped together.
- Findings with type, severity, estimated monthly savings: spike, frequent small purchases, subscription overlap, price increase, interest charged, fees charged.
- All local and rule-based. `fin insights`.
- **Split (2026-10-15).** 13a: recurring charges. A merchant's spending charges form a series when every gap falls in one band (week 6 to 8 days, month 27 to 33, quarter 85 to 97, year 350 to 380), with at least 3 charges (2 for a year); when a merchant's charges together are not a series, each amount is tried alone, which finds several subscriptions billed by one app store. Active until the last charge plus the band's top. 13b: merchant stats and findings, which build on 13a (subscription overlap, price increase). 13c: the web.

### Phase 14: Agent interface (MCP server)
- New package `src/finances/mcp_server/`; new dependency: the official `mcp` Python SDK. `fin mcp serve` runs the server on **stdio only** (no HTTP transport, no port).
- Read-only tools, each a thin wrapper over one existing function in `analysis` or `db`:
  - `list_accounts`, `get_balances`, `get_net_worth`
  - `list_transactions` (filters: account, bank, card, person, date range, category, merchant, text; hard row cap with paging)
  - `spending_by_category`, `spending_by_merchant`, `spending_by_person`, `month_over_month`
  - `list_findings` (the Phase 13 insights), `merchant_stats`
  - `list_uncategorized`, `list_categories`, `list_rules`, `list_transfers`, `transfer_suggestions` (the transfers waiting for review): the work queues, so the agent knows what to recommend on. Each wraps a function Phases 11a and 11c already built.
  - `data_coverage`: per account, the periods covered, the date of the newest data, which periods are statement-audited, and any sync drift, so the agent can say when its answer rests on stale or partial months
- Results: integer cents, ISO dates, holder-perspective signs, raw merchant and cardholder names. Tool descriptions state the sign convention and units, since the agent reads them.
- The server opens the database read-only where the dialect allows it, and no tool calls a write repository function.
- Tool arguments and results are never logged at INFO or above.
- Tests drive the server through the SDK's in-memory client against a migrated temp database. No subprocess, no socket.
- Depends on Phases 12 and 13. Will be specified as several sub-phases (server skeleton plus one tool, then tool groups).

### Phase 15: removed
The app no longer calls an LLM. The finance subagent of the overarching agent produces advice from the Phase 14 tools.

### Phase 16: Local web UI
- Moved forward at the owner's request (2026-10-14): setup must be possible from a web page, not only the terminal. Split into sub-phases.
- **16a, the foundation, is specified** ([phase-16a](phases/phase-16a-web-foundation.md)): `fin web serve` on 127.0.0.1 only, a host check against DNS rebinding, strict security headers, no JavaScript, and read-only pages for accounts, people, transactions, and SimpleFIN status.
- **16b, the setup workflows, is specified** ([phase-16b](phases/phase-16b-web-setup.md)): a form token on every form; add an account, a person, an owner, a cardholder name; link SimpleFIN by pasting the setup token into a password field; list SimpleFIN's accounts with a dropdown to map each one, or to create the matching account and map it in one step; a "Sync now" button; unlink.
- **16c, forms that work in a real browser, is specified** ([phase-16c](phases/phase-16c-browser-origin.md)): the `no-referrer` policy of 16a made browsers send `Origin: null`, which the origin check of 16b refuses; the policy becomes `same-origin`.
- **16d, new SimpleFIN accounts, is specified** ([phase-16d](phases/phase-16d-new-simplefin-accounts.md)): each sync remembers the SimpleFIN accounts it receives; `fin sync run` and Sync now say how many are new; the SimpleFIN page offers each one pre-filled (type, last four digits, owner, and an existing account it looks like) to create and map, map, or not track, in one click.
- **Decided (2026-10-15): four web sub-phases before Phase 14**, in this order, so each builds on the last and the agent's tools can reuse their filters:
  - **16e, find and drill down** ([phase-16e](phases/phase-16e-find-and-drill-down.md)): search transactions by text; filter by category and merchant; a category column; each spending line, merchant, and finding links to its transactions.
  - **16f, editing categories and rules** ([phase-16f](phases/phase-16f-editing-categories-and-rules.md); decided 2026-10-15: a category in use moves its transactions and rules to a chosen category before it is deleted; web and terminal both): rename categories and groups, delete them, edit rules.
  - **16j, accounts and bulk categorizing** ([phase-16j](phases/phase-16j-accounts-and-bulk.md); split from 16f to keep each spec small): rename, close, and reopen accounts; categorize several transactions at once with checkboxes on the Transactions page, or several `--id` in the terminal.
  - **Bulk-form fix (found in 16j's review):** carried by 16g, R1.
  - **16g, statement upload** ([phase-16g](phases/phase-16g-statement-upload.md)): upload a PDF statement through the same import as `fin import statement`, and a page of the statements held and the gaps between them.
  - **16h, dashboard** ([phase-16h](phases/phase-16h-dashboard.md)): the home page: net worth, this month against last, top findings, and what needs attention (uncategorized, transfers to review, accounts without recent data), each linking to its page.
  - **16i, account pages** ([phase-16i](phases/phase-16i-account-pages.md); split 2026-10-16: 16i is the page and the links, with tables; **16k** adds the charts beside them) (asked for 2026-10-15): clicking an account name (Accounts, the balances on Reports, the Account column of Transactions, From and To on Transfers) opens that account's page; clicking card digits opens it filtered to that card. The page has the account's transactions with 16e's search and filters, and three charts: this month's (or a chosen month's) spending by category group as a pie with a legend whose rows link to the transactions, spent and income per month as bars, and the balance over time as a line.
  - **16k, charts** ([phase-16k](phases/phase-16k-charts.md)): the account page's pie, bars, and line, beside its tables.
  - **Charts use a JavaScript chart library** (the owner's choice, 2026-10-15). To keep the no-network and strict-policy rules: the library is a pinned version served from the app's own static folder (no CDN), its file hash is checked by a test, the policy becomes `script-src 'self'` (no inline scripts, no `eval`), and chart data reaches the page as JSON in a data attribute or a same-origin JSON route. Every chart keeps a table of its numbers beside it, so the page still reads without scripts. The 16i spec names the library and how the file is added; `docs/architecture.md` changes with it.
- Later sub-phases: the review queue of agent suggestions (with Phase 19). When the system moves to the Mac Studio, the site sits behind the private VPN with a login (Phase 20).
- FastAPI + Jinja2, bound to 127.0.0.1. From 16k the site runs its own scripts only (Chart.js 4.4.6, vendored and hash-checked, and `static/charts.js`); HTMX only if a later page needs it, served from the app itself.
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
- **The agent recommends; it does not act** (the owner's decision, 2026-10-14). Every write tool except the advice log stores a **proposal** that changes nothing until a person accepts it. Accepting a proposal calls the same function the terminal and web use, so the result is recorded as the person's choice.
- Schema: a `proposals` table (kind, the target, the proposed value, the agent's one-line reason, status `open` / `accepted` / `declined`, timestamps); a `finding_status` table; an `advice_log` table.
- Tools, in the order they are built: `log_advice` / `list_advice` (the agent's own notes, the only direct write), `propose_category` (for an uncategorized transaction), `propose_transfer` and `propose_not_transfer` (for a candidate waiting for review), `propose_rule`, `propose_merchant_alias`, `propose_finding_status`, `list_proposals`.
- A proposal on something a person has since decided (a category set, a pair confirmed or rejected) is shown as out of date and cannot be accepted. The agent cannot accept or decline a proposal, and cannot propose again what a person declined.
- `fin review` lists open proposals with the agent's reason; accept or decline each, or several at once. The web UI gets the same queue, and the Categories and Transfers pages show the agent's suggestion beside each item.
- No tool for amounts, dates, balances, accounts, imports, deletions, sync, or reconciliation overrides.

### Phase 20: Remote access
- The app still binds to 127.0.0.1 only. The VPN that forwards to it is configured outside the repository; this phase ships the runbook, not the VPN.
- Web UI login for a single household: password hash from configuration, signed session cookie with `Secure`, `HttpOnly`, `SameSite=Strict`, idle timeout, lockout after repeated failures.
- CSRF tokens on every state-changing request; allowed-host check so only the configured VPN hostname and localhost are served.
- `fin doctor` fails if the web UI is configured to bind to anything other than loopback.

### Proposed 2026-10-15 (accepted by the owner)

The order in the build line above is the architect's recommendation: protect the data first, show its health on the dashboard, then plan ahead, then the agent, then the extras.

- **13d, unusual charges** ([phase-13d](phases/phase-13d-unusual-charges.md); specified 2026-10-16 with a $250 floor for a first charge, so earlier tests' data does not trigger it): two more findings in the Phase 13b engine: a duplicate (the same merchant and amount twice on one day) and a first charge from a merchant that is large for its category.

### Phase 24: Backups
- `fin backup` writes a consistent copy of the SQLite database (SQLite's online backup, not a file copy while it is open) into a folder from configuration, outside `data/`'s working files; keeps the newest N; opens each new copy and checks its schema revision and row counts before reporting success.
- `fin backup --restore FILE` asks for confirmation, checks the copy first, and keeps the replaced database aside.
- A `launchd` example for a daily run, like the sync one. No network: copying off the machine is left to the owner's own tools.

### Phase 24b: Backups on the web (decided 2026-10-15)
- A **Backups** page: the backups and the set-aside copies, newest first, with when each was taken and its size; a **Back up now** button (Phase 24's `make_backup`).
- **Delete**: chosen from the list by name only (never a path); a confirmation page names the file. Only backup and set-aside names can be deleted.
- **Restore**: chosen from the list only (no upload, no typed path); a confirmation page where the owner types the backup's name; the current database is always set aside first, and that copy appears in the list, so a restore can be undone by restoring it. The server pauses for it: it holds other requests, closes its database connections, copies the backup in, checks it, and carries on. A backup from an older version says to run `fin db upgrade` in the terminal.
- **No download**: a full copy would land in the browser's downloads folder, often synced to the cloud.
- From Phase 20 (remote access), delete and restore are allowed only from the Mac itself or after the password is entered again.

### Phase 25: Data health
- One list of problems, each with a kind, the account, and what to do: no new data for N days; a SimpleFIN link that needs relinking; a calendar month with no statement for a statement-only account (from statement periods); balance drift from the latest pull.
- `fin health`, and a block on the 16h dashboard. Phase 14's `data_coverage` reuses it.
- A warning when the newest backup (Phase 24) is older than a set number of days (default 2) or there is none; it also shows on the dashboard. Managing backups on the web is Phase 24b.

### Phase 26: Budgets
- **Split (2026-10-16):** 26a is storage, the rules, `fin budgets`, and the `over_budget` finding; 26b is the Budgets web page (set and remove targets, progress) and a budget block on the dashboard.
- A target per category or group per month (one amount repeated monthly; no rollover at first), stored with a migration.
- Progress for the month: spent (Phase 12a's rules), target, left, and the share of the month gone; on the dashboard and `fin budget`.
- A finding `over_budget` in the Phase 13b engine; a web page to set targets.

### Phase 27: Looking ahead
- Upcoming bills: the next charge of every active recurring charge (Phase 13a) in the next 30 days.
- Recurring income found the same way as charges (paychecks every week, two weeks, or half-month), which needs a two-week band.
- A 30-day forecast per account: the newest balance plus expected income minus expected bills, with the lowest point and its day.
- Net worth over time from balance snapshots, as a line (16i's chart library).

### Phase 28: Categorizing extras
- Split a transaction into parts with their own categories and amounts that add up to it exactly; reports count the parts.
- Tags (many per transaction) and a note; filter by tag on the Transactions page.
- Merge merchants: a stored alias from one cleaned name to another, used by stats, recurring charges, and rules.
- A rule preview: before saving, how many transactions it would change, with examples.

### Phase 29: Shared expenses
- Mark a transaction as shared between people (half each by default), and see who owes whom, with a way to record a settlement.

### Phase 30: Year-end and export
- A year's totals by category and group, with tax-relevant groups (medical, gifts and donations, taxes) pulled out.
- CSV export of transactions and of any report, written to a chosen folder; no network.

### Phase 31: Tidy (planned 2026-10-16, after an audit at 2887 tests)
- One `today()` (local date of the machine) used by every command and page; the web's `_today` calls it, so tests that replace `_today` keep working. Stored timestamps stay UTC. Near a month's end in the evening, the web and the terminal then agree on the month.
- `fin statements list` uses `views.statement_rows`; one `print_rows` helper in `cli/common.py` replaces the three copies; the budget amount message is one constant; `fin backup list` uses the web's backup rows (gaining the size column).
- Docs were brought up to date by the architect with the plan (architecture: package roles, the pure `domain` rules, `views` not used by MCP, the full data model, the date rule).

### Phase 32: Split the web app
- `web/app.py` (about 1700 lines, 50 routes) becomes a package of routers, one per area (accounts, people, transactions, categories and rules, transfers, reports and insights, budgets, statements, backups, sync, home), with the security middleware, the form checks, rendering, and notices in shared modules.
- No route, template, message, or status changes; every earlier web test passes unchanged. It comes before Phase 20 (login touches every route) and before Phase 27 and 19 add pages.

### Phase 33: Sync resilience (planned 2026-10-17)
- **Why:** the daily `launchd` sync ran at 07:00 and failed four days running after the last good pull (14 October): once "aggregator answered with an error", three times "could not reach the aggregator", most likely the Mac waking before its network was back. One attempt per day means one network blip loses the day, and the log does not say when each run happened.
- **Retry:** when SimpleFIN cannot be reached (no answer at all), `fin sync run` tries again a few times with a growing wait, over a few minutes, before giving up; an answer with an error status is not retried (it would not change within minutes), and "access revoked" never is. The waits are constants, and tests replace the sleep so they never wait.
- **Timestamped logs:** each scheduled run of `fin sync run` and `fin backup run` writes a start line with the local date and time to its log, so failures can be placed in time. The schedule scripts stay as they are unless the spec finds that the simplest place for the line.
- **The last failure, stored:** a migration adds a small record per SimpleFIN link of the last failed sync (when, and the kind: unreachable, error answer, access revoked), cleared by the next good sync. `fin sync status`, `fin health` (a `sync` problem that names the reason), and the dashboard show it. Phase 25's "no pull for N days" stays.
- Out of scope: syncing more than once a day, notifications, and changing what a successful sync does.
