# Audit (2026-10-25)

After Phase 37 (`boa_deposit` on `main`, 3998 tests). `src/finances` is 19,622 lines in 212 modules.

The structure is sound. Do not introduce parser inheritance or repository objects. The cheap, high-value work is the docs. One behaviour gap is real: after a rule or alias, the CLI pairs transfers and the web categorize path does not.

## What holds

- Domain imports nothing from the rest of the project. Views never open the database, the Keychain, or the network. CLI, web, and MCP do not import each other.
- Money is integer cents. Parsers work on text. A statement that does not reconcile is not imported. Privacy rules (stdio MCP, 127.0.0.1, no network outside `sync/`) match the code.
- Parsers share a `StatementParser` Protocol and a registry, not a base class. Frozen dataclasses are values. Earlier tidies already did the expensive splits: web routes (32), one clock (31), repositories (36a), views that only format (36b/c).
- `testing.md` and `scripts/critical_modules.txt` match (14 paths). Bank parsers are off that list on purpose: reconciliation is the safety net. `AGENTS.md` matches the code.

## Size

| Package | Files | Lines |
|---|---|---|
| db | 45 | 5081 |
| web | 25 | 3056 |
| cli | 24 | 2467 |
| domain | 26 | 2174 |
| views | 29 | 1616 |
| ingest | 14 | 1605 |
| analysis | 28 | 1488 |
| mcp_server | 4 | 952 |
| sync | 7 | 771 |

Largest modules: `db/orm.py` (727), `mcp_server/tools.py` (691), `domain/insights.py` (366), `web/routes/transactions.py` (366), `web/routes/categories.py` (345), `web/routes/sync.py` (338).

## Duplicate code

Most repetition is the three-front-end tax, which Phase 22 already paid once. What is left is either a one-liner copied six times, or a second implementation of a rule that already has a home.

| Kind | Where | What is copied | Fix |
|---|---|---|---|
| One-liner | All 6 parsers | `lines = [line.strip() for page in pages for line in page.splitlines()]` | `flatten(pages)` in `ingest/parsers/helpers.py` |
| Walk | `truist.py`, `boa_deposit.py` | squeeze heading opens a section; a line starting `Total` closes it; checks vs other rows | Extract only if a third deposit parser appears |
| Regex | All 6 parsers plus `helpers.py` | Same digit-group money pattern, wrapped with `$` / sign / named group per bank | Optional `AMOUNT` fragment in helpers. Bank wrappers stay local |
| Rule | `mcp_server/tools.py` `list_accounts` | Owner and joint rebuilt from `list_people` + `list_account_owners` | Call `analysis.listings.account_listing` |
| Glue | `cli/reports.py`, `web/routes/reports.py`, MCP `get_spending` | Month-or-from/to date range, and month-start parsing, copied three times | One parser in `domain/periods` or analysis |
| Behaviour | `cli/categories.py` vs `web/routes/categories.py` | CLI `categorize_all` always `pair_transfers`; web rule/alias/clear only `categorize` | One `categorize_then_pair` used by both |
| Test helper | 7 parser test files | `pages(name)` reads fixtures and splits on form feed | Leave it. Given tests pin the helper in each file |
| Exceptions | accounts, categories, people repos | `AccountExistsError`, `CategoryExistsError`, `PersonExistsError` | Optional: one name-taken error. Low value |

Name-length checks for accounts and categories live in the repositories and are repeated on create and rename. People already do this in domain (`validate_person_name`). Proposal reason validation (`1 to 200 characters`) is copied across `propose_*`.

Views re-apply `clean_merchant` on uncategorized rows (`views/categories.py`) while analysis already has `merchant_name`. Alias merging can disagree with reports.

`to_account` inlines UTC handling instead of calling `_as_utc` a few lines below it in `db/orm.py`.

### Not duplication

ORM `*Row`, domain dataclasses, and view `*Row` look like three copies of Account. They are the layering. Merging them would put SQLAlchemy into domain or display strings into the database.

Truist and `boa_deposit` also look similar in `_row` (fullmatch a date, `parse_amount`, skip 0.00, `collapse_ws`). The posted date, the sign, and the purchase-date rule are different. A shared `_row` that takes six callbacks is inheritance by another name.

Twenty `to_*` converters in `orm.py` are the intended seam. Keep them. Do not introduce a generic mapper.

## OOP-like structure (without classes)

The project already uses the useful parts: a small public surface per module, one place for a rule, values that do not mutate, and substitution through a Protocol. It avoids inheritance trees, repository objects with hidden session state, and parsers that inherit a walk they then override.

Already in place:

- `StatementParser` Protocol: `name`, `detect`, `parse`. Registry refuses two matches.
- Frozen dataclasses as values (`Account`, `StatementLine`, `SpendingLine`).
- Encapsulation: domain has zero imports from db, ingest, or web. Views have zero imports from db.
- One function for today, one for money, one for session scope, one `print_rows` for CLI tables.
- Sync `Transport` as a callable, not an aggregator class tree.

