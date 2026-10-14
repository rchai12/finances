# Phase 8: statements supersede feed rows

## Goal

Make the feed and the statements describe each transaction **once**.

Today the two sources do not know about each other. A purchase that the feed delivered and that the monthly statement also prints is stored twice: once as a provisional row and once as a statement row. Every total would count it double.

After this phase:

- When a statement is imported, each of its lines that the feed already brought **upgrades that provisional row in place**. The row keeps its id and its feed id, and takes the statement's values. A category or note attached to the row later survives.
- A posted feed row inside the statement's period that the statement does not print is **dropped**. The statement reconciles to the cent, so it is the record.
- When the feed delivers a transaction that a statement already stored, the feed id is **linked** to the statement's row, and nothing is stored twice.
- The ledger ends up the same whichever arrives first.

This is the phase that makes "the feed is the daily view, the statement is the audit" true.

## Read first

- `AGENTS.md`: "Running commands", "Privacy rules", "Money and signs", "Architecture rules"
- `docs/architecture.md`: "Data flow", "Data model"
- `docs/phases/phase-17a-feed-core.md`: R16 to R23, which this phase extends
- `src/finances/ingest/service.py`, `src/finances/sync/service.py`, `src/finances/db/repositories.py`, `src/finances/ingest/dedup.py`
- `tests/conftest.py`: `fake_bank`, `fake_statement_pdf`, `db_engine`
- `tests/integration/test_import_service.py` and `tests/integration/test_feed_service.py`: both must keep passing unchanged

## Starting state

- Phase 17a is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `1228` when Phase 17a is the last phase built.
- `import_statement` stores every line whose fingerprint is new, and never looks at aggregator rows.
- `apply_feed` stores every feed transaction whose feed id is new, and never looks at statement rows. It already leaves a row alone once its `source` is `statement`.
- A row that came from the feed has a `feed_items` row. `delete_feed_transaction` deletes a transaction together with its `feed_items` row.
- `finances.sync`, `finances.db`, `finances.domain`, and `finances.ingest` are at 100% line and branch coverage.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/matching.py` | new: `MATCH_MAX_DAYS`, `MatchItem`, `match_one_to_one` |
| `src/finances/db/repositories.py` | five functions added (Part 2) |
| `src/finances/ingest/service.py` | `StatementImportResult` gains two fields; `import_statement` upgrades and drops feed rows |
| `src/finances/sync/service.py` | `apply_feed` links a late feed row to its statement row, or leaves it out |
| `tests/unit/test_matching.py`, `tests/integration/test_statement_supersedes.py` | given, do not change |
| `tests/integration/test_supersede_repositories.py` | new, written by you |
| `docs/progress.md` | one new entry |

You may add private helpers to the two services and to `repositories.py`. Do not change any other production file, any existing test, or `tests/conftest.py`. There is no migration in this phase: no table or column changes.

## Out of scope

- Any command or printed output. `fin import statement` does not show the two new counts yet; Phase 17b adds them with the sync commands.
- Matching by description, merchant, or card digits. Banks and providers word the same purchase differently; the match is by amount and day only.
- A match between two accounts (a card payment and its checking withdrawal). Phase 11.
- Settling a posted feed row again on a later pull (see R20).
- Changes to fingerprints, reconciliation, the parsers, or the feed types.
- New dependencies.

## Design

### The matcher, in `src/finances/domain/matching.py`

```python
MATCH_MAX_DAYS = 5


@dataclass(frozen=True)
class MatchItem:
    """One transaction as the matcher sees it: the caller's key, an amount, and a day."""

    key: int
    amount_cents: int
    day: date


def match_one_to_one(
    left: list[MatchItem], right: list[MatchItem], max_days: int = MATCH_MAX_DAYS
) -> list[tuple[int, int]]:
    """Return (left key, right key) pairs with equal amounts and days at most max_days apart."""
```

The module imports nothing from the project and touches no database. Both services use it, so "the same transaction" means one thing.

### The result

`StatementImportResult` gains two fields after `duplicates`, both defaulting to `0`:

```python
    upgraded: int = 0
    dropped: int = 0
