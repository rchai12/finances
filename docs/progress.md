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

## Phase 21: people and ownership (2026-10-14)
- Built: migration `0006` (`people`, `account_owners`, `cardholder_aliases`); `Person` in `src/finances/domain/models.py`; `src/finances/domain/people.py` (`JOINT`, `RESERVED_NAMES`, `NAME_LIMIT`, `normalize_cardholder`, `validate_person_name`, `person_for`); `PersonRow`, `AccountOwnerRow`, `CardholderAliasRow`, and `to_person` in `src/finances/db/orm.py`; `PersonExistsError`, `create_person`, `get_person_by_name`, `list_people`, `set_account_owner`, `list_account_owners`, `set_cardholder_alias`, and `list_cardholder_aliases` in `src/finances/db/repositories.py`; the new `src/finances/analysis` package (`Attribution`, `load_attribution`, `list_transactions_with_people`); `fin people add`, `list`, and `alias` in `src/finances/cli/people.py`, registered in `main.py` after `sync`; `fin accounts set-owner` and an `Owner` column in `fin accounts list`; a `Person` column and `--person` in `fin transactions list`. The four given test files, and `tests/integration/test_people_repositories.py`. N was 1454. 1552 tests pass. `finances.analysis`, `finances.db`, `finances.domain`, and `finances.cli` coverage: 100%.
- Deviations from spec (and why): `analysis/people.py` has a private `_wanted` (the attribution a `--person` value keeps: a person's stored name, `JOINT`, or `None`). With `person` given, `list_transactions_with_people` asks `list_transactions` for `limit` rows, keeps that person's, and doubles the number asked for until it has `limit` kept rows or `list_transactions` returns fewer rows than asked, so the limit counts the kept rows without a new repository function. `create_person` finds a duplicate through `get_person_by_name`. `cli/people.py` and `cli/accounts.py` each have a private `_fail` (prints `Error: ...` and exits 1). `fin accounts set-owner` looks up the account before the owner, so an unknown account is reported first. `fin accounts list` reads owners through `load_attribution`.
- Follow-ups / known issues: As in Phase 17c, the full `pytest` gates were run outside the agent's sandbox, whose `HTTPS_PROXY` makes `test_conftest_keeps_tests_off_the_network` fail.

## Phase 16a: the web interface, foundation (2026-10-14)
- Built: `fastapi>=0.143`, `uvicorn>=0.30`, and `jinja2>=3.1` in `dependencies`, `httpx2>=2.0` in the `dev` extras, and package data for the templates and stylesheet in `pyproject.toml` (installed: FastAPI 0.143.1, Starlette 1.8.0, uvicorn 0.54.0, Jinja2 3.1.6, httpx2 2.13.1; pip also moved `click` to 8.5.0); `Settings.web_port` (default 8765, `FIN_WEB_PORT`); `src/finances/web/app.py` (`HOST`, `SECURITY_HEADERS`, `NOT_MIGRATED`, `create_app`) with the read-only pages `/accounts`, `/people`, `/transactions`, and `/sync`, `/` redirecting to `/accounts`, and the stylesheet at `/static`; the given templates and stylesheet; `fin web serve` in `src/finances/cli/web.py`, registered in `main.py` after `people`. The given tests in `tests/unit/test_web_security.py`, `tests/integration/test_web_pages.py`, and `tests/e2e/test_cli_web.py`. N was 1552 (the spec's 1528 predates the final Phase 21 count). 1620 tests pass. `finances.web`, `finances.cli`, and `finances.config` coverage: 100%. `fin web serve` was not run against the real database.
- Deviations from spec (and why): `app.py` has a private ASGI class `_Guard` (the host check and the headers; a request with no `Host` header or more than one is refused like a wrong one), `_reading` (one engine per request, disposed afterwards, since the server lives long), `_render` (adds `section`), `_not_migrated`, `_day`, `_limit`, `_find` (the filters of R11 in their order: account, from, to, limit, then the person through `list_transactions_with_people`), `_transaction_row`, `_keychain`, and `_sync_row`, and the constants `_HERE`, `_TEMPLATES`, `_HEADER_BYTES`, `_BULLETS`, `_DEFAULT_LIMIT`, `_LIMIT_MAX`, `_DATE`, and `_WHOLE`. A date must match `[0-9]{4}-[0-9]{2}-[0-9]{2}` and be a real day, as `date.fromisoformat` alone also accepts forms such as `20260501`. An absent or empty `limit` is shown as `50` in the form. `SyncError` is imported from `finances.sync.simplefin`, where it is defined, to catch what `load_access_url` raises. `fin web serve` passes `host=HOST`. The SimpleFIN page reads the Keychain once per link.
- Follow-ups / known issues: As in Phase 17c, the full `pytest` gates were run outside the agent's sandbox, whose `HTTPS_PROXY` makes `test_conftest_keeps_tests_off_the_network` fail.

## Phase 16b: the web interface, setup forms (2026-10-14)
- Built: `python-multipart>=0.0.9` in `pyproject.toml` (0.0.32 installed); `urllib_transport`'s opener now starts with `ProxyHandler({})`, so proxy settings in the environment are ignored (R18); `LinkRun` and `run_links` in `src/finances/sync/runner.py`; in `src/finances/web/app.py`, `CSRF_COOKIE`, `NOTICES`, `ACCOUNT_TYPES`, the form token and notices in every rendered page, and the routes `POST /accounts/add`, `/accounts/owner`, `/people/add`, `/people/alias`, `/sync/link`, `/sync/unlink`, `/sync/map`, `/sync/create`, `/sync/run`, and `GET /sync/accounts`; the given templates and stylesheet. The given tests in `tests/unit/test_run_links.py`, `tests/unit/test_transport_proxies.py`, `tests/integration/test_web_forms.py`, and `tests/integration/test_web_sync_setup.py`. N was 1620. 1753 tests pass. `finances.web` and `finances.sync` coverage: 100%. Nothing contacted SimpleFIN or the real Keychain, and `fin web serve` was not run.
- Deviations from spec (and why): `app.py` has private `_engine` (an engine disposed when the request ends; `_reading` now uses it), `_today` (today in UTC), `_done` (the `303` redirect), `_drift`, `_run_row` (the cells of `fin sync run`), `_blank_account_form`, `_add_account` (R5's type check, then `create_account`), `_feed_id` (R12's length check), `_accounts_page`, `_people_page`, `_sync_page`, `_error_page` (`error.html` with `back` `/sync`, status 400), and a `refused` closure inside `create_app` (R3's three checks in order), and the constants `_FEED_ID_LIMIT` (200), `_TOKEN`, `_REFUSALS`, and `_Field`. Each form route does its work inside one session and turns a `ValueError`, `SyncError`, `AccountExistsError`, or `PersonExistsError` into the refusal, so a refused `/sync/create` rolls the new account back with the mapping. The form token check also requires the cookie to be a well-formed token (43 URL-safe characters), so an empty cookie never matches an empty field, and compares the two as bytes, since `hmac.compare_digest` refuses non-ASCII text. The SimpleFIN page reads the Keychain once per link.
- Follow-ups / known issues: The Phase 17c known issue is resolved: the full `pytest` run passes inside the agent's sandbox, with `HTTPS_PROXY` set.

## Phase 9: test hardening, and the bugs it found (2026-10-14)
- Built: N was 1753; the full run now passes 1856 (the seven given files add 127 tests and replace 29, and `test_migration_chain.py` and `test_log_hygiene.py` add 5). Hypothesis is a dev dependency with one shared profile in `tests/conftest.py` (derandomized, no example database). The five fixes: (1) pairing statement lines with feed rows now takes the most pairs, then the most pairs on the same side of a period's edge, then the fewest days apart, for a whole statement (`_supersede`, zones from every stored period plus the new one) or a whole pull (`apply_feed` pairs every settling transaction before applying any); (2) `create_account` refuses a name or institution over 100 characters; (3) `create_account` refuses a currency that is not three ASCII capitals (`validate_currency`); (4) the statement import cuts a description to 500 characters and a cardholder or reference to 100 (`DESCRIPTION_LIMIT`, `TEXT_LIMIT`), with fingerprints still taken from the parsed line; (5) `RecursionError` from a deeply nested SimpleFIN answer becomes "aggregator answer could not be read".
- Deviations from spec (and why): None. Design choices: R5 is a dynamic program per amount over the two day-sorted lists (`_pair_sorted`), where `best[i][j]` is the best score of the items from `i` and `j` on, scores are tuples (pairs, same-zone pairs, minus total days) compared in order, and the walk from (0, 0) is the one R5 prescribes. Helpers: `_gain` (one pair's score, or `None` beyond `max_days`) and `_plus` in `domain/matching.py`; `_description` and `_cut` in `ingest/service.py`; `_resolve` (the stored row and its feed id, with the `replaces_feed_id` fallback), `_settles`, and `_statement_rows` (one fetch per amount over the earliest settling day minus 5 to the latest plus 5, then one pairing) replace `_statement_row` in `sync/service.py`; the constant `ACCOUNT_TEXT_LIMIT` (100) in `db/repositories.py`.
- Follow-ups / known issues:
  - A statement is the record for its own period (Phase 8). When the feed dates a purchase inside an imported statement's period but the statement does not print it, the purchase is not stored, even when it belongs to the next or previous period's statement that is not imported yet. It appears when that statement is imported. This needs the feed to date a purchase earlier than the statement does, across a period's first day, or later across its last day.
  - A feed row and a statement line of the same amount at most five days apart, with nothing else to pair with, are one purchase, even when they straddle a period's edge. That is what lets a purchase the feed posts a few days late join its statement line. Two different purchases can be taken for one only when the feed has not been pulled for longer than the gap between them.
  - The ledger property models feeds that date a purchase on the statement's day or up to three days later, statements imported at least three days after their period, and pulls that deliver the last 30 days. Holds that later post are covered by Phase 8's tests, not by the generated runs.

## Phase 16c: forms that work in a real browser (2026-10-14)
- Built: N was 1856; the full run now passes 1877. `SECURITY_HEADERS["referrer-policy"]` is `same-origin` instead of `no-referrer`, so a browser sends the site's true `Origin` on its own forms instead of `null`, and the origin check of Phase 16b accepts them. The expected value in `test_the_security_headers` changed to match, and the given `tests/integration/test_web_browser_origin.py` posts every form with the `Origin` a browser sends under the served policy, at `127.0.0.1` and at `localhost`. The origin check, the form token, and the refusal of `Origin: null` are unchanged.
- Deviations from spec (and why): None.
- Follow-ups / known issues: None.

## Phase 16d: new SimpleFIN accounts (2026-10-14)
- Built: N was 1877; the full run now passes 1961. Migration `0007` adds `feed_seen_accounts` (`FeedSeenAccountRow`, `to_seen_feed_account`, `SeenFeedAccount`). `domain/feed_setup.py` guesses a new account's tidied name and institution, type (whole words of the name), last four digits (the last run of ASCII digits when it is four long), owner (a person named like the link), and an existing unmapped account it looks like (same last four digits, else same name). The repositories gain `record_seen_feed_account` (one row per link and SimpleFIN account, text cut to 100 characters), `list_new_feed_accounts`, `set_feed_account_ignored`, and `list_feed_links`. `run_sync` records every account SimpleFIN delivers before it applies anything. `fin sync run` and Sync now run every link with a mapping or a seen account, and say how many new accounts each link that ran has. The SimpleFIN page offers each new account with a pre-filled Create and map form (with an owner), a Map form with the look-alike account preselected, and Don't track; accounts not tracked are listed with Track again (`POST /sync/ignore`, `POST /sync/track`). `POST /sync/create` takes `owner`, and it and `POST /sync/map` take `next=sync` to return to the SimpleFIN page.
- Deviations from spec (and why): None. Helpers: `_feed_text` in `db/repositories.py` (whitespace collapsed, cut to `ACCOUNT_TEXT_LIMIT`, trailing spaces removed); `_owner_id` in `web/app.py` (Joint or a person, else `person not found`), now shared by `/accounts/owner` and `/sync/create` with the same behaviour as before; `_mapped` (the redirect chosen by `next`); and a `tracking` closure behind `/sync/ignore` and `/sync/track`.
- Follow-ups / known issues: None.

## Phase 10: quality gates (2026-10-14)
- Built: N was 1961; the full run now passes 1986. `scripts/check.py` (standard library only, nothing imported from `finances`) runs lint, the format check, the test suite with a JSON coverage report written to a temporary folder, and the critical coverage gate, which requires every line and branch of the nine modules in `scripts/critical_modules.txt`; `--real-samples` then runs the opt-in real-statement check. It stops at the first failure and ends with a summary. `scripts/install-git-hooks.sh` and `scripts/uninstall-git-hooks.sh` install and remove `scripts/git-hooks/pre-commit` (lint, then format), leaving any hook that is not ours alone. `docs/testing.md` (mutation row, rule 6, critical modules, commands) and `AGENTS.md` (run the check before reporting) are updated.
- Deviations from spec (and why): None. Helpers: the constant `COVERAGE_STEP` and `_critical_coverage` (reads the report and the list, prints each gap).
- Follow-ups / known issues: `tests/e2e/test_git_hooks.py` runs `git init` in a temporary folder. The agent's sandbox forbids writing any `.git/hooks` folder, so those nine tests error there; they and the check pass when run outside the sandbox. The hook was not installed in this repository.

## Phase 22: one source for view rows (2026-10-14)
- Built: N was 1986; the full run now passes 2007. The new package `finances.views` builds each view's rows once, as plain text in frozen dataclasses: `format.py` (`BULLETS`, `mask_last4`, `drift_text`, `balance_date_text`, `last_pull_text`), `accounts.py` (`AccountRow`, `account_rows`), `people.py` (`PersonRow`, `people_rows`), `transactions.py` (`TransactionRow`, `transaction_row`), and `sync.py` (`StatusRow`, `RunRow`, `SetupOffer`, `keychain_state`, `status_rows`, `run_rows`, `waiting_counts`, `simplefin_messages`, `unmapped_accounts`, `setup_offers`). `account_names` in the repositories replaces the eight inline id-to-name lookups. `LinkRun` gains `failure` and `cause` (`KEYCHAIN_FAILED`, `NOT_SET_UP`, `AGGREGATOR_FAILED`), so `fin sync run` now goes through `run_links` and keeps its exact messages. The command line adds each view row's cells in field order; the web passes the rows to the unchanged templates, and turns each setup offer into the dictionary the SimpleFIN page reads. The private row helpers and `_BULLETS` are gone from `cli` and `web/app.py`. `docs/architecture.md` describes the views.
- Deviations from spec (and why): None. Helper: `_failure_text` in `cli/sync.py` (the stderr text for each kind of failure).
- Follow-ups / known issues: None.

## Phase 23: one home for text rules, limits, and input checks (2026-10-14)
- Built: N was 2007; the full run now passes 2060. `finances.domain.text` holds `NAME_LIMIT`, `DESCRIPTION_LIMIT`, `FEED_ID_LIMIT`, `PROVIDER_ACCOUNT_ID_LIMIT`, `collapse_ws`, and `fit`; the ORM's twelve 100, 200, and 500 wide columns take their width from it, and the older names (`helpers.collapse_ws`, `people.NAME_LIMIT`, `feed_setup.TEXT_LIMIT`, `ingest.service.TEXT_LIMIT` and `DESCRIPTION_LIMIT`) stay as the same objects or values. The four copies of "collapse, cut, trim" use `fit`. `validate_provider_account_id` checks a SimpleFIN id, and `map_feed_account` runs it first. `create_account` checks the type first, with the friendly message the web gave. New repository functions `resolve_owner` (Joint, a person, or `person not found`) and `statement_periods` serve the command line, the web, and both pairing services. `cli/common.fail` replaces three `_fail`, and `helpers.squeeze` the two `_squeezed`. `fin sync map` still checks the id before the account, and the web forms keep their order. `AGENTS.md` names `finances.domain.text`.
- Deviations from spec (and why): `domain/models.py` writes the 200 of `validate_provider_account_id` itself instead of importing `PROVIDER_ACCOUNT_ID_LIMIT`, because `tests/unit/test_statement_models.py` pins that module to the standard library; the given tests tie both to 200. `ingest/service.py` imports `fit` and the limits from `finances.domain.text`, but not `collapse_ws`, which it no longer uses once its `_description` is gone. With the user's approval, the imports of the given `tests/unit/test_text.py` and of Phase 22's `tests/integration/test_views.py` were re-sorted by `ruff check --fix` (import order only). Ruff counts a `finances` module as first-party only once it exists, so both files failed lint on a fresh run; `test_views.py` had passed only from ruff's cache.
- Follow-ups / known issues: Given tests that import a module the phase creates should list it with the other `finances` imports, so they pass lint once the module exists.

## Phase 11a: categories, merchants, and rules (2026-10-14)
- Built: N was 2060; the full run now passes 2200. Migration `0008` (given) adds `categories` with the default two-level tree, `category_rules`, and `transaction_categories`; the ORM maps them (`CategoryRow`, `CategoryRuleRow`, `TransactionCategoryRow`), with `CATEGORY_NAME_LIMIT` and `RULE_PATTERN_LIMIT` from `domain.text`. `domain/merchants.clean_merchant` works out a merchant in the spec's ten steps; `domain/rules` normalizes patterns, matches (`contains`, `starts_with`, `equals`), and picks the highest-priority rule, the oldest among equals. The repositories add the category tree, rules, assignments (by rule or by hand), and the uncategorized listing; `delete_rule` removes its assignments first, and `delete_feed_transaction` removes a feed row's assignment before the row. `categorize` runs the rules over every transaction and never touches one set by hand. `views/categories.py` builds the lines and the `Categorized ...` sentence. New commands: `fin categories list|add`, `fin rules list|add|delete`, `fin categorize`, `fin uncategorized`, and `fin transactions set-category`. `fin import statement`, `fin import folder`, and `fin sync run` categorize quietly after their work.
- Deviations from spec (and why): None. Choices: `fin import statement` skips categorizing with `--dry-run`, as `fin import folder` does, since a dry run writes nothing; both categorize after any other run, even a failed one, which changes nothing then. `categorize_all` in `cli/categories.py` opens the session the commands and the imports and sync categorize in. `fin transactions set-category` is registered on `transactions_app` from `cli/categories.py`, so `cli/listing.py` is unchanged. Helpers: `_category_row`, `_leaf_category`, `_assignment_row`, `_assign`, and `_require_transaction` in the repositories; `_without_prefix` and `_cut_at` in `merchants.py`; `_category` in the service; `_kind` in the views; `_print_rows` in the commands. `categorize` writes only the assignments that differ. Verification found that no test failed if `fin sync run` printed the categorizing line; `test_a_sync_categorizes_quietly` now pins its output to the table alone.
- Follow-ups / known issues: None.

## Phase 11b: categories on the web (2026-10-14)
- Built: N was 2200; the full run now passes 2249. The menu has **Categories**: the 50 latest uncategorized transactions (each opening its page), the rules with a **Delete** button each, **Add a rule**, the category tree, and **Add a category**. Every transaction has its own page (`/transactions/ID`) with its details, merchant, category and how it was set, a form to set the category by hand, **Leave it to the rules** when it was set by hand, and **Make a rule** filled in from its merchant. Each date on the Transactions page opens its transaction. Adding or deleting a rule and leaving a category to the rules run the rules again in the same session; **Sync now** categorizes quietly when a link ran. New: `get_transaction` in the repositories; `TransactionDetail`, `transaction_detail`, and `category_choices` in `views/categories.py`; the five notices; six given templates; two lines of `app.css`.
- Deviations from spec (and why): None. Choices: `tests/integration/test_category_views.py`, named in "Tests to write" but not in the Scope table, holds the tests the spec asks for plus four page tests (the two new pages refuse an unmigrated database; a form posted to a transaction id that is not a number answers 404), which the coverage gate needs and the given file cannot hold. An id in a path or a form is read as a whole number of at most 18 digits, so a longer one is "not found" instead of overflowing SQLite's integer. The 404 page for an unknown transaction links back to Transactions. The routes for a transaction's category check that it exists first, so a refusal after that is a 400 on its page; clearing has no other refusal, so it has no error branch. Sync now calls `categorize` itself instead of `cli.categories.categorize_all`, since `web` does not import `cli`. Helpers in `web/app.py`: `_id`, `_priority`, `_rule_form`, `_categories_page`, `_missing_transaction`, `_transaction_page`, `_known_transaction`; `_set_by` in the views.
- Follow-ups / known issues: None.

## Phase 11c: transfers (2026-10-14)
- Tests: 2249 -> 2311 (given 41)
- New public names: `domain.models`: `AUTO`, `CONFIRMED`, `TransferPair`; `domain.transfers`: `TRANSFER_MAX_DAYS`, `Movement`, `transfer_candidates`, `clear_pairs`; `db.orm`: `TransferPairRow`, `TransferRejectionRow`, `to_transfer_pair`; `db.repositories`: `list_transfer_movements`, `list_transfer_rejections`, `list_transfer_pairs`, `create_transfer_pair`, `reject_transfer`, `unpair_transfer`; `categorize.transfers`: `TransferResult`, `pair_transfers`, `transfer_suggestions`; `views.transfers`: `TransferLine`, `SuggestionLine`, `transfer_lines`, `suggestion_lines`; `cli.transfers`: `transfers_app`
- Changed files: 17
- Deviations:
  - Given `tests/e2e/test_cli_transfers.py` and its spec block: the In date cell `"2026-05-0{}"` became `"2026-05-0{1}"` (the `{}` repeated the in id, a day before the fixture's date); approved by the owner.
  - `create_transfer_pair` refuses a wrong status after the four ordered messages; `reject_transfer` and `unpair_transfer` store a rejection only when it is not already there.
  - `transfer_candidates` indexes inflows by amount instead of comparing every pair of movements.
  - `cli/transfers.py` has its own `_print_rows`, the same as `cli/categories.py`'s, since `cli/common.py` is not in Scope.
- Follow-ups:
  - `_print_rows` is now in two CLI modules; it could move to `cli/common.py` in a phase that touches that file.

## Phase 11d: transfers on the web (2026-10-14)
- Tests: 2311 -> 2342 (given 23)
- New public names: `db.repositories`: `find_transfer_pair`; `views.transfers`: `transfer_of`
- Changed files: 9
- Deviations:
  - `transfer_lines` and `transfer_of` build each line with the private `_line`; `transfer_lines` now sorts the finished lines by date and pair id instead of sorting the pairs first.
  - `create_transfer_pair` uses `find_transfer_pair` for its "already in a transfer" check, replacing its own query.
  - The `in` form field is read through `Form(alias="in")`, since `in` cannot be a parameter name; `_transfer_sides` turns `out` and `in` into ids or refuses with `transaction not found`.
- Follow-ups:
  - None

## Phase 12a: spending (2026-10-14)
- Tests: 2342 -> 2403 (given 43)
- New public names: `domain.spending`: `SPENDING`, `INCOME`, `TRANSFER`, `UNSORTED_IN`, `UNCATEGORIZED`, `UNASSIGNED`, `NO_CARD`, `BY`, `Flow`, `SpendingLine`, `SpendingSummary`, `flow_kind`, `check_by`, `spending_lines`, `summarize`, `month_range`, `month_bounds`; `db.repositories`: `list_transactions_between`; `analysis.spending`: `SpendingReport`, `load_flows`, `spending_report`; `views.spending`: `SpendingRow`, `spending_rows`, `spending_heading`, `spending_summary`; `cli.reports`: `spending_command`
- Changed files: 10
- Deviations:
  - `domain.spending.check_by` (not in the design) raises the `by must be one of: ...` message; `spending_lines` and `spending_report` both call it, so the report checks `--by` before the dates without repeating the message.
  - `month_range` turns a year of `0000` into the month message too, since `date` refuses year 0 with its own text.
  - `cli/reports.py` builds its Rich table inline instead of copying `_print_rows` a third time.
- Follow-ups:
  - None

## Phase 12b: balances and months (2026-10-15)
- Tests: 2403 -> 2433 (given 17)
- New public names: `domain.periods`: `MONTHS_MAX`, `months_ending`, `uncovered`; `db.repositories`: `account_data_span`; `analysis.balances`: `BalanceLine`, `BalanceReport`, `balance_report`; `analysis.months`: `MonthLine`, `month_report`; `views.balances`: `BalanceRow`, `balance_rows`, `balance_summary`; `views.months`: `MonthRow`, `month_rows`, `month_heading`, `month_notes`; `cli.reports`: `balances_command`, `months_command`
- Changed files: 12
- Deviations:
  - `account_data_span` reads the earliest and latest feed pull through `to_feed_pull`, so `pulled_at` is taken as UTC before its date is used.
  - `cli/reports.py` gained a private `_print_rows`, and `fin spending` now uses it too, replacing its inline table.
  - `fin months` with no active account still prints the heading and every month as covered; the spec gives it no `No accounts.` line.
- Follow-ups:
  - `_print_rows` is now in three CLI modules (`categories`, `transfers`, `reports`); it could move to `cli/common.py` in a phase that touches that file.

## Phase 12c: reports on the web (2026-10-15)
- Tests: 2433 -> 2449 (given 16)
- New public names: None
- Changed files: 5
- Deviations:
  - A `by` field sent empty is read as `category`, like a missing one, matching "given means not empty" for the other fields.
  - The private `_spending_range` in `web/app.py` reads the four fields in the spec's order; the months end on the spending report's end day, or on today when the request is refused.
  - No `tests/integration/test_web_reports_more.py`: the given tests reach every branch.
- Follow-ups:
  - None

## Phase 13a: recurring charges (2026-10-15)
- Tests: 2449 -> 2490 (given 33)
- New public names: `domain.recurring`: `CADENCES`, `Charge`, `Recurring`, `find_recurring`, `monthly_cost`, `next_charge`; `analysis.recurring`: `recurring_charges`; `views.recurring`: `RecurringRow`, `recurring_rows`, `recurring_summary`; `cli.reports`: `recurring_command`
- Changed files: 9
- Deviations:
  - The bands, monthly factors, and calendar steps are private dictionaries in `domain/recurring.py`; `monthly_cost` rounds half up with integer arithmetic, and `next_charge` clips the day with `calendar.monthrange`.
- Follow-ups:
  - None

## Phase 13b: findings and merchant stats (2026-10-15)
- Tests: 2490 -> 2523 (given 21)
- New public names: `domain.recurring`: `Recurring.previous_cents`; `domain.insights`: `TYPES`, `SEVERITIES`, `Finding`, `MerchantStat`, `merchant_stats`, `spikes`, `frequent_small`, `charges_found`, `price_increases`, `overlaps`, `order_findings`; `analysis.insights`: `InsightsReport`, `insights_report`; `views.insights`: `FindingRow`, `MerchantRow`, `finding_rows`, `findings_summary`, `merchant_rows`; `cli.reports`: `insights_command`, `merchants_command`
- Changed files: 10
- Deviations:
  - The merchant-to-category map for overlaps comes from the charges in the four loaded months (the one `load_flows` call), so a yearly series whose latest charge is older than that has no category and is left out of overlaps.
  - `charges_found` splits merchants into words with `[^\W_]+` and compares them in upper case.
  - `fin merchants` builds the whole `insights_report` and shows its merchant stats; both commands share a private `_first_day` for `--month`.
  - The thresholds are private constants in `domain/insights.py`; `views/insights.py` has its own `_change`, the same as `views/months.py`'s.
- Follow-ups:
  - If overlaps should see yearly subscriptions, the category map needs charges from before the four-month window (a second read or a wider one).

## Phase 13c: insights on the web (2026-10-15)
- Tests: 2523 -> 2533 (given 9)
- New public names: `views.insights`: `insights_heading`
- Changed files: 11
- Deviations:
  - `tests/integration/test_web_insights_more.py` holds one test, added after verification: no given test failed when the page listed inactive recurring charges (the given data has none), so R4's "active only" had no test. The spec allows this file only for an unreached branch.
  - Of the two failing-first tests named for R1, only `test_a_month` failed before the fix; `test_a_yearly_plan_charged_before_the_window_still_overlaps` already passed, since an April report reads January to April and the yearly charge is on 8 January.
  - The category map reads the charges a second time, from `date.min` to the month's last day; the route reads the month through a private `_month_start` and calls `recurring_charges` itself for the page's recurring table.
- Follow-ups:
  - None

## Phase 16e: find and drill down (2026-10-15)
- Tests: 2533 -> 2578 (given 28)
- New public names: `domain.spending`: `PENDING`, `KINDS`; `db.repositories`: `list_transactions_by_day`; `analysis.spending`: `flows_for`; `analysis.search`: `TransactionQuery`, `FoundTransaction`, `search_transactions`; `views.transactions`: `found_rows`
- Changed files: 13
- Deviations:
  - `search_transactions` checks the account and the person with `get_account_by_name` and `get_person_by_name` (both ignore case and outer spaces), and compares `joint` and `unassigned` to the flow's `Joint` and `Unassigned` ignoring case, like every other label.
  - The route builds the query in a private `_search_query` (messages 1 to 3 in order), replacing `_find`; the fields and the kept filters are private tuples `_SEARCH_FIELDS` and `_KEPT`.
- Follow-ups:
  - None

## Phase 24: backups (2026-10-15)
- Tests: 2578 -> 2611 (given 18)
- New public names: `config`: `Settings.backup_dir`, `Settings.backup_keep`, `Settings.effective_backup_dir`; `db.backup`: `BackupCheck`, `BackupResult`, `RestoreResult`, `backup_name`, `list_backups`, `check_backup`, `make_backup`, `restore_backup`; `cli.backup`: `app`, `run_command`, `list_command`, `restore_command`
- Changed files: 15
- Deviations:
  - Adding `db/backup.py` to `scripts/critical_modules.txt` broke `tests/unit/test_check_script.py::test_the_shipped_list` (and three tests that read the same list), which hard-codes the list; with the owner's approval, `db/backup.py` was added to its `CRITICAL` and to the critical-module list in `docs/testing.md`, as that file asks. Neither path is in the Scope table.
  - `restore_backup` also refuses a URL that is not a database file, with `backups need a database file`, after checking the backup; the spec's message table names the case but R5 does not place it.
  - `check_backup` reads the known revisions with `ScriptDirectory(MIGRATIONS).walk_revisions()`; the read-only open is `Path.resolve().as_uri()` plus `?mode=ro`, so no `urllib` is needed.
  - `tests/integration/test_backup_more.py` has `test_a_check_changes_none_of_the_files_it_reads`, added after verification: with the not-a-file guard in place, no test failed when `check_backup` opened read-write. A read-write open merges and deletes a backup's leftover `-wal` file; the test checks the database and its `-wal` are left byte for byte.
- Follow-ups:
  - A phase that adds a critical module should list `tests/unit/test_check_script.py` and `docs/testing.md` in its Scope.

## Phase 24b: backups on the web (2026-10-15)
- Tests: 2611 -> 2652 (given 35)
- New public names: `db.backup`: `list_set_asides`, `find_backup`, `delete_backup`, `taken_at`; `views.format`: `size_text`; `views.backups`: `BackupRow`, `backup_rows`, `taken_text`; `web.app`: `GET /backups`, `POST /backups/run`, `GET`/`POST /backups/delete`, `GET`/`POST /backups/restore`
- Changed files: 11
- Deviations:
  - The given `test_only_backups_in_the_folder_can_be_deleted[""]` expected the paragraph `" is not a backup in the folder"`, but `tests/support.Page` strips paragraph text, so no code could pass it; with the owner's approval its one assertion compares `NOT_A_BACKUP.format(name).strip()`. The message sent is the spec's, the name as sent.
  - `create_app` splits the form check: `forged` checks the origin and the token on any database, and `refused` is `forged` then the database check; only `POST /backups/run` uses `refused`.
  - The Backups page and the confirmation page are rendered by private `_backups_page` and `_backup_confirm`; `_engine` waits on the gate with `with _RESTORE_GATE: pass`.
  - `size_text` rounds megabytes half up as `(20 * size + MB) // (2 * MB)` tenths.
  - `tests/integration/test_backups_page_more.py` also covers a refused Back up now (`keep` below 1), which no given test reached.
- Follow-ups:
  - A given test that names an empty or space-edged value should expect the text `Page` reads, which is stripped.

## Phase 16f: editing categories and rules (2026-10-15)
- Tests: 2652 -> 2692 (given 32)
- New public names: `db.repositories`: `CategoryDeletion`, `rename_category`, `delete_category`, `edit_rule`; `cli.categories`: `rename_category_command`, `delete_category_command`, `edit_rule_command`; `web.app`: `POST /categories/rename`, `POST /categories/delete`, `GET`/`POST /categories/rules/{id}`
- Changed files: 9
- Deviations:
  - `GET /categories/rules/{rule_id}` answers 405 when the id is `add` or `delete`, so earlier tests that expect Method Not Allowed on those POST-only paths still pass; without that, the parameterized route would answer 404.
  - The Categories page and the rule edit page are rendered by private `_categories_page` (now with `rename_form` and `delete_form`) and `_rule_edit_page`.
- Follow-ups:
  - When a phase adds `GET /path/{id}` beside existing `POST /path/add` and `POST /path/delete`, say that GET on `add` and `delete` must stay 405 (or reserve those names).

## Phase 16j: accounts and bulk categorizing (2026-10-15)
- Tests: 2692 -> 2728 (given 29)
- New public names: `db.repositories`: `rename_account`, `set_account_active`, `set_categories_by_hand`, `clear_categories_by_hand`; `cli.accounts`: `rename`, `deactivate`, `activate`; `cli.categories`: `set-category` with several `--id`; `web.app`: `POST /accounts/rename`, `POST /accounts/active`, `POST /transactions/bulk`
- Changed files: 10
- Deviations:
  - `web.app` has private `_filter_query` and `_back_filters` so the Transactions page and bulk redirect share one ordered filter list.
  - `tests/integration/test_account_and_bulk_repositories.py` raises Starlette's form `max_fields` to 2000 for the 1001-id refusal, because the default of 1000 would answer before the app's message.
- Follow-ups:
  - A bulk POST that sends more than about 1000 form fields needs a higher `Request.form` `max_fields` (or another shape) before the route can refuse with the app's own message.

## Phase 16g: statement upload (2026-10-15)
- Tests: 2728 -> 2763 (given 23)
- New public names: `domain.periods.statement_gaps`; `analysis.statements`: `StatementGap`, `statement_gap_lines`; `views.statements`: `StatementRow`, `GapRow`, `statement_rows`, `gap_rows`, `import_rows`; `web.app`: `GET /statements`, `POST /statements/upload`, bulk form `max_fields=1100`
- Changed files: 11
- Deviations:
  - `POST /transactions/bulk` and `POST /statements/upload` are `async` and run database work with `run_in_threadpool`.
  - Private `_upload_name` and `_statements_page` hold the file-name cut and the page context.
- Follow-ups:
  - The TestClient's multipart layer already strips a Windows-style file path, and `import_statement` uses `Path.name`, so a given test that only uploads through the client does not prove the route's own folder strip; call `_upload_name` directly for that.

## Phase 25: data health (2026-10-16)
- Tests: 2763 -> 2791 (given 22)
- New public names: `domain.health`: `BACKUP_STALE_DAYS`, `SYNC_STALE_DAYS`, `STATEMENT_STALE_DAYS`, `KINDS`, `AccountFacts`, `Problem`, `health_problems`; `analysis.health`: `account_facts`, `gather_health`; `views.health`: `HealthRow`, `health_rows`, `health_summary`; `cli.health`: `health_command` (`fin health`)
- Changed files: 9
- Deviations:
  - Action texts are module constants in `domain/health.py`.
- Follow-ups:
  - The given "no statements needed" case for a mapped account uses a fresh statement end or none with `has_data` true, so it does not fail when statements checks also run for mapped accounts; pin a mapped account with a stale statement end for that spot check.

## Phase 16h: dashboard (2026-10-16)
- Tests: 2791 -> 2798 (given 5; removed 1 earlier home-redirect test)
- New public names: `db.repositories.count_uncategorized`; `analysis.dashboard`: `Dashboard`, `dashboard`; `web.app`: `GET /` is the Home page
- Changed files: 9
- Deviations:
  - `_PROBLEM_LINKS` in `web/app.py` maps each health kind to its page.
- Follow-ups: none

## Phase 16i: account pages (2026-10-16)
- Tests: 2798 -> 2813 (given 11; coder 4)
- New public names: `db.repositories.list_balance_snapshots`; `analysis.account_page`: `AccountMonth`, `AccountPage`, `account_page`; `views.account_page`: `AccountMonthRow`, `BalanceHistoryRow`, `account_detail_rows`, `group_rows`, `account_month_rows`, `balance_history_rows`; `web.app`: `GET /account`
- Changed files: 11
- Deviations:
  - `_missing_account` in `web/app.py` renders `error.html` with a link back to `/accounts`.
  - A bad `month` still loads today's month for details and months, clears spending, and answers `400` with the message as `error`.
- Follow-ups: none

## Phase 16k: charts (2026-10-16)
- Tests: 2813 -> 2829 (given 13; coder 3)
- New public names: `views.charts`: `pie_chart`, `months_chart`, `balance_chart`; `web.app`: CSP `script-src 'self'`; account page chart JSON; `static/charts.js`; vendored Chart.js 4.4.6
- Changed files: 12
- Deviations: none
- Follow-ups: none

## Phase 13d: unusual charges (2026-10-16)
- Tests: 2829 -> 2838 (given 6; coder 3)
- New public names: `domain.insights`: `duplicates`, `large_first_charges`; TYPES gains `duplicate`, `large_first_charge`; `analysis.insights` includes both
- Changed files: 8
- Deviations:
  - `insights_report` loads all flows once through M's end for categories, `seen`, and the four-month window.
- Follow-ups: none

## Phase 26a: budgets (2026-10-16)
- Tests: 2838 -> 2868 (given 26; coder 4)
- New public names: migration `0010`; `Budget` / `BudgetRow`; `set_budget`, `remove_budget`, `list_budgets`; `domain.budgets`; `over_budget` finding; `budget_report`; `views.budgets`; `fin budgets`
- Changed files: 17
- Deviations:
  - `delete_category` calls private `_delete_budget_for` before deleting the category or group row.
- Follow-ups: none

## Phase 26b: budgets on the web (2026-10-16)
- Tests: 2868 -> 2887 (given 16; coder 3)
- New public names: `analysis.dashboard.Dashboard.budgets`; `web.app`: `GET /budgets`, `POST /budgets/set`, `POST /budgets/remove`, notices `budget-set` / `budget-removed`
- Changed files: 9
- Deviations:
  - `_budgets_page` in `web/app.py` gathers the Budgets page context; a bad month clears `month_label` so the table is omitted.
- Follow-ups: none

## Phase 31: tidy (2026-10-16)
- Tests: 2887 -> 2895 (given 8)
- New public names: `finances.clock.today`; `cli.common.print_rows`; `domain.budgets.AMOUNT_MESSAGE`
- Changed files: 16
- Deviations:
  - `tests/integration/test_budgets_more.py` patches `finances.clock.today` instead of `finances.cli.budgets.date`, which the tidy removed.
  - `web.app._utc_today` keeps the Sync routes on the UTC date.
- Follow-ups: none

## Phase 32: split the web app (2026-10-16)
- Tests: 2895 -> 2911 (given 16)
- New public names: None
- Changed files: 10
- Deviations:
  - Shared helpers live in `web/access.py`, `web/forms.py`, `web/helpers.py`, and `web/render.py`; routers read clock and restore hooks through `finances.web.app` at call time; `create_app` imports routers inside the function.
- Follow-ups:
  - Spot checks 1 and 2 as written do not fail under that allowed design (lazy router import; `_RESTORE_GATE` used from `access._reading` for page requests).

## Phase 33: sync resilience (2026-10-21)
- Tests: 2911 -> 2932 (given 15)
- New public names: `sync.simplefin`: `AggregatorUnreachable`; `domain.models`: `SyncFailure`; `db.orm`: `SyncFailureRow`; `db.repositories`: `record_sync_failure`, `clear_sync_failure`, `list_sync_failures`; `sync.runner`: `RETRY_WAITS`; `views.sync`: `failure_lines`
- Changed files: 21
- Deviations:
  - The failure-message column uses `PROVIDER_ACCOUNT_ID_LIMIT` (200) so `test_the_orm_names_its_widths_by_constant` still passes.
  - `test_retries_without_an_on_retry` covers the retry loop when `on_retry` is omitted.
- Follow-ups:
  - Reinstall both schedule jobs after commit: `scripts/install-sync-schedule.sh 7 0` and `scripts/install-backup-schedule.sh 2 0`.
  - `docs/roadmap.md` also holds uncommitted Phase 34 outline notes, not part of this phase.

## Phase 27a: upcoming bills and recurring income (2026-10-21)
- Tests: 2932 -> 2954 (given 17)
- New public names: `domain.recurring`: `INCOME_CADENCES`, `find_recurring_income`; `domain.upcoming`: `BILL`, `INCOME`, `Upcoming`, `expected`; `analysis.recurring`: `recurring_income`; `analysis.upcoming`: `UpcomingReport`, `upcoming_report`; `views.upcoming`: `UpcomingRow`, `upcoming_rows`, `upcoming_heading`, `upcoming_summary`; `views.recurring`: `recurring_income_summary`; `cli.reports`: `upcoming_command`
- Changed files: 12
- Deviations:
  - Charges and income share `_find` and `_series`; `two_weeks` is in the shared band tables, and `find_recurring` still passes `CADENCES`.
- Follow-ups: none

## Phase 27b: a 30-day forecast per account (2026-10-22)
- Tests: 2954 -> 2976 (given 16)
- New public names: `domain.forecast`: `Step`, `Walk`, `walk`; `analysis.forecast`: `AccountForecast`, `ForecastReport`, `forecast_report`; `views.forecast`: `ForecastRow`, `StepRow`, `forecast_rows`, `forecast_heading`, `no_balance_line`, `account_heading`, `starting_line`, `step_rows`, `lowest_line`; `cli.reports`: `forecast_command`
- Changed files: 9
- Deviations:
  - `walk` totals in and out with two independent sign checks; a private helper picks one account's charges and credits from the loaded flows.
- Follow-ups: none

## Phase 27c: looking ahead on the web (2026-10-22)
- Tests: 2976 -> 2997 (given 14)
- New public names: `analysis.dashboard.Dashboard.upcoming`; `web.routes.reports`: `DAYS_REFUSED`, `ahead`
- Changed files: 11
- Deviations:
  - `_days` uses `str.isdigit`; wrapped a 130-character line in `template_check.py` left by the 27c spec commit so ruff could pass.
- Follow-ups:
  - Wrap that `template_check.py` line in the spec tree so later phases do not have to touch it.

## Phase 27d: net worth over time (2026-10-22)
- Tests: 2997 -> 3014 (given 13)
- New public names: `domain.networth`: `NetWorthPoint`, `point_days`, `net_worth_points`; `analysis.networth`: `net_worth_over_time`; `views.networth`: `NetWorthRow`, `net_worth_rows`; `views.charts`: `net_worth_chart`
- Changed files: 12
- Deviations:
  - `point_days` uses `months_ending` then replaces this month with today; `_days` refuses non-ASCII with `str.isascii`.
- Follow-ups:
  - Known limit: a closed account leaves past months too, so closing an account changes the history shown.

## Phase 14a: the MCP server and the account tools (2026-10-22)
- Tests: 3014 -> 3033 (given 13)
- New public names: `db.engine.get_engine` (`read_only`); `mcp_server.access`: `NOT_MIGRATED`, `reading`; `mcp_server.server`: `SERVER_NAME`, `INSTRUCTIONS`, `READ_ONLY`, `build_server`, `serve`; `mcp_server.tools`: `list_accounts`, `get_balances`, `get_net_worth`; `cli.mcp`: `app`, `serve`
- Changed files: 9
- Deviations:
  - tools registered in a loop over a table; `reading()` uses try/finally.
- Follow-ups:
  - installed mcp 2.3.0