Where the analogy is thin:

- Parser classes hold only a `name` string. They are namespaces. That is fine.
- `web/helpers.py` and `web/access.py` still use leading underscores (`_day`, `_reading`) from when they lived inside `app.py`.
- Web `_reading` is a writable session. MCP correctly splits `reading()` (read-only engine) vs `writing()`.
- `tools.py` and `orm.py` are the remaining catalog modules. Split `tools.py` the next time a write tool is added, the same way Phase 32 split routes. Leave `orm.py` until a table split is forced, then split by area like the repositories, not with a base class.
- `domain/insights.py` owns nine finding types plus English `detail` strings. A tuple of finder functions would make "add a finding" one registration. Subclasses of `Finding` would scatter ordering.
- `domain/models.py` is inconsistent packaging: `Account` / `Transaction` / `Category` live there; `SplitPart`, `Proposal`, `MerchantAlias` live in sibling files.
- Views import service types (`ImportStatus`, `CategorizeResult`, `LinkRun`) from ingest, categorize, and sync. Analysis (or a tiny domain type) should own those so views never import those packages.
- `views/audit.py` `change_link` is web URLs. CLI `fin audit` never uses it.
- Uniqueness errors are typed (`*ExistsError`). Missing rows are `ValueError("… not found")` except `get_account`, which returns `None`. Sync uses `FeedError("account not found")` for the same situation.

Do not add a parser base class. Bank layouts disagree on dates (MM/DD vs MM/DD/YY vs Month D), on whether the amount is signed as printed or by section, and on whether a check is one or two per line. A base class becomes a hook farm. Keep helpers (`flatten`, `squeeze`, `parse_amount`, `infer_year`) and keep each bank's walk in its own module.

Do not add `AccountRepository` classes, `Finding` subclasses, ORM rows that subclass domain dataclasses, or a `SimpleFinClient(AggregatorClient)` tree. There is one aggregator. `Transport` as a callable is the extension point.

## BoA card vs deposit detection

Both look for `bankofamerica.com` on page 1. The card parser then requires `Account#` with no space; the deposit parser requires `Account number:` and `Beginning balance on`. That is a substring fence, not a shared discriminator.

Overlap fails closed: `detect_parser` raises `statement matches more than one parser`. Import is refused, not silently wrong.

Card tests (`tests/unit/test_boa_parser.py` `OTHER_BANKS`) never list `boa_deposit` fixtures. The other direction is covered. PDF layout that joins `Account` and `#` on a deposit first page would dual-match.

## Document drift

Code is ahead of the two documents people read first. Phase specs and `progress.md` are current. `architecture.md` and the roadmap status line are not.

| Severity | Document | Claim | Code today |
|---|---|---|---|
| High | `architecture.md` Non-goals | taxes, budgeting envelopes | Budgets shipped in 26a/26b. Tax flag and year report in 30a/30b. |
| High | `roadmap.md` status | Built through 20d (3952 tests); Phase 37 is specified | 37 is built and on `main`. 3998 tests. `boa_deposit` is registered. |
| High | `architecture.md` parsing | A statement that does not reconcile can be overridden and flagged | `ingest/service.py` always refuses. Roadmap Phase 3 already says there is no override. |
| Med | `architecture.md` package layout | parsers: Capital One, BoA, Citi, Truist, Marcus; `migrations/` at repo root | Sixth parser `boa_deposit`. Alembic lives in `src/finances/db/migrations/` (`0001`–`0021`). |
| Med | `architecture.md` Non-goals | The app holds only an aggregator access token in the Keychain | Also the web password hash, session key, and extra SimpleFIN access URLs. |
| Med | `roadmap.md` Phase 6 outcome | every kind of statement has a parser | True after 6 for the banks then in hand. False as current state until 37. |
| Med | `architecture.md` Open decisions | Heading still says Open; both bullets marked decided | SimpleFIN and Tailscale Serve are decided. Remaining work is operational (link the banks, check card sign). |
| Low | `statement-formats.md` | Section 8 is BoA deposit; 6 and 7 are CSV layouts | Numbering is leftover from removed CSV import. |
| Low | `architecture.md` Non-goals | CSV import. The aggregator feed replaces it. | Still true. CSV export exists (30c/30d) and is easy to mix up with this line. |
| Low | `docs/README.md` | `roadmap.md`: outlines for phases not yet specified | Every numbered phase has a spec. Only the Backlog is unspecified. |
| Low | `testing.md` | Unit tests must be fast (under 10 s total) | Written when the suite was small. |

`clock.py` and `export/` are already in the architecture package layout. The analysis one-liner is a role summary, not a file inventory.

## Front ends

Architecture wants CLI, web, and MCP to validate, call one function, and render. That is mostly true. The leaks:

- After a rule, alias, or bulk-clear, CLI `categorize_all` runs `categorize` then `pair_transfers`. Web rule add/edit/delete, alias add/delete, bulk-clear, and split-clear call only `categorize`. Import and sync-run on the web do pair. Same household action, different ledger until the next sync or `fin categorize`. Spending can double-count a transfer that was not paired.
- Date-range rules ("month or from/to, not both"; "both or neither") and month-start parsing are copied in CLI `_range` / `_first_day`, web `_spending_range` / `_month_start`, and MCP `get_spending` / `_month_start`. Export re-imports the web private helpers.
- `web/routes/sync.py` `_keychain_links` reads a test Keychain's private `passwords` dict. On a real Keychain it returns empty, so keychain-only links never show Unlink. That was a Phase 20d deviation.
- MCP `list_accounts` rebuilds owner/joint. MCP also renames spending fields (`purchases_cents` to `spent_cents`) and flips recurring signs in the tool. `list_transfers` sorts by id; CLI/web sort by date then pair id.
- PDF validation (empty file, 20 MB, `%PDF-` magic, filename) lives in the upload route. CLI import just reads bytes.
- Web password/lockout is a full state machine in `web/login.py`. Domain only hashes, verifies, and computes lock duration. Architecture documents this as web; it is still household-auth logic in a front-end package.
- CLI still builds some rows itself: `_TagRow` in `cli/tags.py`, folder import cells in `cli/importing.py`, year sections in `cli/reports.py`, hand-built Rich tables in `cli/sync.py` and `cli/main.py` `doctor`. Architecture says neither CLI nor web builds rows of its own.
- `tests/unit/test_views_take_data.py` still lists `STILL_LOADING = {"backups.py", "sync.py", "transfers.py"}`. Those files only format now.

Analysis does not format money. Finding and health English is pre-rendered in `domain/insights.py` and `domain/health.py` (`format_cents` in `detail` strings), then passed through unchanged. MCP returns that `detail` as-is. That is the "one implementation" goal, with the formatting sitting in domain rather than views.

### Coverage gaps (already partly in the backlog)

| Feature | CLI | Web | MCP |
|---|---|---|---|
| Transaction search (text, category, tag, kind) | list by account/dates/person only | full | full except no tag |
| Recurring income | `fin recurring --income` | insights is charges only | `get_recurring(income=True)` |
| Year report | yes | yes | no |
| CSV export | folder | download of current filters | no |
| Backup delete | no | confirm + password | no |
| Shared expenses | yes | yes | no |
| Tags / notes / splits write | yes | yes | no (proposals only, by spec) |
| `find_merchants` / `data_coverage` | no / overlap with health | no / dashboard problems | MCP only |
| Advice notes | review does not list them | shown on `/review` | `log_advice` / `list_advice` |
| Add-account currency | `--currency` | omitted; default USD | n/a |

CLI `fin transactions list` and web/MCP search are two different loaders (`list_transactions_with_people` vs `search_transactions`).

## What to improve

Ordered by value for a household app that is now in UAT, not by elegance. Nothing here should become a phase unless named.

1. **Docs now.** Refresh `architecture.md` (non-goals, parser list, `migrations/` path, Keychain, reconcile override, "Open decisions" heading) and the `roadmap.md` status line (built through 37, 3998 tests, only the Backlog left). Those two files are what the next agent reads first.
2. **Pairing now.** One `categorize_then_pair(session)` used by CLI and web after rules, aliases, and bulk clear. CLI pairs; web categorize after a rule does not. Import and sync on the web do.
3. **Cheap tidy.** `flatten(pages)` in parser helpers; MCP `list_accounts` through `account_listing`; `BoaCardParser` tests include `boa_deposit` fixtures; one date-range parser; empty `STILL_LOADING`; `to_account` calls `_as_utc`; pass `merchant` from analysis into uncategorized views; one `validate_name` in domain for accounts and categories.
4. **Next deposit parser.** Shared section walker only if a third checking/savings layout looks like Truist and BoA. Two copies is cheaper than a premature abstraction.
5. **Next MCP growth.** Split `tools.py` by area. A proposal-kind table of callables in `repositories/proposals.py` (not a handler class). Finding registry as a tuple of functions in `domain/insights.py`.
6. **UAT, not code.** Run the real-sample check on the two BoA checking PDFs. Confirm SimpleFIN signs for cards. Parser work does not close that.
7. **Backlog, already listed.** `fin transactions search`; `fin backup delete`; tags on MCP and `fin transactions list`; `fin networth`. Do not invent a tidy phase for CLI/web/MCP parity.

### Skip

Parser inheritance. Repository classes. Merging ORM, domain, and view rows. Putting `boa_deposit` on the critical-module list without a failing real statement. A tidy phase that only renames `_reading`. An error-type hierarchy; uniqueness is already a tuple that the web catches.

## Residual product risk

Reconciliation catches a wrong total. It does not catch a row in the wrong section, a purchase date that used the posted year, or a check number that dropped a star, if the cents still add up. That is why Phase 37's spot checks exist. The same gap applies to every parser. Keep adding a deciding fixture when a real statement surprises the layout, rather than promoting all parsers to critical modules.