```

### Layering

`ingest` and `sync` both import `domain.matching`. Neither imports the other. Database access stays in `db/repositories.py`: the services call repository functions and write no query.

## Requirements

### Part 1: the matcher

- **R1.** A left item and a right item are **compatible** when their amounts are equal and their days are at most `max_days` apart, in either direction. `max_days=0` means the same day.
- **R2.** Pairs are chosen in this order: fewer days apart first; among those, the item earlier in `left` first; among those, the item earlier in `right` first. A pair is taken when neither of its items is already in a pair. So each item is in at most one pair, and the closest pairs are made first.
- **R3.** The result is a list of `(left key, right key)`, ordered by the position of the left item in `left`. Keys are returned as given; they need not be positions, unique, or positive.
- **R4.** The function changes neither list, and the same lists always give the same result.

### Part 2: repository functions

All take the session first, return domain objects, and leave the commit to the caller.

- **R5.** `list_provisional_transactions(session, account_id, start, end) -> list[Transaction]` returns the account's transactions whose `source` is `aggregator`, that are not pending, and whose `posted_date` is from `start` to `end` inclusive, in id order.
- **R6.** `confirm_transaction(session, transaction_id, *, statement_id, posted_date, transaction_date, description, section, card_last4, cardholder, external_id, fingerprint) -> Transaction` sets those nine columns, sets `source` to `statement` and `is_pending` to false, and returns the stored transaction. Its id, account, amount, and creation time stay, and so does its `feed_items` row. For an unknown id it raises `ValueError("transaction not found")`.
- **R7.** `find_unlinked_statement_transactions(session, account_id, amount_cents, start, end) -> list[Transaction]` returns the account's transactions whose `source` is `statement`, whose amount is `amount_cents`, whose `posted_date` is from `start` to `end` inclusive, and that have no `feed_items` row, in id order.
- **R8.** `link_feed_transaction(session, account_id, feed_id, transaction_id) -> None` adds the `feed_items` row that ties the feed id to the transaction.
- **R9.** `statement_covers(session, account_id, day) -> bool` is true when a stored statement of that account has `period_start <= day <= period_end`.

### Part 3: importing a statement

Everything up to and including reconciliation and the fingerprint check is unchanged. A line whose fingerprint is already stored is a **duplicate**, as before, and takes no further part. The other lines are **fresh**.

- **R10.** The **candidates** are `list_provisional_transactions` for the account from `period_start` minus `MATCH_MAX_DAYS` days to `period_end` plus `MATCH_MAX_DAYS` days.
- **R11.** Fresh lines are matched to candidates with `match_one_to_one`: the fresh lines in statement order on the left, each with its amount and `posted_date`; the candidates in id order on the right, each with its amount and `posted_date`.
- **R12.** Each matched candidate is **upgraded** with `confirm_transaction`:

  | Column | Value |
  |---|---|
  | `statement_id` | the new statement |
  | `posted_date`, `section`, `cardholder`, `external_id` | the line's (`external_id` is the line's `external_ref`) |
  | `description` | the line's, through `collapse_ws`, as for an inserted line |
  | `transaction_date` | the line's; when the line has none, the row keeps the one it had |
  | `card_last4` | the line's; when the line has none, the row keeps the one it had |
  | `fingerprint` | the line's statement fingerprint |

- **R13.** Each fresh line without a match is inserted exactly as before.
- **R14.** Each candidate without a match whose `posted_date` is inside the period (`period_start <= posted_date <= period_end`) is **dropped** with `delete_feed_transaction`. A candidate without a match outside the period is left as it is: it waits for the statement of its own period.
- **R15.** Pending feed rows are never candidates. They are neither upgraded nor dropped.
- **R16.** The result's `upgraded` is the number of upgraded rows, `dropped` the number of dropped rows, and `inserted` the number of inserted lines, so that `inserted + upgraded + duplicates` equals `lines_parsed`. The stored statement's `rows_inserted` is `inserted`.
- **R17.** A dry run returns the same four counts and writes nothing. A statement that fails for any reason (unreadable, unknown account, not reconciled) changes no row and reports zero for the two new counts, as it does for the old ones.

### Part 4: applying a feed

Everything in Phase 17a stands, with one addition. A feed transaction is **settled** when it is not pending and either no stored row was found for it (17a R18 step 1) or the stored row found is a pending aggregator row. A settled transaction is handled by R18 to R20 before the 17a steps.

- **R18.** Find the **statement row** for the transaction: among `find_unlinked_statement_transactions` for the account, the transaction's amount, and the days from `posted_date` minus `MATCH_MAX_DAYS` to `posted_date` plus `MATCH_MAX_DAYS`, the one whose `posted_date` is closest to the transaction's, and among equally close ones the one with the lowest id.
- **R19.** When there is a statement row, or when there is none but `statement_covers` the transaction's `posted_date`:
  - a stored pending row found for the transaction is deleted with `delete_feed_transaction`, and the transaction is counted in `removed`;
  - otherwise the transaction is counted in `unchanged`;
  - when there is a statement row, `link_feed_transaction` ties the transaction's `feed_id` to it;
  - nothing is inserted and nothing else is updated.

  A later transaction in the same feed can no longer take a statement row that was just linked.
- **R20.** Otherwise the transaction is handled by the 17a steps as before. A transaction that is pending, and a transaction whose stored row is a posted aggregator row or a statement row, is never settled: it goes straight to the 17a steps. A posted feed row is therefore settled once, when it first arrives as posted.
- **R21.** `feed_total_cents`, the balance snapshot, and drift are computed as in 17a, after all of this. A statement row counts toward the total from the moment it is linked.
- **R22.** The same feed applied twice in a row inserts and removes nothing the second time.

### Part 5: both together

- **R23.** For a statement and a feed that describe the same account, importing the statement and then applying the feed leaves the same transactions (posted date, amount, description, source, pending flag) as applying the feed and then importing the statement, whenever each statement line has at most one feed transaction of its amount within reach and each feed transaction at most one such line. Stored ids may differ. When several equal amounts lie within reach of one another, which rows pair up can depend on the order of arrival; that is accepted.

## Given tests

Create these two files exactly as shown and do not change them. If one of their tests fails, the production code is wrong.

`tests/unit/test_matching.py` covers every branch of the matcher.

```python
import random
from datetime import date

import pytest

from finances.domain.matching import MATCH_MAX_DAYS, MatchItem, match_one_to_one


