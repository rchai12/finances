# Codebase audit (2026-11-15)

Static read of `src/finances` and `tests` after Phase 46. The earlier snapshot is [audit.md](audit.md) (2026-10-25, after Phase 37). This pass did not re-run `scripts/check.py`.

The design still holds: domain stays pure, money is integer cents, statements that do not reconcile are refused, and the only outbound HTTP call is the SimpleFIN transport. The cost of the later phases is concentrated in a few dispatch functions, two modules that sit outside the 400-line gates, and one behavior split between the CLI and the web.

## Size

`src/finances` is 21,644 lines in 226 modules (19,622 lines and 212 modules at the October audit). Tests are 51,520 lines in 328 modules: 324 of those define tests (2,573 functions named `test_*`). [roadmap.md](roadmap.md) reports 4,310 collected tests as of 2026-11-08; collection counts parametrized cases as well as functions.

| Package | Files | Lines | Share of source |
|---|---:|---:|---:|
| db | 57 | 6,245 | 29% |
| web | 25 | 3,207 | 15% |
| cli | 25 | 2,593 | 12% |
| domain | 27 | 2,331 | 11% |
| views | 29 | 1,742 | 8% |
| ingest | 14 | 1,606 | 7% |
| analysis | 28 | 1,551 | 7% |
| mcp_server | 4 | 1,182 | 5% |
| sync | 7 | 771 | 4% |
| root (`config`, `log`, `diagnostics`, `clock`) | 4 | 205 | 1% |
| categorize, export | 5 | 205 | 1% |

Most modules are small. Of 1,014 functions, 46 are 40 lines or longer and 6 are 80 lines or longer. The suite has no classes over 80 lines. The pressure is a handful of files and a handful of functions, plus a test tree two and a half times the size of the source.

### Largest modules

Two size gates already exist. `tests/unit/test_repositories_split.py` refuses any file under `db/repositories/` over 400 lines. `tests/unit/test_web_split.py` does the same for `web/`. Nothing caps `db/orm.py`, `mcp_server/tools.py`, `domain/`, `cli/`, `analysis/`, or `ingest/`. Those uncapped files are where growth went.

| Lines | Module | Gate |
|---:|---|---|
| 866 | `mcp_server/tools.py` | none |
| 775 | `db/orm.py` | none |
| 398 | `db/repositories/categories.py` | 400 |
| 381 | `web/routes/categories.py` | 400 |
| 368 | `web/routes/transactions.py` | 400 |
| 366 | `domain/insights.py` | none |
| 363 | `db/repositories/proposals.py` | 400 |
| 348 | `cli/categories.py` | none |
| 336 | `web/routes/sync.py` | 400 |
| 329 | `db/repositories/__init__.py` | 400; re-exports only |
| 323 | `cli/reports.py` | none |
| 303 | `ingest/service.py` | none |

`tools.py` grew from 691 lines to 866. `orm.py` grew from 727 to 775. The module docstring on `tools.py` still says the tools are read-only. The second half of the file is every proposal tool.

`categories.py` in the repositories is two lines under the cap (`delete_category` alone is 93 lines). The next proposal kind cannot land in `proposals.py` either: progress entries for Phases 44 and 45 already record helpers moved out so the file would stay under 400. That cap is now choosing the package shape.

### Long functions

| Lines | Function | Why it is hard to change |
|---:|---|---|
| 105 | `domain/health.py` `health_problems` | One function appends every health kind. A new kind is another branch in the middle. |
| 101 | `sync/service.py` `apply_feed` | Match, insert, update, drop, and drift in one function. It is on the critical-module list, so the size is paid for with branch coverage. |
| 93 | `db/repositories/categories.py` `delete_category` | Group delete, category delete, move-to, splits, rules, budgets, and the audit row. |
| 92 | `ingest/service.py` `import_statement` | The import transaction: parse, reconcile, dedup, supersede, store. |
| 85 | `db/repositories/rule_changes.py` `propose_rule_change` | Validation, the stored "before", and the open-proposal checks. |
| 83 | `mcp_server/tools.py` `_proposal_item` | One dict literal with a condition per proposal kind. |

`accept_proposal` (62 lines) and `proposal_out_of_date` are the same shape: a chain of `if kind == ...` with a fallback.

