# Phase 8: Statements supersede provisional CSV rows

## Goal

When a reconciled statement is imported for a period that already has provisional CSV rows, the statement becomes the record: matching CSV rows are **upgraded in place** (keeping their ids, so later categories and notes survive), unmatched statement lines are inserted, and leftover CSV rows inside the period are removed. The final database must be the same no matter whether the CSV or the statement was imported first.

## Read first

- `AGENTS.md`
- `docs/statement-formats.md` ("Cross-source notes", sections 4, 6, 7)
- `docs/progress.md`
- `src/finances/ingest/service.py` (statement import), `csv_service.py`

## In scope

- A merge step inside statement import
- Result/CLI reporting of the merge
- Order-independence tests

## Out of scope

Categories (Phase 11). Any change to CSV import other than what is needed for shared helpers.

## Why in place

Phase 11 onward attaches categories and manual overrides to transaction ids. Deleting and re-inserting would lose them. Upgrading the matched row keeps the id.

## Deliverables

### 1. Matching (`src/finances/ingest/merge.py`)

```python
@dataclass(frozen=True)
class MergePlan:
    upgrades: list[tuple[int, StatementLine]]   # (existing csv transaction id, statement line)
    inserts: list[StatementLine]
    drop_ids: list[int]                         # csv rows inside the period with no match

def plan_merge(stmt: ParsedStatement, provisional: list[Transaction], *,
               other_periods: list[tuple[date, date]],
               max_days: int = MATCH_MAX_DAYS) -> MergePlan
```
- `max_days` defaults to `MATCH_MAX_DAYS` from `ingest/matching.py` (Phase 7).
- `provisional` = this account's `source = "csv"` rows with `posted_date` in `[period_start - max_days, period_end + max_days]`.
- Pairing uses **`match_one_to_one` from Phase 7**. Do not write a second matcher; the CSV import and the statement merge must agree on what "same transaction" means.
- `drop_ids` = unmatched provisional rows that are now inside a closed, reconciled period:
  - `posted_date` in `[period_start, period_end]` of this statement, or
  - `posted_date` in `[period_start - max_days, period_start)` **and** that date lies inside another reconciled statement period of this account (a boundary-zone row kept by Phase 7 that this statement did not claim either, so it appears on neither statement).
- Other unmatched rows are left alone; they belong to a statement not yet imported.
- Pure function, no DB access. To check the second drop rule, the caller passes in the account's other reconciled periods: `plan_merge(stmt, provisional, other_periods=[(start, end), ...])`.

### 2. Applying the plan (statement import service)

Inside the existing single transaction, after reconciliation passes:
- **Upgrades**: overwrite `posted_date`, `transaction_date` (keep the CSV value if the statement has none), `amount_cents`, `raw_description`, `description_normalized`, `section`, `card_last4`, `cardholder` (keep CSV value if the statement has none), `external_id`, `fingerprint`, `import_batch_id`, and set `source = "statement"`. Keep `id`, `bank_merchant`, `bank_category`, and any columns added by later phases.
- **Inserts**: as before (fingerprint dedup still applies).
- **Drops**: delete those rows.
- The balance snapshot logic is unchanged. CSV-sourced balance snapshots dated inside the period stay (they are still true daily balances).

`StatementImportResult` gains `upgraded: int` and `provisional_dropped: int`. CLI output shows them. Dry run computes and reports the plan without writing.

### 3. Repository helpers

- `list_provisional(session, account_id, start, end) -> list[Transaction]`
- `upgrade_transaction(session, txn_id, fields: dict) -> None` (whitelisted fields only)
- `delete_transactions(session, ids) -> int`

## Tests

Use the fake statement parser from Phase 3 and the synthetic CSV fixtures from Phase 7 (add a fake CSV profile in tests if that is simpler).

- `plan_merge` unit tests:
  - exact date + amount match → upgrade.
  - date off by 2 days (sale vs post date) → upgrade.
  - two identical amounts on nearby days pair by closest date.
  - statement line with no CSV counterpart → insert.
  - CSV row inside the period with no counterpart → drop; after the period → untouched.
  - **Boundary hand-off**: previous statement ends Jan 23; a provisional CSV row dated Jan 23 (kept by Phase 7's boundary rule) matches a line on this statement (period Jan 24 to Feb 23, posted Jan 24) → upgraded.
  - Same boundary row with no match on this statement → dropped (it is inside the previous reconciled period and on neither statement).
  - Same boundary row when no previous statement exists → untouched.
  - amount differs by 1 cent → no match (insert + drop).
  - determinism: same inputs in shuffled order produce the same plan.
- Service tests:
  - **Order independence**: (a) import CSV then statement, (b) statement then CSV. Compare the final set of `(posted_date, amount_cents, source, description_normalized)` tuples: identical.
  - **Full scenario** (the user's real workflow, synthetic data): January statement (Dec 24 to Jan 23); a "last 30 days" CSV covering Jan 21 to Feb 20, including a purchase dated Jan 23 that posts Jan 24; then the February statement (Jan 24 to Feb 23). After each step, assert the transaction count, how many are provisional, and that no real transaction appears twice or goes missing. After the February statement, zero provisional rows remain before Feb 24.
  - Upgraded row keeps its id and its `bank_category`.
  - A row with a manually set value in a column the upgrade does not touch (simulate with `bank_merchant`) survives.
  - Failed reconciliation → no merge, nothing written.
  - Dry run reports upgrade/insert/drop counts and writes nothing.

## Acceptance criteria

```powershell
ruff check . ; ruff format --check . ; pytest
```
Then, on a scratch database (`$env:FIN_DATA_DIR="data/scratch"`), import the real Truist checking CSV first and the matching Truist PDF statement second: the statement import reports upgrades for the overlapping days and zero provisional rows dropped. Report only counts in `docs/progress.md`.

Append your entry to `docs/progress.md`.