def item(key: int, cents: int, day: int) -> MatchItem:
    return MatchItem(key, cents, date(2026, 5, day))


def test_the_default_reach_is_five_days() -> None:
    assert MATCH_MAX_DAYS == 5
    assert type(MATCH_MAX_DAYS) is int


def test_a_match_item_is_frozen_and_has_three_fields() -> None:
    made = item(7, -450, 3)
    assert (made.key, made.amount_cents, made.day) == (7, -450, date(2026, 5, 3))
    with pytest.raises(AttributeError):
        made.key = 8  # type: ignore[misc]


def test_empty_lists() -> None:
    assert match_one_to_one([], []) == []
    assert match_one_to_one([item(1, -450, 3)], []) == []
    assert match_one_to_one([], [item(1, -450, 3)]) == []


def test_the_same_amount_on_the_same_day() -> None:
    assert match_one_to_one([item(10, -450, 3)], [item(77, -450, 3)]) == [(10, 77)]


@pytest.mark.parametrize("day", [10, 11, 14, 15, 20])
def test_days_apart_up_to_the_reach_in_either_direction(day: int) -> None:
    assert match_one_to_one([item(1, -450, 15)], [item(2, -450, day)]) == [(1, 2)]


@pytest.mark.parametrize("day", [1, 9, 21, 31])
def test_days_apart_beyond_the_reach(day: int) -> None:
    assert match_one_to_one([item(1, -450, 15)], [item(2, -450, day)]) == []


def test_the_reach_spans_a_month_and_a_year_end() -> None:
    left = [MatchItem(1, -450, date(2026, 12, 30))]
    right = [MatchItem(2, -450, date(2027, 1, 4))]
    assert match_one_to_one(left, right) == [(1, 2)]
    assert match_one_to_one(left, [MatchItem(2, -450, date(2027, 1, 5))]) == []


@pytest.mark.parametrize("cents", [-451, -449, 450, 0, -45000])
def test_amounts_must_be_equal_to_the_cent(cents: int) -> None:
    assert match_one_to_one([item(1, -450, 3)], [item(2, cents, 3)]) == []


def test_a_given_reach_replaces_the_default() -> None:
    left, right = [item(1, -450, 3)], [item(2, -450, 5)]
    assert match_one_to_one(left, right, max_days=1) == []
    assert match_one_to_one(left, right, max_days=2) == [(1, 2)]
    assert match_one_to_one(left, [item(2, -450, 3)], max_days=0) == [(1, 2)]
    assert match_one_to_one([item(1, -450, 1)], [item(2, -450, 31)], max_days=30) == [(1, 2)]


def test_each_item_is_used_once() -> None:
    left = [item(1, -450, 3), item(2, -450, 3)]
    assert match_one_to_one(left, [item(9, -450, 3)]) == [(1, 9)]
    right = [item(8, -450, 3), item(9, -450, 3)]
    assert match_one_to_one([item(1, -450, 3)], right) == [(1, 8)]
    assert match_one_to_one(left, right) == [(1, 8), (2, 9)]


def test_the_closest_day_wins() -> None:
    left = [item(1, -450, 10)]
    right = [item(7, -450, 14), item(8, -450, 11), item(9, -450, 6)]
    assert match_one_to_one(left, right) == [(1, 8)]


def test_closer_pairs_are_made_before_farther_ones() -> None:
    left = [item(1, -450, 10), item(2, -450, 13)]
    right = [item(8, -450, 13), item(9, -450, 16)]
    assert match_one_to_one(left, right) == [(2, 8)]
    right = [item(8, -450, 13), item(9, -450, 15)]
    assert match_one_to_one(left, right) == [(1, 9), (2, 8)]


def test_ties_go_to_the_earlier_left_item_then_the_earlier_right_item() -> None:
    left = [item(1, -450, 9), item(2, -450, 11)]
    assert match_one_to_one(left, [item(9, -450, 10)]) == [(1, 9)]
    assert match_one_to_one(list(reversed(left)), [item(9, -450, 10)]) == [(2, 9)]
    right = [item(8, -450, 12), item(9, -450, 8)]
    assert match_one_to_one([item(1, -450, 10)], right) == [(1, 8)]
    assert match_one_to_one([item(1, -450, 10)], list(reversed(right))) == [(1, 9)]


def test_pairs_come_back_in_the_order_of_the_left_list() -> None:
    left = [item(3, -100, 20), item(1, -200, 2), item(2, -300, 9)]
    right = [item(30, -300, 9), item(10, -100, 24), item(20, -200, 2)]
    assert match_one_to_one(left, right) == [(3, 10), (1, 20), (2, 30)]


def test_keys_are_returned_not_positions() -> None:
    left = [item(500, -100, 2), item(400, -100, 2)]
    right = [item(-7, -100, 2), item(0, -100, 2)]
    assert match_one_to_one(left, right) == [(500, -7), (400, 0)]


def test_different_amounts_are_matched_independently() -> None:
    left = [item(1, -450, 3), item(2, -1299, 3), item(3, -450, 4), item(4, 5000, 20)]
    right = [item(10, 5000, 22), item(11, -450, 4), item(12, -450, 3), item(13, -9999, 3)]
    assert match_one_to_one(left, right) == [(1, 12), (3, 11), (4, 10)]


