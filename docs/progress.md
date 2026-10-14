# Progress log

Coding agents append one entry per phase, newest at the bottom.

Template:

```
## Phase N: <name> (YYYY-MM-DD)
- Built:
- Deviations from spec (and why):
- Follow-ups / known issues:
```

## Phase 1: Project skeleton (2026-10-01)
- Built: installable `finances` 0.1.0 package, `FIN_` settings, redacting log filter, `fin --version`, `fin doctor`, and tests.
- Deviations from spec (and why): `.gitignore` also ignores `data/samples/`, uppercase statement extensions, and `*.sqlite3`, so real exports stay untracked even if Git's ignore matching is case-sensitive. Ruff format excludes `docs/` so `ruff format --check .` does not rewrite phase specs.
- Follow-ups / known issues: tests now live in `tests/unit/` (`test_config.py`, `test_log.py`) and `tests/e2e/` (`test_cli.py`), matching `docs/testing.md`.

## Phase 2a: Coverage gate and shared fixture (2026-10-12)
- Built: pyproject.toml with pytest-cov>=5 dependency, tests/conftest.py with tmp_settings fixture, and tests/unit/test_diagnostics.py with five tests. TOTAL coverage: 93.70%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2b: Tests for Phase 1 gaps (2026-10-12)
- Built: three tests for untested Phase 1 branches (`mask_url` with a port, `mask_url` with an IPv6 host, `fin doctor` exit code 1), and the final newline of `pyproject.toml`. 16 tests pass. TOTAL coverage: 98.43%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2c: format_cents (2026-10-12)
- Built: `format_cents` in `src/finances/domain/money.py`, and `tests/unit/test_money.py`. 30 tests pass. `money.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2d: parse_money (2026-10-12)
- Built: `parse_money` in `src/finances/domain/money.py`, with the full money tests in `tests/unit/test_money.py`. 89 tests pass. `money.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2e: AccountType and Account (2026-10-12)
- Built: `AccountType` and `Account` in `src/finances/domain/models.py`, and `tests/unit/test_models.py`. 102 tests pass. `models.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2f: validate_last4 (2026-10-12)
- Built: `validate_last4` in `src/finances/domain/models.py`, with its tests in `tests/unit/test_models.py`. 122 tests pass. `models.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2g: accounts table and to_account (2026-10-12)
- Built: SQLAlchemy dependency; `Base`, `AccountRow`, and `to_account` in `src/finances/db/orm.py`; `tests/unit/test_orm.py`. 170 tests pass. `orm.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2h: get_engine and session_scope (2026-10-12)
- Built: `get_engine` and `session_scope` in `src/finances/db/engine.py`; `tests/integration/test_engine.py`. 191 tests pass. `engine.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2i: the first migration (2026-10-12)
- Built: Alembic dependency; `src/finances/db/migrations/env.py`; migration `0001` creating the `accounts` table; `tests/integration/test_migrations.py`. 208 tests pass.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2j: running migrations from code (2026-10-12)
- Built: `head_revision`, `upgrade_to_head`, and `current_revision` in `src/finances/db/migrate.py`; `db_url` and `db_engine` fixtures in `tests/conftest.py`; `tests/integration/test_migrate.py`. 228 tests pass. `migrate.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2k: get_account_by_name and create_account (2026-10-12)
- Built: `AccountExistsError`, `get_account_by_name`, and `create_account` in `src/finances/db/repositories.py`; `tests/integration/test_repositories.py`. 267 tests pass. `repositories.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2l: find_accounts_by_last4 and list_accounts (2026-10-13)
- Built: `find_accounts_by_last4` and `list_accounts` in `src/finances/db/repositories.py`, with their tests in `tests/integration/test_repositories.py`. 282 tests pass. `repositories.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 2m: the database and account commands (2026-10-13)
- Built: `fin db upgrade` in `src/finances/cli/db.py`; `fin accounts add` and `fin accounts list` in `src/finances/cli/accounts.py`; the "Database schema" check in `src/finances/diagnostics.py`; `tests/e2e/test_cli_accounts.py` and updated CLI and diagnostics tests. 315 tests pass. `finances.cli` and `diagnostics.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 3a: the statement model and parsing helpers (2026-10-13)
- Built: `StatementError`, `Section`, `StatementLine`, and `ParsedStatement` in `src/finances/ingest/statement.py`; `collapse_ws`, `parse_amount`, `infer_year`, and `parse_month_day` in `src/finances/ingest/parsers/helpers.py`; `tests/unit/test_statement.py` and `tests/unit/test_parser_helpers.py`. 450 tests pass. `finances.ingest` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None

