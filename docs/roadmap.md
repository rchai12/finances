# Roadmap

Each phase is sized for one focused coding session: a few modules, their tests, and a CLI command to exercise them. Every phase ends in a working, tested state.

**Input decision:** monthly **PDF statements** are the record (see `docs/statement-formats.md`); each is reconciled against its own opening and closing balances before import. **CSV exports** (where offered; Marcus has none) are imported as provisional rows to cover the time since the latest statement, and are superseded in place when the statement arrives.

Status: **Phases 1 to 8 are fully specified.** Later phases are outlines and will be specified after earlier ones are built and reviewed.

| # | Phase | Outcome | Spec |
|---|---|---|---|
| 1 | Project skeleton | Installable package, config, logging, `fin doctor`, tests run | [phase-01](phases/phase-01-skeleton.md) |
| 2 | Database and accounts | Schema + migrations, repositories, `fin accounts add/list` | [phase-02](phases/phase-02-database-accounts.md) |
| 3 | Statement import core | PDF text, parser registry, reconciliation, dedup, `fin import statement/folder` | [phase-03](phases/phase-03-statement-import-core.md) |
| 4 | Capital One parser | Multi-cardholder card statements, year wrap | [phase-04](phases/phase-04-capital-one-parser.md) |
| 5 | BoA + Citi parsers | Two more card formats | [phase-05](phases/phase-05-boa-citi-parsers.md) |
| 6 | Truist + Marcus parsers | Checking/savings; all PDF samples import | [phase-06](phases/phase-06-deposit-parsers.md) |
| 7 | CSV import | Truist + Citi CSV profiles, daily balance check, provisional rows | [phase-07](phases/phase-07-csv-import.md) |
| 8 | Statements supersede CSV | In-place upgrade of provisional rows; import order does not matter | [phase-08](phases/phase-08-statement-supersedes-csv.md) |
| 9 | Categorization and transfers | Merchant normalization, categories, rules, own-account transfer matching | outline below |
| 10 | Core reports | Balances, net worth, spending by category/merchant/person, month-over-month | outline below |
| 11 | Insights engine | Recurring charges, spikes, frequent small purchases, findings list | outline below |
| 12 | Privacy payload | Pseudonymization, coarsening, PII check, preview file. No network | outline below |
| 13 | LLM advice | Provider interface, Anthropic implementation, confirm-and-send, re-hydration | outline below |
| 14 | Local web UI | FastAPI dashboard on 127.0.0.1, statement/CSV upload | outline below |
| 15 | Cloud readiness | Dockerfile, PostgreSQL verified, auth hook, health endpoint | outline below |
| 16 | Azure deployment | Bicep: Container Apps, DB, Key Vault, Entra auth, budget alert | outline below |

## Outlines

### Phase 9: Categorization and transfers
- Tables: `categories` (with `is_sensitive`, `is_transfer`, `is_income` flags), `category_rules` (pattern, match type, priority), `merchants` (display name, kind: national_chain / local / p2p / unknown).
- Seed a default category tree (Groceries, Dining, Coffee & Dessert, Subscriptions & Digital, Shopping, Travel, Gas, Parking, Utilities & Internet, Health*, Insurance, Entertainment, Gaming, Fees & Interest, Transfers, Income...). *sensitive.
- Merchant normalization tuned to the formats seen: strip processor prefixes (`SQ *`, `TST*`, `PP*`, `PAYPAL *`, `SP `, `GOOGLE *`, `AMAZON MKTPL*<id>`), store numbers (`#1234`), phone numbers, run-together city+state suffixes, debit-card prefixes (`DEBIT CARD PURCHASE`, `DEBIT CARD RECURRING PYMT`), and embedded `MM-DD` dates.
- **Transfer matching** (important: the samples are full of them): card payments (`CAPITAL ONE MOBILE PYMT`, `PAYMENT FROM CHK`, autopay) and bank-to-bank transfers. Pair an outflow in one account with an inflow of the same amount in another account within N days; also keyword rules for transfers to untracked accounts (e.g. a CD). Paired and keyword transfers are excluded from spending.
- Refunds and reversals (credits from a merchant) net against that merchant's spending.
- Use `bank_merchant` / `bank_category` from CSV imports as low-priority hints (useful, but e.g. own-account savings transfers are labeled "Investments").
- Transfer matching must use amount and date, not card numbers in descriptions (they do not match; see formats doc).
- Rule engine: highest priority wins; manual overrides are never overwritten.
- CLI: `fin categorize`, `fin rules add/list`, `fin uncategorized`, `fin tx set-category`, `fin transfers review`.

### Phase 10: Core reports
- Pure functions in `analysis/` returning dataclasses (reused by the web UI).
- Balances per account from latest statement snapshot; net worth (cash minus card debt).
- Spending by category and by merchant for a month or range, using `transaction_date` when present; spending by cardholder (household of two).
- Month-over-month change. Statement periods do not align with calendar months; reports use calendar months and say when a month is only partly covered.

### Phase 11: Insights engine
- Per-merchant stats: visits per month, average ticket, trend vs 3-month baseline, time-of-week pattern.
- Recurring charge detection (similar amount, regular interval), including many charges to the same digital merchant (e.g. app store billing) grouped together.
- Findings with type, severity, estimated monthly savings: spike, frequent small purchases, subscription overlap, price increase, interest charged, fees charged.
- All local and rule-based. `fin insights`.

### Phase 12: Privacy payload
- National-brand allowlist (shipped file + user additions).
- Pseudonymize non-allowlisted merchants with per-run random tokens and generic type labels.
- Drop cardholder names (use "Person A/B"), card numbers, references, locations. Coarsen dates; round amounts; drop sensitive categories.
- PII checker that blocks the payload (digit runs, emails, phones, user blocklist including household names).
- `fin advice preview` writes `data/payloads/<timestamp>.json` plus the local-only token map.

### Phase 13: LLM advice
- `AdviceProvider` interface; Anthropic implementation using the official SDK; model id configurable.
- Sends only a payload that passed the PII check, after confirmation showing its hash.
- Structured response referencing tokens; re-hydrated locally; stored in `advice_runs`.
- API key from `FIN_ANTHROPIC_API_KEY`. `fin advice run`.

### Phase 14: Local web UI
- FastAPI + Jinja2 + HTMX, bound to 127.0.0.1.
- Dashboard, transactions with category editing, insights, advice; statement upload page that calls the same import service.

### Phase 15: Cloud readiness
- Dockerfile; docker compose with PostgreSQL; full test suite against PostgreSQL.
- Auth middleware required when `FIN_ENVIRONMENT=cloud`; `/healthz`; structured logs.
- Decide cloud DB and raw-vs-summary storage.

### Phase 16: Azure deployment
- Bicep: Container App, database, Key Vault, managed identity, Entra ID auth limited to the household, budget alert.
- Deployment runbook.