def test_the_lists_are_not_changed() -> None:
    left = [item(2, -450, 4), item(1, -450, 3)]
    right = [item(9, -450, 3), item(8, -450, 4)]
    before = (list(left), list(right))
    match_one_to_one(left, right)
    assert (left, right) == before


def test_the_same_lists_always_give_the_same_pairs() -> None:
    generator = random.Random(8)
    left = [
        item(n, generator.choice([-100, -200, -300]), generator.randint(1, 28)) for n in range(40)
    ]
    right = [
        item(100 + n, generator.choice([-100, -200, -300]), generator.randint(1, 28))
        for n in range(40)
    ]
    first = match_one_to_one(left, right)
    assert first == match_one_to_one(list(left), list(right))
    assert len({pair[0] for pair in first}) == len(first)
    assert len({pair[1] for pair in first}) == len(first)
    by_key = {entry.key: entry for entry in left + right}
    for one, other in first:
        assert by_key[one].amount_cents == by_key[other].amount_cents
        assert abs((by_key[one].day - by_key[other].day).days) <= 5
    assert [pair[0] for pair in first] == [entry.key for entry in left if entry.key in dict(first)]
```

`tests/integration/test_statement_supersedes.py` fixes both services, in both orders of arrival.

```python
from datetime import date

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import FeedItemRow, StatementRow, TransactionRow
from finances.db.repositories import create_account
from finances.ingest.dedup import fingerprint_lines
from finances.ingest.service import ImportStatus, StatementImportResult, import_statement
from finances.ingest.statement import Section, StatementLine
from finances.sync.feed import AccountFeed, FeedTransaction, feed_fingerprint
from finances.sync.service import apply_feed


def may(number: int) -> date:
    return date(2026, 5, number)


def tx(feed_id: str, number: int, cents: int, text: str, **more: object) -> FeedTransaction:
    return FeedTransaction(feed_id, may(number), cents, text, **more)


def feed(*items: FeedTransaction, removed: tuple[str, ...] = ()) -> AccountFeed:
    return AccountFeed(list(items), list(removed))


def money(cents: int) -> str:
    return f"{'-' if cents < 0 else ''}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def row(number: int, cents: int, text: str, section: str = "purchases", **more: str) -> str:
    """One ROW of the fake bank's statement: posted on that day of May 2026."""
    bought = more.get("bought", "-")
    card = more.get("card", "-")
    reference = more.get("reference", "-")
    return f"2026-05-{number:02d}|{bought}|{section}|{money(cents)}|{card}|{reference}|{text}"


ROWS = (
    (3, -450, "ACME COFFEE #12"),
    (8, -2599, "FOOBAR GROCERY"),
    (20, 5000, "PAYMENT THANK YOU"),
)