## Phase 3b: statement checks and reading (2026-10-13)
- Built: `ReconcileResult` and `reconcile` in `src/finances/ingest/reconcile.py`; `fingerprint_lines` in `src/finances/ingest/dedup.py`; `extract_pages` in `src/finances/ingest/pdf_text.py`; `StatementParser`, `register`, `unregister`, `registered_parsers`, and `detect_parser` in `src/finances/ingest/parsers/__init__.py`; `pypdf` dependency; PDF and registry fixtures in `tests/conftest.py`; tests in `tests/unit/test_reconcile.py`, `tests/unit/test_dedup.py`, `tests/unit/test_pdf_text.py`, and `tests/unit/test_parser_registry.py`. 516 tests pass. `finances.ingest` coverage: 100%.
- Deviations from spec (and why): The parser registry is a dict keyed by parser name, which keeps registration order. No private helpers.
- Follow-ups / known issues: None

## Phase 3c: storing and importing statements (2026-10-13)
- Built: `DataSource`, `Statement`, `NewTransaction`, `Transaction`, and `BalanceSnapshot` in `src/finances/domain/models.py`; `StatementRow`, `TransactionRow`, `BalanceSnapshotRow`, and their converters in `src/finances/db/orm.py`; migration `0002_statements`; eight repository functions in `src/finances/db/repositories.py`; `ImportStatus`, `StatementImportResult`, `import_statement`, and `import_folder` in `src/finances/ingest/service.py`; the fake-bank fixtures in `tests/conftest.py`; `tests/integration/test_migration_0002.py`, `tests/unit/test_statement_models.py`, `tests/unit/test_statement_orm.py`, `tests/integration/test_statement_repositories.py`, and `tests/integration/test_import_service.py`. 590 tests pass. `finances.ingest`, `finances.db`, and `finances.domain` coverage: 100%.
- Deviations from spec (and why): `import_statement` is one function with private helpers `_match_account`, `_reconcile_message`, and `_new_transaction`. Converters share `_as_utc`, and the three timestamps share `_utc_now`. `existing_fingerprints` asks about 500 fingerprints per query. No other public names.
- Follow-ups / known issues: None

## Phase 3d: the import commands (2026-10-13)
- Built: `require_current_schema` in `src/finances/cli/common.py`; `fin import statement` and `fin import folder` in `src/finances/cli/importing.py`; `fin statements list` and `fin transactions list` in `src/finances/cli/listing.py`; the three groups registered in `src/finances/cli/main.py`; `accounts add` and `accounts list` now call `require_current_schema`. Given tests in `tests/e2e/test_cli_import.py` and `tests/e2e/test_cli_listing.py`. N was 590. 631 tests pass. `finances.cli` and `finances.diagnostics` coverage: 100%.
- Deviations from spec (and why): The two table consoles are `Console(width=200, height=25)`, because a dumb terminal ignores `COLUMNS` and wraps the rows the tests pin. `--from` and `--to` are `datetime` values parsed with `%Y-%m-%d`, because this Typer version does not accept `datetime.date`. Private helpers: `_report_statement`, `_folder_cells`, `_period`, `_account_id`, `_account_names`, `_statement_cells`, `_transaction_cells`. Constants: `_STATUS`, `_FOLDER_HEADINGS`, `_BULLETS`.
- Follow-ups / known issues: None