## Behavior: the web leaves transfers unpaired

`cli/categories.py` `categorize_all` runs `categorize` and then `pair_transfers`. Rules, aliases, imports, and sync on the CLI go through it.

These web writes call `categorize` and return:

- `web/routes/categories.py`: add a rule, add an alias, delete an alias, delete a rule, edit a rule
- `web/routes/transactions.py`: bulk "Leave to the rules", and clearing one transaction's category

Import, sync, clearing a split, and removing a share on the web do call `pair_transfers`. After a rule or a clear on the site, a transfer that the rules just freed stays unpaired until the next sync or `fin categorize`. Reports that drop paired transfers will count that money as spending until then.

Phase 38 closed the split and share cases. The rule and clear cases from the October audit are still open.

## Duplicate code

### The same check, eight times

This block is copied in `proposals.py` (three times), `transfers.py`, `new_categories.py` (twice), `rule_changes.py`, `category_changes.py`, and `finding_proposals.py`:

```python
clean = collapse_ws(reason)
if not 1 <= len(clean) <= PROPOSAL_TEXT_LIMIT:
    raise ValueError("a reason must be 1 to 200 characters")
```

`datetime.now(UTC)` wrapped as `_now` is copied in eight repository modules (`proposals`, `finding_proposals`, `findings`, `category_changes`, `rule_changes`, `advice`, `new_categories`, `audit`). A later phase that must record "who decided" or use the test clock will have to find every copy.

### Front-end copies of one rule

Month-or-range parsing is implemented three times:

- `cli/reports.py` `_range` and `_first_day`
- `web/routes/reports.py` `_spending_range` and `_month_start`
- `mcp_server/tools.py` `_month_start`, plus the start/end check inside `get_spending`

`cli/export.py` imports the CLI helper. `web/routes/export.py` imports the web helper. The three agree today. The next change to "what is a valid month" has to be made in all three, and the export routes will follow whichever private helper they import.

`mcp_server/tools.py` `list_accounts` rebuilds owner and joint from `list_people` and `list_account_owners`. `analysis/listings.py` `account_listing` already does that for the CLI and the web.

`get_spending` renames `purchases_cents` to `spent_cents` and rebuilds the summary in the tool. `list_transfers` sorts by pair id. The CLI and the web sort transfer rows by date, then pair id.

### Parsers

All six parsers still start with:

```python
lines = [line.strip() for page in pages for line in page.splitlines()]
```

`ingest/parsers/helpers.py` is the place a `flatten(pages)` belongs. The October audit already named it. It was not done, and Phase 46's Marcus CD path added another copy in the same file.

Truist and BoA deposit still walk sections the same way (a squeezed heading opens a section, a `Total` line closes it). Their posted-date, sign, and purchase-date rules differ. Two copies are still cheaper than a shared walker with a pile of callbacks. A third deposit parser would be the time to extract it.

BoA card and BoA deposit both look for `bankofamerica.com` on page 1, then fence on `Account#` versus `Account number:` plus `Beginning balance on`. `detect_parser` refuses a first page that matches both. That failure mode is safe. It is still a substring fence: a layout that joins `Account` and `#` on a deposit first page is refused as ambiguous.

### What looks like duplication and is the layering

`AccountRow`, `Account`, and the view row are three types on purpose. `orm.py` has 26 tables and a `to_*` function for each. That seam is the right one. A generic mapper would hide the conversions that have real rules (signs, enums, null text).

`to_account` still inlines the naive-datetime-to-UTC step. `_as_utc` is defined a few lines later and is what the other converters use. `to_account` was written before the helper and was never switched over.

## Where the 400-line cap is distorting the code

The repository split (Phase 36a) and the web split (Phase 32) were the right cuts. The cap is now forcing the next cuts into the wrong shape.

`accept_proposal` dispatches on kind. Kinds added after the file filled up (`GROUP`, `NEW_CATEGORY`, `CATEGORY_RENAME`, `CATEGORY_DELETE`, `FINDING_STATUS`, rule edits) live in other modules and are imported inside the function, so the import cycle stays broken. The `else` branch calls `set_category_by_hand`. That branch is the category proposal. A new kind that is stored and accepted without a new `elif` is written onto a transaction as a category.