@pytest.fixture
def session(db_engine: Engine, fake_bank):
    """A session on a migrated database with a card (id 1) and a checking account (id 2)."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Fake Bank", "credit_card", last4="1111")
        create_account(opened, "Test Checking", "Fake Bank", "checking", last4="2222")
        yield opened


@pytest.fixture
def statement(fake_statement_pdf):
    """Return a function that builds a May 2026 statement of account 1111 from ROW texts."""

    def build(*rows: str, start: str = "2026-05-01", end: str = "2026-05-31", **more) -> bytes:
        total = sum(
            int(text.split("|")[3].replace(".", "").replace("-", ""))
            * (-1 if text.split("|")[3].startswith("-") else 1)
            for text in rows
        )
        return fake_statement_pdf(
            start=start,
            end=end,
            opening="-100.00",
            closing=money(-10000 + total),
            rows=rows,
            **more,
        )

    return build


def default_rows() -> tuple[str, ...]:
    return (
        row(3, -450, "ACME COFFEE #12", bought="2026-05-02", card="1111", reference="7001"),
        row(8, -2599, "FOOBAR GROCERY"),
        row(20, 5000, "PAYMENT THANK YOU", section="payments_credits"),
    )


def ledger(session: Session, account_id: int = 1) -> list[tuple]:
    """Every stored transaction of the account with its feed id, in id order."""
    stmt = (
        select(TransactionRow, FeedItemRow.feed_id)
        .outerjoin(FeedItemRow, FeedItemRow.transaction_id == TransactionRow.id)
        .where(TransactionRow.account_id == account_id)
        .order_by(TransactionRow.id)
    )
    return [
        (item.id, feed_id, item.posted_date.day, item.amount_cents, item.description, item.source)
        for item, feed_id in session.execute(stmt).all()
    ]


def outcome(session: Session, account_id: int = 1) -> list[tuple]:
    """What the ledger says, without the ids: the same for either order of arrival."""
    return sorted(
        (day, cents, text, source, feed_id)
        for _, feed_id, day, cents, text, source in ledger(session, account_id)
    )


def counts(result: StatementImportResult) -> tuple[int, int, int, int]:
    return (result.inserted, result.upgraded, result.dropped, result.duplicates)


def test_the_result_has_two_new_counts_that_default_to_zero() -> None:
    result = StatementImportResult("a.pdf", ImportStatus.FAILED, "x")
    assert (result.upgraded, result.dropped) == (0, 0)
    assert (
        StatementImportResult("a.pdf", ImportStatus.IMPORTED, "imported", upgraded=2).upgraded == 2
    )


def test_a_statement_upgrades_the_rows_the_feed_brought(session: Session, statement) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("f-coffee", 2, -450, "Acme Coffee", transaction_date=may(1), card_last4="9999"),
            tx("f-grocery", 9, -2599, "FOOBAR GROCERY ONLINE", card_last4="1111"),
            tx("f-payment", 20, 5000, "PAYMENT"),
        ),
    )
    result = import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    assert result.status is ImportStatus.IMPORTED
    assert counts(result) == (0, 3, 0, 0)
    assert result.lines_parsed == 3
    assert ledger(session) == [
        (1, "f-coffee", 3, -450, "ACME COFFEE #12", "statement"),
        (2, "f-grocery", 8, -2599, "FOOBAR GROCERY", "statement"),
        (3, "f-payment", 20, 5000, "PAYMENT THANK YOU", "statement"),
    ]
    rows = session.scalars(select(TransactionRow).order_by(TransactionRow.id)).all()
    assert [(item.statement_id, item.is_pending, item.section) for item in rows] == [
        (1, False, "purchases"),
        (1, False, "purchases"),
        (1, False, "payments_credits"),
    ]
    assert [(item.transaction_date, item.card_last4, item.external_id) for item in rows] == [
        (may(2), "1111", "7001"),
        (None, "1111", None),
        (None, None, None),
    ]
    lines = [
        StatementLine(
            may(3), may(2), "ACME COFFEE #12", -450, Section.PURCHASES, "1111", None, "7001"
        ),
        StatementLine(may(8), None, "FOOBAR GROCERY", -2599, Section.PURCHASES),
        StatementLine(may(20), None, "PAYMENT THANK YOU", 5000, Section.PAYMENTS_CREDITS),
    ]
    assert [item.fingerprint for item in rows] == fingerprint_lines(1, lines)
    stored = session.scalars(select(StatementRow)).one()
    assert (stored.lines_parsed, stored.rows_inserted, stored.rows_duplicate) == (3, 0, 0)


def test_what_the_statement_does_not_say_is_kept_from_the_feed(session: Session, statement) -> None:
    apply_feed(
        session, 1, feed(tx("f-1", 8, -2599, "FOOBAR", transaction_date=may(6), card_last4="1111"))
    )
    import_statement(
        session, filename="may.pdf", content=statement(row(8, -2599, "FOOBAR GROCERY"))
    )
    stored = session.get(TransactionRow, 1)
    assert (stored.transaction_date, stored.card_last4) == (may(6), "1111")
    assert (stored.cardholder, stored.external_id, stored.source) == (None, None, "statement")


def test_lines_without_a_feed_row_are_inserted_and_leftover_feed_rows_are_dropped(
    session: Session, statement
) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("f-coffee", 3, -450, "ACME COFFEE"),
            tx("f-wrong-amount", 8, -2600, "FOOBAR GROCERY"),
            tx("f-unknown", 15, -999, "NOT ON THE STATEMENT"),
        ),
    )
    result = import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    assert counts(result) == (2, 1, 2, 0)
    assert ledger(session)[0] == (1, "f-coffee", 3, -450, "ACME COFFEE #12", "statement")
    assert [entry[1:] for entry in ledger(session)[1:]] == [
        (None, 8, -2599, "FOOBAR GROCERY", "statement"),
        (None, 20, 5000, "PAYMENT THANK YOU", "statement"),
    ]
    assert session.scalars(select(FeedItemRow.feed_id)).all() == ["f-coffee"]
    stored = session.scalars(select(StatementRow)).one()
    assert (stored.lines_parsed, stored.rows_inserted, stored.rows_duplicate) == (3, 2, 0)


def test_feed_rows_outside_the_period_wait_for_their_own_statement(
    session: Session, statement
) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("f-before", 9, -100, "BEFORE THE PERIOD"),
            tx("f-first", 10, -200, "FIRST DAY UNMATCHED"),
            tx("f-last", 20, -300, "LAST DAY UNMATCHED"),
            tx("f-after", 21, -400, "AFTER THE PERIOD"),
            tx("f-early", 7, -450, "MATCHES FROM BEFORE"),
            tx("f-late", 25, -2599, "MATCHES FROM AFTER"),
            tx("f-too-early", 2, 5000, "TOO FAR BEFORE"),
        ),
    )
    content = statement(
        row(12, -450, "ACME COFFEE #12"),
        row(20, -2599, "FOOBAR GROCERY"),
        row(10, 5000, "PAYMENT THANK YOU", section="payments_credits"),
        start="2026-05-10",
        end="2026-05-20",
    )
    result = import_statement(session, filename="mid-may.pdf", content=content)
    assert counts(result) == (1, 2, 2, 0)
    assert ledger(session) == [
        (1, "f-before", 9, -100, "BEFORE THE PERIOD", "aggregator"),
        (4, "f-after", 21, -400, "AFTER THE PERIOD", "aggregator"),
        (5, "f-early", 12, -450, "ACME COFFEE #12", "statement"),
        (6, "f-late", 20, -2599, "FOOBAR GROCERY", "statement"),
        (7, "f-too-early", 2, 5000, "TOO FAR BEFORE", "aggregator"),
        (8, None, 10, 5000, "PAYMENT THANK YOU", "statement"),
    ]


def test_pending_rows_are_neither_upgraded_nor_dropped(session: Session, statement) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("f-pending-same", 3, -450, "ACME COFFEE", is_pending=True),
            tx("f-pending-other", 15, -999, "HOTEL HOLD", is_pending=True),
        ),
    )
    result = import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    assert counts(result) == (3, 0, 0, 0)
    rows = session.scalars(select(TransactionRow).order_by(TransactionRow.id)).all()
    assert [(item.source, item.is_pending) for item in rows] == [
        ("aggregator", True),
        ("aggregator", True),
        ("statement", False),
        ("statement", False),
        ("statement", False),
    ]


def test_equal_amounts_pair_by_the_closest_day_and_each_row_once(
    session: Session, statement
) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("f-a", 12, -450, "COFFEE A"),
            tx("f-b", 4, -450, "COFFEE B"),
            tx("f-c", 5, -450, "COFFEE C"),
        ),
    )
    content = statement(row(3, -450, "ACME COFFEE ONE"), row(11, -450, "ACME COFFEE TWO"))
    result = import_statement(session, filename="may.pdf", content=content)
    assert counts(result) == (0, 2, 1, 0)
    assert ledger(session) == [
        (1, "f-a", 11, -450, "ACME COFFEE TWO", "statement"),
        (2, "f-b", 3, -450, "ACME COFFEE ONE", "statement"),
    ]


def test_another_accounts_feed_rows_are_not_touched(session: Session, statement) -> None:
    apply_feed(session, 2, feed(tx("f-1", 3, -450, "ACME COFFEE"), tx("f-2", 15, -999, "OTHER")))
    result = import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    assert counts(result) == (3, 0, 0, 0)
    assert [entry[5] for entry in ledger(session, 2)] == ["aggregator", "aggregator"]
    pull = apply_feed(session, 2, feed(tx("f-3", 8, -2599, "FOOBAR"), tx("f-4", 9, -1, "ACME")))
    assert (pull.inserted, pull.unchanged) == (2, 0)
    assert len(ledger(session, 2)) == 4
    assert [entry[1] for entry in ledger(session, 1)] == [None, None, None]


def test_a_dry_run_reports_the_counts_and_writes_nothing(session: Session, statement) -> None:
    apply_feed(
        session, 1, feed(tx("f-coffee", 3, -450, "ACME COFFEE"), tx("f-unknown", 15, -999, "OTHER"))
    )
    before = ledger(session)
    content = statement(*default_rows())
    result = import_statement(session, filename="may.pdf", content=content, dry_run=True)
    assert result.status is ImportStatus.DRY_RUN
    assert counts(result) == (2, 1, 1, 0)
    assert ledger(session) == before
    assert session.scalars(select(StatementRow)).all() == []
    assert counts(import_statement(session, filename="may.pdf", content=content)) == (2, 1, 1, 0)


def test_a_statement_that_does_not_reconcile_changes_no_feed_row(
    session: Session, fake_statement_pdf
) -> None:
    apply_feed(session, 1, feed(tx("f-coffee", 5, -450, "ACME COFFEE")))
    before = ledger(session)
    content = fake_statement_pdf(
        start="2026-05-01",
        end="2026-05-31",
        opening="-100.00",
        closing="-999.00",
        rows=(row(5, -450, "ACME COFFEE #12"),),
    )
    result = import_statement(session, filename="bad.pdf", content=content)
    assert result.status is ImportStatus.FAILED
    assert counts(result) == (0, 0, 0, 0)
    assert ledger(session) == before


def test_lines_already_stored_are_duplicates_and_claim_no_feed_row(
    session: Session, statement
) -> None:
    first = statement(row(3, -450, "ACME COFFEE"), end="2026-05-04")
    import_statement(session, filename="first.pdf", content=first)
    apply_feed(session, 1, feed(tx("f-old", 3, -450, "ACME COFFEE")))
    apply_feed(session, 1, feed(tx("f-new", 7, -450, "ACME COFFEE AGAIN")))
    assert [entry[1] for entry in ledger(session)] == ["f-old", "f-new"]
    content = statement(
        row(3, -450, "ACME COFFEE"), row(8, -2599, "FOOBAR GROCERY"), end="2026-05-30"
    )
    result = import_statement(session, filename="second.pdf", content=content)
    assert counts(result) == (1, 0, 1, 1)
    assert [entry[1:] for entry in ledger(session)] == [
        ("f-old", 3, -450, "ACME COFFEE", "statement"),
        (None, 8, -2599, "FOOBAR GROCERY", "statement"),
    ]


def test_after_an_upgrade_the_feed_leaves_the_row_alone(session: Session, statement) -> None:
    items = (tx("f-coffee", 3, -450, "Acme Coffee"), tx("f-unknown", 15, -999, "OTHER"))
    apply_feed(session, 1, feed(*items))
    import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    before = ledger(session)
    june = FeedTransaction("f-june", date(2026, 6, 1), -100, "NEXT MONTH")
    pull = apply_feed(session, 1, feed(*items, june))
    assert (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (1, 0, 0, 2)
    assert ledger(session)[:3] == before
    assert ledger(session)[3][1:] == ("f-june", 1, -100, "NEXT MONTH", "aggregator")


def test_a_feed_that_arrives_after_the_statement_is_linked_not_stored_twice(
    session: Session, statement
) -> None:
    import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    before = [entry[2:] for entry in ledger(session)]
    pull = apply_feed(
        session,
        1,
        feed(
            tx("f-coffee", 2, -450, "Acme Coffee"),
            tx("f-grocery", 13, -2599, "FOOBAR GROCERY ONLINE"),
            tx("f-payment", 20, 5000, "PAYMENT"),
        ),
    )
    assert (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (0, 0, 0, 3)
    assert pull.feed_total_cents == 1951
    assert ledger(session) == [
        (1, "f-coffee", 3, -450, "ACME COFFEE #12", "statement"),
        (2, "f-grocery", 8, -2599, "FOOBAR GROCERY", "statement"),
        (3, "f-payment", 20, 5000, "PAYMENT THANK YOU", "statement"),
    ]
    assert [entry[2:] for entry in ledger(session)] == before
    again = apply_feed(session, 1, feed(tx("f-coffee", 2, -450, "Acme Coffee")))
    assert (again.inserted, again.unchanged) == (0, 1)


def test_a_late_feed_row_inside_a_statement_period_with_no_line_is_not_stored(
    session: Session, statement
) -> None:
    import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    pull = apply_feed(
        session,
        1,
        feed(
            tx("f-wrong-amount", 8, -2600, "FOOBAR GROCERY"),
            tx("f-first-day", 1, -100, "FIRST DAY"),
            tx("f-last-day", 31, -200, "LAST DAY"),
            FeedTransaction("f-april", date(2026, 4, 30), -300, "DAY BEFORE THE PERIOD"),
            FeedTransaction("f-june", date(2026, 6, 1), -400, "DAY AFTER THE PERIOD"),
            tx("f-pending", 15, -999, "HOLD IN THE PERIOD", is_pending=True),
        ),
    )
    assert (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (3, 0, 0, 3)
    assert [entry[1] for entry in ledger(session)] == [
        None,
        None,
        None,
        "f-april",
        "f-june",
        "f-pending",
    ]
    assert pull.feed_total_cents == -700
    again = apply_feed(session, 1, feed(tx("f-wrong-amount", 8, -2600, "FOOBAR GROCERY")))
    assert (again.inserted, again.unchanged) == (0, 1)
    assert len(ledger(session)) == 6


def test_a_late_feed_row_takes_the_closest_unlinked_statement_row(
    session: Session, statement
) -> None:
    content = statement(
        row(3, -450, "COFFEE ONE"), row(11, -450, "COFFEE TWO"), row(12, -450, "COFFEE THREE")
    )
    import_statement(session, filename="may.pdf", content=content)
    apply_feed(session, 1, feed(tx("f-a", 12, -450, "A")))
    apply_feed(session, 1, feed(tx("f-b", 12, -450, "B"), tx("f-c", 8, -450, "C")))
    pull = apply_feed(session, 1, feed(tx("f-d", 12, -450, "D")))
    assert [(entry[0], entry[1]) for entry in ledger(session)] == [
        (1, "f-c"),
        (2, "f-b"),
        (3, "f-a"),
    ]
    assert (pull.inserted, pull.unchanged) == (0, 1)


def test_a_hold_that_posts_after_its_statement_gives_way_to_the_statement_row(
    session: Session, statement
) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("hold-1", 2, -450, "ACME COFFEE", is_pending=True),
            tx("hold-2", 7, -2599, "FOOBAR", is_pending=True),
            tx("hold-3", 14, -999, "HOTEL HOLD", is_pending=True),
        ),
    )
    import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    pull = apply_feed(
        session,
        1,
        feed(
            tx("hold-1", 3, -450, "ACME COFFEE"),
            tx("post-2", 8, -2599, "FOOBAR GROCERY", replaces_feed_id="hold-2"),
            tx("hold-3", 15, -1050, "HOTEL"),
            removed=("hold-2",),
        ),
    )
    assert (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (0, 0, 3, 0)
    assert ledger(session) == [
        (4, "hold-1", 3, -450, "ACME COFFEE #12", "statement"),
        (5, "post-2", 8, -2599, "FOOBAR GROCERY", "statement"),
        (6, None, 20, 5000, "PAYMENT THANK YOU", "statement"),
    ]


def test_a_hold_that_posts_outside_every_statement_is_updated_as_before(
    session: Session, statement
) -> None:
    import_statement(session, filename="may.pdf", content=statement(*default_rows()))
    apply_feed(session, 1, feed(FeedTransaction("hold-1", date(2026, 6, 2), -450, "X", True)))
    pull = apply_feed(
        session, 1, feed(FeedTransaction("hold-1", date(2026, 6, 9), -450, "X POSTED"))
    )
    assert (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (0, 1, 0, 0)
    assert ledger(session)[3] == (4, "hold-1", 9, -450, "X POSTED", "aggregator")
    assert session.get(TransactionRow, 4).fingerprint == feed_fingerprint(1, "hold-1")


@pytest.mark.parametrize("statement_first", [True, False])
def test_the_ledger_is_the_same_whichever_arrives_first(
    session: Session, statement, statement_first: bool
) -> None:
    content = statement(
        row(3, -450, "ACME COFFEE #12", bought="2026-05-02"),
        row(3, -450, "ACME COFFEE #12", bought="2026-05-02"),
        row(8, -2599, "FOOBAR GROCERY"),
        row(20, 5000, "PAYMENT THANK YOU", section="payments_credits"),
        row(28, -1500, "ACME GAS"),
        end="2026-05-28",
    )
    delivered = feed(
        tx("f-1", 2, -450, "Acme Coffee"),
        tx("f-2", 4, -450, "Acme Coffee"),
        tx("f-3", 9, -2599, "Foobar"),
        tx("f-4", 20, 5000, "Payment"),
        tx("f-5", 15, -777, "Not on the statement"),
        tx("f-6", 30, -1500, "Acme Gas"),
        tx("f-7", 30, -888, "After the period"),
        tx("f-8", 12, -321, "Hold", is_pending=True),
    )
    if statement_first:
        import_statement(session, filename="may.pdf", content=content)
        apply_feed(session, 1, delivered)
    else:
        apply_feed(session, 1, delivered)
        import_statement(session, filename="may.pdf", content=content)
    apply_feed(session, 1, delivered)
    found = outcome(session)
    assert [(day, cents, source) for day, cents, _, source, _ in found] == [
        (3, -450, "statement"),
        (3, -450, "statement"),
        (8, -2599, "statement"),
        (12, -321, "aggregator"),
        (20, 5000, "statement"),
        (28, -1500, "statement"),
        (30, -888, "aggregator"),
    ]
    assert sorted(feed_id for *_, feed_id in found) == [
        "f-1",
        "f-2",
        "f-3",
        "f-4",
        "f-6",
        "f-7",
        "f-8",
    ]
    assert [text for _, _, text, source, _ in found if source == "statement"] == [
        "ACME COFFEE #12",
        "ACME COFFEE #12",
        "FOOBAR GROCERY",
        "PAYMENT THANK YOU",
        "ACME GAS",
    ]


def test_a_posted_feed_row_is_settled_only_when_it_first_arrives(
    session: Session, statement
) -> None:
    apply_feed(session, 1, feed(tx("f-early", 9, -100, "DAY BEFORE THE PERIOD")))
    content = statement(row(12, -450, "ACME COFFEE #12"), start="2026-05-10", end="2026-05-20")
    import_statement(session, filename="mid-may.pdf", content=content)
    pull = apply_feed(session, 1, feed(tx("f-early", 11, -450, "NOW INSIDE THE PERIOD")))
    assert (pull.inserted, pull.updated, pull.removed, pull.unchanged) == (0, 1, 0, 0)
    assert ledger(session) == [
        (1, "f-early", 11, -450, "NOW INSIDE THE PERIOD", "aggregator"),
        (2, None, 12, -450, "ACME COFFEE #12", "statement"),
    ]
```

## Tests to write

`tests/integration/test_supersede_repositories.py`, on the `db_engine` fixture, one repository function at a time:

- R5: rows of another account, pending rows, and statement rows are left out; both ends of the date range are included and the days outside are not; id order
- R6: each of the eleven columns changes; the id, account, amount, creation time, and the `feed_items` row do not; a row without a `feed_items` row can be confirmed too; the `ValueError` for an unknown id, with its exact message
- R7: rows of another account, aggregator rows, rows with another amount, and rows that have a `feed_items` row are left out; both ends of the date range are included; id order
- R8: the row is stored; the same feed id twice in one account, and two feed ids for one transaction, each raise `IntegrityError`
- R9: false with no statement; true on the first and on the last day of a period; false the day before and the day after; false for another account's statement; true when the day is in the second of two statements

Every line and branch of `finances.sync`, `finances.db`, `finances.domain`, and `finances.ingest` must be reached by a test.

## Rules for this phase

- **Money is `int` cents.** Amounts are compared with `==`. No `float`.
- **The match is by amount and day.** Nothing in this phase compares descriptions.
- **A statement row is never changed by the feed.** Linking adds a `feed_items` row and touches no column of `transactions`.
- **Only feed rows are ever deleted**, and only through `delete_feed_transaction`.
- **Constant messages.** The one new message is in R6. Nothing from a statement or a feed goes into an exception, and nothing is logged or printed.
- **Database access** stays in `src/finances/db/`. No dialect-specific SQL.
- **Synthetic data only** in tests.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least N + 49 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_matching.py tests/integration/test_statement_supersedes.py --no-cov` | exactly `49 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| each of the four searches below | no output |
| `git diff HEAD --stat -- src/finances/cli src/finances/db/orm.py src/finances/db/migrations src/finances/domain/models.py src/finances/sync/feed.py src/finances/ingest/dedup.py src/finances/ingest/parsers tests/conftest.py tests/integration/test_import_service.py tests/integration/test_feed_service.py` | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.sync --cov=finances.db --cov=finances.domain --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/domain/matching.py src/finances/sync`

`git grep -n --untracked -E "^ *(import|from) +(finances|sqlalchemy)" -- src/finances/domain/matching.py`

`git grep -n --untracked -E "finances\.(ingest|cli)" -- src/finances/sync src/finances/db src/finances/domain`

`git grep -n --untracked -E "finances\.sync" -- src/finances/ingest src/finances/db src/finances/domain`

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 8: statements supersede feed rows (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. Under "Deviations", list your design choices (private helpers, how each service is divided) and anything you did that the spec did not ask for, or `None`.

In your final message, give the output line of each acceptance command, and for each of R1 to R23 the name of a test that covers it.