## Phase 4: the Capital One credit card parser (2026-10-13)
- Built: `CapitalOneCardParser` in `src/finances/ingest/parsers/capital_one.py`, registered by the three given lines at the end of `src/finances/ingest/parsers/__init__.py`. Given tests in `tests/unit/test_capital_one_parser.py` and `tests/integration/test_capital_one_import.py`; my tests in `tests/unit/test_capital_one_parser_more.py`. Phase 3d was built first, so the suite started at 631. 703 tests pass. `finances.ingest` coverage: 100%. Real-statement check: no samples on this machine.
- Deviations from spec (and why): `parse` reads the header and balances itself and hands the rest to private helpers: `_period` and `_date` for the billing period, `_find` for every summary, interest, and fee label, `_declared_totals`, `_rows` for the card sections, and `_charges` for the interest and fee lines. When a label is followed by money text that `parse_amount` rejects (such as `= = $9.00`), `_find` treats that line as not fitting and keeps looking, so `parse` raises only `StatementError`.
- Follow-ups / known issues: None

## Phase 3e: table width (2026-10-13)
- Built: `print_table` in `src/finances/cli/common.py`; `accounts list`, `doctor`, `import folder`, `statements list`, and `transactions list` print their tables with it, and no CLI module keeps a console. Given tests in `tests/unit/test_print_table.py` and `tests/e2e/test_cli_table_width.py`. N was 703. 727 tests pass. `finances.cli` coverage: 100%.
- Deviations from spec (and why): The plain case prints through a second `Console` on the same file with a width of 1,000,000 columns (`_PLAIN_WIDTH`), no colour system, no terminal, and an empty environment, and passes the table's measured maximum width to `print`. The gates were run with `FORCE_COLOR` removed from the environment, because the agent's shell exports `FORCE_COLOR=0`, which Rich treats as a terminal; the spec puts that variable out of scope.
- Follow-ups / known issues: None

## Phase 5: the Bank of America and Citi credit card parsers (2026-10-13)
- Built: `find_labeled_amount` in `src/finances/ingest/parsers/helpers.py`; `BoaCardParser` in `src/finances/ingest/parsers/boa.py`; `CitiCardParser` in `src/finances/ingest/parsers/citi.py`; both registered by the five given lines at the end of `src/finances/ingest/parsers/__init__.py`. Given tests in `tests/unit/test_find_labeled_amount.py`, `tests/unit/test_boa_parser.py`, `tests/unit/test_citi_parser.py`, and `tests/integration/test_boa_citi_import.py`; my tests in `tests/unit/test_boa_parser_more.py` and `tests/unit/test_citi_parser_more.py`. N was 727, because Phase 3e was built first. 882 tests pass. `finances.ingest` coverage: 100%. Real-statement check: no samples on this machine.
- Deviations from spec (and why): `find_labeled_amount` uses a private pattern `_LABELED_MONEY`, and its money token must not be followed by another digit, so `$5.001` does not fit. Each parser reads the header and balances in `parse` and hands the rest to private helpers: `_period`, `_declared_totals`, and `_rows` in both, `_split` in `boa.py` (tries the six-part row, then the four-part row), and `_cardholders` in `citi.py` (collects every cardholder line before rows are read). A row whose amount is zero is left out before its dates are read. The gates were run with `FORCE_COLOR` removed from the environment, as in Phase 3e, because the agent's shell exports `FORCE_COLOR=0` and two Phase 3e tests fail with it.
- Follow-ups / known issues: None

## Phase 6: the Truist and Marcus deposit account parsers (2026-10-13)
- Built: `TruistDepositParser` in `src/finances/ingest/parsers/truist.py` and `MarcusSavingsParser` in `src/finances/ingest/parsers/marcus.py`, both registered by the five given lines at the end of `src/finances/ingest/parsers/__init__.py`. Given tests in `tests/unit/test_truist_parser.py`, `tests/unit/test_marcus_parser.py`, and `tests/integration/test_truist_marcus_import.py`; my tests in `tests/unit/test_truist_parser_more.py` and `tests/unit/test_marcus_parser_more.py`. N was 882. 1038 tests pass. `finances.ingest` coverage: 100%. Real-statement check: no samples on this machine.
- Deviations from spec (and why): Each parser reads the header and balances in `parse` and hands the rest to private helpers. `truist.py` has `_account` (the first line with `CHECKING` or `SAVINGS` as a word that ends in whitespace and 4+ digits), `_balance` (used for both the previous and the new balance), `_declared_totals`, `_rows` (tracks the open section), `_row` for withdrawal and deposit rows, `_checks` for every check on a `Checks` line, and `_card_details` for the debit card date and card. `marcus.py` has `_period`, `_balance` (used for both balance labels), `_squeezed` (removes whitespace), and `_rows` (keeps the running balance and the row number). One addition the spec did not ask for: a Truist previous balance dated 12/31/9999 has no next day, so `parse` raises `truist: previous balance not found` for it instead of letting `OverflowError` escape (R25). The gates ran without the `FORCE_COLOR` workaround, because `tests/conftest.py` now clears it.
- Follow-ups / known issues: The Truist `Checks` rows (R10), the section headings standing alone on a line (R7), and the balance lines (R4) are unconfirmed until real statements pass.