`proposal_out_of_date` has the same fallback: any kind that is not listed is treated as a transfer pair (`pair_is_out_of_date`).

`_proposal_item` repeats the kind list as a JSON shape. Adding a kind means touching the repository, the accept chain, the out-of-date chain, the tool serializer, the review view, and the facade's `__all__` (139 names, asserted in order by `test_the_facade_offers_every_name_and_only_those`).

`db/repositories/__init__.py` is 329 lines that only import and re-export. It is the supported import path, and the area modules are forbidden from importing it. That is a sound rule. The file itself is a standing merge conflict, and every new function is a two-place edit (the area module and the name list in the split test).

`orm.py` is the other catalog: every table, every column width, every `to_*`. It is past 400 because the gate does not cover it. Splitting it by area, the way the repositories were split, is the change that matches the rest of `db/`. A base `Row` class would not help.

## Layering and names

What the architecture asks for is still true in the places that matter:

- `domain/` imports only other `domain` modules.
- `views/` does not import `db`. The source guard in `tests/unit/test_views_take_data.py` enforces that.
- `cli`, `web`, and `mcp_server` do not import each other. `fin web serve` and `fin mcp serve` are the two launchers, which is the allowed exception. `diagnostics.py` imports `web.login.has_password` so `fin doctor` can report a missing household password.
- Network calls are `urllib` inside `sync/transport.py`. `simplefin.py` allows only `https` hosts that are `simplefin.org` or a subdomain, refuses a URL without credentials, and the opener refuses redirects and ignores proxies.
- No `eval`, `exec`, `pickle`, or `subprocess`.

The leaks that remain are smaller:

- `views/statements.py` imports `ImportStatus` and `StatementImportResult` from `ingest.service`. `views/categories.py` imports `CategorizeResult` and `RulePreview` from `categorize.service`. `views/sync.py` imports `LinkRun` from `sync.runner`. Those are result types, and the views do not query. The packages are still coupled: a view cannot be read without those services.
- `views/audit.py` `change_link` returns web paths (`/transactions/3`, `/insights?month=2026-01`). `fin audit` never uses it. A URL builder lives in the shared view package.
- `web/access.py` `_reading` opens a normal writable session and commits on success. The name is shared with `mcp_server/access.py` `reading`, which opens `get_engine(read_only=True)`. On the web, every mutation (rules, categories, restore-adjacent writes) goes through `_reading`. The underscore also marks it private, and routes, forms, and session all import it.
- The same underscore style is on helpers that are the public API of their module: `_day`, `_id`, `_spending_range`, `_search_query`, `web_app._today`, `web_app._now`, `web_app._upload_name`. `web/routes/export.py` imports `_spending_range` from reports and `_search_query` from transactions. `web/routes/shared.py` imports from transactions. A rename looks local and breaks another route.
- CLI still builds a few tables itself: `_TagRow` in `cli/tags.py`, the folder-import table in `cli/importing.py`, and Rich tables in `cli/sync.py` and `fin doctor`. Architecture says `views` builds each row once.
- `domain/insights.py` and `domain/health.py` format English sentences with `format_cents` inside the rule functions. MCP returns that `detail` unchanged. One implementation is preserved. The sentences are not in `views`, so a wording change is a domain change and a test change in the rules.

`STILL_LOADING` in `test_views_take_data.py` is still `{"backups.py", "sync.py", "transfers.py"}`. Only `views/sync.py` still imports `finances.sync`, and only for the `LinkRun` type. The allowlist is wider than the tree.

## Tests

The suite is the right kind for this app: migrations are applied in integration tests, Hypothesis is derandomized, real PDFs stay out of the normal run, and critical modules require full branch coverage (`scripts/critical_modules.txt`, 14 paths). Bank parsers stay off that list on purpose. Reconciliation is the backstop, and a wrong section that still sums is a layout bug, not a missed branch.

The organization is what will slow the next change down.

55 files are named `*_more.py` (`test_mcp_more.py`, `test_web_login_more.py`, `test_capital_one_parser_more.py`, and the rest). The name records that the given tests shipped first and later cases had to go somewhere. It does not say which behavior lives there. A fix for findings, proposals, or a parser starts with two files, sometimes three, and the phase specs now tell the coder which `*_more.py` to extend. That convention is load-bearing and undocumented in `docs/testing.md` (the rule there is still "named `test_<module>.py`").