## Phase 6a: repairs from the first run on real statements (2026-10-13)
- Built: `extract_pages` in `src/finances/ingest/pdf_text.py` reads a page that layout mode cannot read in plain mode, and narrows every run of three or more spaces to two. `TruistDepositParser` in `src/finances/ingest/parsers/truist.py` matches section headings and the start of a `Total` line with spaces ignored, and reads balances and declared totals with labels found loosely, the balance being the first money after its date. Given tests in `tests/unit/test_pdf_text_repairs.py` and `tests/unit/test_truist_parser_spacing.py`. N was 1038. 1133 tests pass. `finances.ingest` coverage: 100%. Real-statement check: 9 passed (8 samples and the presence check), 0 failed, 0 xfailed, in 0.79 seconds.
- Deviations from spec (and why): `pdf_text.py` has a private `_page_text` (one page: layout mode, plain mode on any exception, then `_WIDE_GAP`). `truist.py` has private `_squeezed` (removes all whitespace), `_loose` (builds a pattern from a label's characters with `\s*` between each, anchored at the line start or after two whitespace characters, followed by the given tail), `_SPACED_DATE` (the ten date characters with optional whitespace between), `_date` and `_money` (validate a match and give `None` when the date does not exist or `parse_amount` refuses the token), `_balance`, and `_first_money` for the totals. Every match on a line is tried, not only the first. `truist.py` no longer calls `find_labeled_amount`, because the labels must now be found loosely; `helpers.py` is unchanged.
- Follow-ups / known issues: The Truist `Checks` rows are still unconfirmed: no real statement with checks has been seen.

## Phase 17a: the feed core (2026-10-13)
- Built: migration `0003` (tables `feed_items` and `feed_pulls`); `FeedPull` in `src/finances/domain/models.py`; `FeedItemRow`, `FeedPullRow`, and `to_feed_pull` in `src/finances/db/orm.py`; nine repository functions in `src/finances/db/repositories.py` (`get_account`, `set_balance_snapshot`, `find_feed_transactions`, `insert_feed_transaction`, `update_feed_transaction`, `delete_feed_transaction`, `feed_posted_total`, `create_feed_pull`, `latest_feed_pull`); the new package `src/finances/sync/` with `FeedError`, `FeedTransaction`, `AccountFeed`, and `feed_fingerprint` in `feed.py` and `apply_feed` in `service.py`. Given tests in `tests/integration/test_migration_0003.py` and `tests/integration/test_feed_service.py`; my tests in `tests/unit/test_feed_models.py` and `tests/integration/test_feed_repositories.py`. N was 1133, because Phase 6a was built first. 1228 tests pass. `finances.sync`, `finances.db`, and `finances.domain` coverage: 100%.
- Deviations from spec (and why): `sync/service.py` has private `_usable_id`, `_description`, `_check` (every R16 check before anything is written), and `_unchanged`, and the constants `_ID_LIMIT` (100) and `_DESCRIPTION_LIMIT` (500). `apply_feed` looks up every `feed_id` and `replaces_feed_id` of the feed in one `find_feed_transactions` call and keeps that map current as rows are inserted or given a new feed id, so a later transaction in the same feed sees the earlier ones; removals are looked up afresh after all transactions, so an id that was just renamed is no longer found and is passed over. `repositories.py` has a private `_feed_item` (the `feed_items` row of a transaction); `find_feed_transactions` asks in chunks of `_FINGERPRINT_CHUNK`; `delete_feed_transaction` flushes the `feed_items` delete before deleting the transaction, so the foreign key is never broken. R18 numbers its steps 1, 2, 3, 3, 4 and then refers to "step 5"; I read "step 5" as the update in place.
- Follow-ups / known issues: None

## Phase 8: statements supersede feed rows (2026-10-13)
- Built: `MatchItem`, `MATCH_MAX_DAYS`, and `match_one_to_one` in the new `src/finances/domain/matching.py`; five repository functions in `src/finances/db/repositories.py` (`list_provisional_transactions`, `confirm_transaction`, `find_unlinked_statement_transactions`, `link_feed_transaction`, `statement_covers`); `upgraded` and `dropped` on `StatementImportResult`, and the upgrade, drop, and insert steps in `import_statement` in `src/finances/ingest/service.py`; settled feed transactions in `apply_feed` in `src/finances/sync/service.py`. Given tests in `tests/unit/test_matching.py` and `tests/integration/test_statement_supersedes.py`; my tests in `tests/integration/test_supersede_repositories.py`. N was 1228. 1291 tests pass. `finances.sync`, `finances.db`, `finances.domain`, and `finances.ingest` coverage: 100%.
- Deviations from spec (and why): `match_one_to_one` groups the right items by amount before it measures day gaps, so it compares only items of equal amount. `ingest/service.py` has private `_supersede` (finds the candidates, matches them, and returns the upgrades, the lines to insert, and the rows to drop, so a dry run reports the same counts) and `_confirm` (one `confirm_transaction` call per pair), and the type alias `Fresh`. On import, the upgrades are written first, then the new lines, then the drops. `sync/service.py` has a private `_statement_row` (the closest unlinked statement row, lowest id on ties). A statement row linked earlier in the same feed is left out because `link_feed_transaction` flushes, so the next `find_unlinked_statement_transactions` call no longer returns it; no separate set is kept. A settled transaction whose stored pending row is deleted is also dropped from the in-memory map before its feed id is linked to the statement row.
- Follow-ups / known issues: None

## Phase 17b: syncing from SimpleFIN (2026-10-13)
- Built: migration `0004` (table `feed_accounts`); `FeedAccount` in `src/finances/domain/models.py`; `FeedAccountRow` and `to_feed_account` in `src/finances/db/orm.py`; `map_feed_account`, `list_feed_accounts`, and `list_pending_feed_ids` in `src/finances/db/repositories.py`; the SimpleFIN client (`SyncError`, `ProviderAccount`, `ProviderAnswer`, `claim_access_url`, `fetch_accounts`, `parse_account_set`) in `src/finances/sync/simplefin.py`; `urllib_transport` in `src/finances/sync/transport.py`, the only module that opens a connection; `run_sync`, `AccountSync`, and `SyncReport` in `src/finances/sync/runner.py`. Given tests in `tests/integration/test_migration_0004.py`, `tests/unit/test_simplefin.py`, `tests/unit/test_transport.py`, and `tests/integration/test_sync_runner.py`; my tests in `tests/integration/test_feed_account_repositories.py`. N was 1291. 1388 tests pass. `finances.sync`, `finances.db`, and `finances.domain` coverage: 100%. Nothing contacted SimpleFIN.
- Deviations from spec (and why): `simplefin.py` has private `_allowed` (the parts of an https URL on `simplefin.org` or a subdomain, or `None`, also when `urlsplit` or the port cannot be read), `_usable` (an allowed URL with a user name and a password), `_seconds` (midnight UTC of a day in Unix seconds), `_clean` (R12), `_day` (the UTC date of a Unix time, counted from 1970-01-01 in whole days so the computer's time zone never matters), `_transaction`, and `_account`, and the constants `_HOST`, `_MESSAGE_LIMIT` (200), `_EPOCH`, `_SECONDS_PER_DAY`, and `_UNREADABLE` (the exceptions that `fetch_accounts` turns into "aggregator answer could not be read": `ValueError`, `TypeError`, `KeyError`, `AttributeError`, and `OverflowError` for a time too large to be a date). `parse_account_set` raises a bare `TypeError` when `accounts` is not a list, so no fourteenth message exists. The user name and password are percent-decoded before they go into the Basic header, as a URL's user information is percent-encoded. `transport.py` closes an `HTTPError` without reading it. `runner.py` has a private `_apply` (one account's feed, with the removed holds only when the answer has no message).
- Follow-ups / known issues: `urllib.request.urlopen` follows redirects and carries the `Authorization` header to the new location, whatever its host. R13 prescribes `urlopen`, so this phase keeps it; SimpleFIN Bridge does not redirect `/accounts`, but a later phase could open requests through an opener whose redirect handler refuses redirects, so the credentials can only ever reach the host in the access URL.

## Phase 17c: SimpleFIN links and the sync commands (2026-10-14)
- Built: `keyring>=25` in `pyproject.toml` (25.7.0 installed); migration `0005` (`feed_accounts.link`, the unique constraint on `link` and `provider_account_id` in place of the one on `provider_account_id`, done in batch mode); `DEFAULT_LINK` and `FeedAccount.link` in `src/finances/domain/models.py`; `FeedAccountRow.link` and its constraint in `src/finances/db/orm.py`; a `link` parameter on `map_feed_account`, `list_feed_accounts`, and `run_sync`; a transport that sends every request through one opener whose redirect handler refuses redirects; `src/finances/sync/links.py` (`validate_link_name`, `save_access_url`, `load_access_url`, `delete_access_url`); the `fin sync` commands `link`, `unlink`, `accounts`, `map`, `run`, and `status` in `src/finances/cli/sync.py`, registered in `main.py`. The given block in `tests/conftest.py`, the replaced `tests/unit/test_transport.py`, and the given `tests/integration/test_migration_0005.py`, `tests/unit/test_links.py`, `tests/integration/test_sync_links.py`, and `tests/e2e/test_cli_sync.py`. N was 1388. 1449 tests pass. `finances.sync`, `finances.db`, `finances.domain`, and `finances.cli` coverage: 100%. No `fin sync` command was run against the real Keychain or SimpleFIN.
- Deviations from spec (and why): `transport.py` has a private `_RefuseRedirects` (its `redirect_request` returns `None`) and `_OPENER`, built once at import. `links.py` has a private `_NAME` pattern; `delete_access_url` reads the entry before deleting it, so a missing entry gives `False` without a delete. The migration adds the column, fills it with a Core `update()` on a lightweight `sa.table`, then makes it non-nullable and swaps the constraint in a second batch. `cli/sync.py` has private `_fail` (prints `Error: ...` and exits 1), `_link_name`, `_not_set_up` (the message of R16), `_access` (loads a link's access URL or ends the command), `_today` (now in UTC), `_account_names`, `_run_cells`, `_drift`, and `_balance_date`, and the constant `_FEED_ID_LIMIT` (200). `fin sync run` lists the links in one session, runs each link in its own committed session, and reads account names in a third session after the runs. `fin sync status` reads the Keychain once per link.
- Follow-ups / known issues: urllib's opener honours the `HTTPS_PROXY` environment variable. In a shell whose `HTTPS_PROXY` points at a proxy on `127.0.0.1` (as the agent's sandbox does), `test_conftest_keeps_tests_off_the_network` fails: the guard allows the local proxy, and the proxy's refusal comes back as `SyncError("could not reach the aggregator")` instead of the guard's `AssertionError`. Nothing leaves the machine either way. The gates were run in a shell without proxy variables, where all 1449 tests pass.

## Phase 17d: a user agent for SimpleFIN (2026-10-14)
- Built: `USER_AGENT` (`finances/` and the package version) in `src/finances/sync/transport.py`; every request `urllib_transport` sends carries it, unless the caller gives its own `User-Agent`. Given tests in `tests/unit/test_transport_user_agent.py`. N was 1449. 1454 tests pass. `finances.sync` coverage: 100%. Nothing contacted SimpleFIN, and no `fin sync` command was run.
- Deviations from spec (and why): The request's headers are a new dictionary, `{"User-Agent": USER_AGENT, **headers}`, so the caller's value comes later and wins, and the caller's dictionary is never changed. No helper or other constant was added.
- Follow-ups / known issues: None