`docs/testing.md` also says unit tests must finish in under 10 seconds. That was written for a small suite. It is not a gate in `scripts/check.py`.

Parser tests each define their own `pages()` helper (`test_capital_one_parser.py`, `test_boa_parser.py`, `test_citi_parser.py`, `test_truist_parser.py`, `test_marcus_parser.py`, `test_boa_deposit_parser.py`, plus the `_more` variants and `test_marcus_cd.py`). `docs/testing.md` says shared helpers live in `tests/support.py` and older copies stay until the file is next edited. These copies have survived several edits.

Integration tests are 31,939 lines, about 62% of the test tree. A lot of that is the web and MCP restating a repository rule through HTTP or a tool call. That repetition is what catches a front end that forgot `pair_transfers`. It is also why a repository change fans out across `test_*_more.py` files.

## Risks

### Data

Accepting an unknown proposal kind falls through to `set_category_by_hand` (see above). The kind list in `domain/proposals.py` (`KINDS`) is not what `accept_proposal` switches on. The two can drift.

Web categorization without pairing can double-count a transfer in spending, budgets, and findings until something else pairs.

Reconciliation checks the closing balance and the declared section totals. A line in the wrong section, a purchase date that took the posted year, or a dropped check-number mark still imports when the cents match. That is true of every parser. The spot-check fixtures are the mitigation. Keep adding one when a real statement surprises the layout.

`get_engine` enables `PRAGMA foreign_keys=ON` per connection. SQLite will not enforce a `String(n)` length. The project rule is `finances.domain.text.fit` for statement and feed text, and a refusal for text a person typed. That rule is convention plus tests, not the database.

### Concurrency

`get_engine` creates a new engine on every call, creates the parent directory when the path is a file, and sets no `journal_mode` and no `busy_timeout`. The SQLAlchemy default SQLite timeout is 5 seconds. Web requests, `fin` commands, and the daily sync all open that same file. A statement import or a restore holds the write lock for the whole session. The other side then fails the commit.

`web/access.py` holds `_RESTORE_GATE` for the whole request, which serializes web requests against each other during a restore. It does not serialize the CLI or the sync process. Those are other processes.

`reading()` in the MCP server sets `PRAGMA query_only=ON`. That blocks ordinary writes on that connection. It is not a read-only URI (`mode=ro`), so the same connection could turn the pragma off. The tools do not take SQL, so this is a property of the guard, not an open hole. Backup checks do use `mode=ro` (`db/backup.py`).

Each MCP tool call and each web request builds an engine and disposes it. For one household that cost is small. It does throw away SQLite's page cache on every call.

### Auth and the boundary

These are in good shape and should stay as they are:

- The site binds to `127.0.0.1`, refuses a `Host` outside loopback and the optional Tailscale name, and sends a locked-down content security policy, `nosniff`, `DENY` framing, and `no-store`. OpenAPI and the docs routes are off. FastAPI telemetry is off in code, with a test that fails if an OpenTelemetry package is installed.
- The household password is scrypt (`n=16384`, `r=8`, `p=1`) with a random salt, checked with `hmac.compare_digest`. Failures lock at 5 (one hour), 10 (one day), and then every third failure (three days). The hash, the session key, and the lockout counter live in the OS keychain.
- The session cookie is HMAC-SHA256, `HttpOnly`, `SameSite=Strict`, idle 30 minutes, and at most one day. `Secure` is set when the request is for the Tailscale hostname or carries `X-Forwarded-Proto: https`.
- Forms use a CSRF token. Uploads are capped at 20 MB, and the stored file name is the last path segment, cut to 255 characters. Backup and restore resolve a name with a strict `finances-YYYYMMDD-HHMMSS.db` pattern inside the backup folder.
- The log filter rewrites email addresses and digit runs of six or more. A search of `src/` found no `logger.info` / `warning` / `error` calls. Amounts and merchant names are not written by the app's own log lines. The filter would not catch a four-digit amount or a merchant name if a future log line included them.

Two operational edges are worth knowing:

- `web/session.py` `gate` lets every request through when no password is stored. The bind address is loopback, so this is localhost until Tailscale Serve is pointed at the port. `fin doctor` is what reports the missing password. Turning Serve on first exposes an unlocked site to the tailnet.
- `over_https` trusts `X-Forwarded-Proto` from any caller that already passed the host check. The effect is to mark the cookie `Secure`. A local client can set the header. It cannot clear `Secure` on a request that already matches the Tailscale hostname.

The agent boundary matches the architecture. MCP write tools store proposals and advice. `accept_proposal` is reached from `fin review` and the Review page. A tool cannot change an amount, a date, a balance, or an account.

## Docs

`architecture.md` and `roadmap.md` caught up after the October audit. The roadmap status line is Phase 46, 2026-11-08. Reconciliation is documented as "no override". Budgets, the tax flag, the BoA deposit parser, the keychain contents, and the SimpleFIN and Tailscale decisions match the code.

Small drifts:

- Architecture says the CLI, the web, and MCP contain no business logic, and that neither CLI nor web builds rows of its own. The date-range parsers, `categorize_all`, the web password state machine, `_TagRow`, and the hand-built Rich tables are the exceptions.
- `tools.py` describes itself as read-only.
- `docs/testing.md` still requires `test_<module>.py` and a 10-second unit suite.
- `pyproject.toml` version is still `0.1.0`.

`docs/progress.md` is a long append-only log. It is accurate and hard to skim. The roadmap is the index; the log is the evidence.

## What to change, in order

1. **Pair after every web categorize.** One function that runs `categorize` then `pair_transfers`, used by the CLI's `categorize_all` and by the web rule, alias, and clear routes. This is the only behavior bug in this audit.
2. **Make `accept_proposal` refuse an unknown kind.** The category write should be the `CATEGORY` branch. The fallback should raise. Do the same in `proposal_out_of_date`, so a forgotten kind cannot be judged as a transfer pair.
3. **One `clean_reason` and one clock helper** for the proposal repositories, and `flatten(pages)` in the parser helpers. Small, and they remove the copies that have already drifted once (the Marcus CD parser).
4. **Point MCP `list_accounts` at `account_listing`.** Then owner and joint cannot diverge from the pages.
5. **One month-range parser** in `domain/periods` (or next to `month_range`), called by the CLI, the web, and the tools. Export routes then stop importing private helpers from sibling routes.
6. **Split `tools.py` by area** the way `web/routes/` was split: read tools, proposal tools, and the proposal JSON shape. The file is the largest module and it has no size gate, so the next tool lands in it by default.
7. **Leave `orm.py` until a table forces a split**, then split by area (accounts, statements, feed, categories, proposals), with the `to_*` functions beside their tables. Do not add a mapper base class.
8. **When a repository file next hits 400 lines, extract a cohesive module** (category deletion is the obvious one) **instead of moving a private helper to make the line count pass.** The cap is doing its job only if the new module is a real home.
9. **Name new tests for the behavior**, and when a `*_more.py` file is next edited, fold it back or give it a name that says what it covers. Update `docs/testing.md` so the `*_more.py` practice is either retired or written down.
10. **SQLite busy timeout, and WAL if the daily sync overlaps with someone using the site.** Set both in `get_engine` so the CLI, the web, and sync wait on each other instead of failing at 5 seconds. This is a behavior change and deserves a failing test first (two connections, one holding a write).

`to_account` calling `_as_utc`, narrowing `STILL_LOADING` to the files that still import `sync`, and moving `change_link` next to the History page are worth doing when those files are already open.

## Leave alone

- Parser inheritance. The six walks disagree on dates, signs, and checks. A base class becomes a hook farm. Helpers (`parse_amount`, `infer_year`, `squeeze`, and a future `flatten`) are the share point.
- A shared section walker for Truist and BoA deposit, until a third deposit layout matches them.
- Repository classes, `Finding` subclasses, and ORM rows that subclass domain dataclasses.
- Merging the three Account shapes.
- Putting every bank parser on the critical-module list. Add a fixture when a real statement fails a spot check.
- An error-class hierarchy for "not found" and "name taken". The web already catches the exception types it needs. `get_account` returning `None` while other getters raise is inconsistent and local; it is not worth a sweep.
- A tidy phase whose only product is renaming `_reading`. Rename it when the pairing fix or the read/write split touches `web/access.py`, so the name matches the session it opens.
