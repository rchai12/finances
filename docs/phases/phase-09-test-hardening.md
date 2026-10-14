# Phase 9: test hardening, and the bugs it found

## Goal

The per-phase tests check the examples each spec gave. This phase adds tests that check **rules over many generated inputs**: money and dates read back exactly, a damaged statement is refused rather than misread, any SimpleFIN answer is read or refused cleanly, every web form survives any text, every stored text fits its column, and, most important, **statements and feed pulls arriving in any realistic order store each purchase exactly once**.

Those tests were written and run before this spec. They found five bugs, which this phase fixes:

1. **Pairing lost or doubled equal purchases.** Pairing feed rows with statement lines took the closest pair first, one at a time. With several purchases of the same amount a few days apart (a daily coffee, a transit fare), that order of choices could leave a statement line and a feed row unpaired that should have been a pair, so the purchase was stored twice; or it could pair a feed row with the wrong line across the first or last day of a statement period, so a purchase disappeared. In a pull, the first transaction listed took the nearest statement row, so a feed listed newest first (as SimpleFIN lists it) lost purchases on the first pull after a statement import. Pairing now takes **the most pairs possible**, then **the most pairs on the same side of a period's edge**, then **the fewest days apart**, for a whole statement or a whole pull at once.
2. **Account names and institutions of any length were stored.** SQLite does not enforce `VARCHAR(100)`, so a 300-character name was kept, and a database that does enforce it would refuse the data later.
3. **Any text was accepted as a currency**, such as `usd dollars`, into a three-character column.
4. **Statement text longer than its column was stored.** A parser can return a description over 500 characters or a cardholder name over 100; the feed already cut descriptions to 500, the statement import did not.
5. **A deeply nested SimpleFIN answer crashed the reader** with `RecursionError` instead of the usual "aggregator answer could not be read", which would end `fin sync run` with a traceback and the web page with a server error.

There are no new features.

### Known limits (not bugs, recorded so nobody chases them)

- **A statement is the record for its own period** (Phase 8). When the feed dates a purchase inside an imported statement's period but the statement does not print it, the purchase is not stored, even when it belongs to the next or previous period's statement that is not imported yet. It appears when that statement is imported. This needs the feed to date a purchase earlier than the statement does, across a period's first day, or later across its last day.
- **A feed row and a statement line of the same amount at most five days apart, with nothing else to pair with, are one purchase**, even when they straddle a period's edge. That is what lets a purchase the feed posts a few days late join its statement line. Two different purchases can be taken for one only when the feed has not been pulled for longer than the gap between them.
- The ledger property models feeds that date a purchase on the statement's day or up to three days later, statements imported at least three days after their period, and pulls that deliver the last 30 days. Holds that later post are covered by Phase 8's tests, not by the generated runs.

## Read first

- `AGENTS.md`, `docs/testing.md` (updated for this phase: no golden snapshots, the property profile)
- `docs/phases/phase-08-statements-supersede-feed.md`: R1 to R4 (the matcher), R10 to R16 (import), Part 4 with R18 to R22 (applying a feed). This phase replaces its R2 and R18.
- `src/finances/domain/matching.py`, `src/finances/ingest/service.py`, `src/finances/sync/service.py`, `src/finances/db/repositories.py` (`create_account`), `src/finances/domain/models.py` (`validate_last4`), `src/finances/sync/simplefin.py`
- `tests/conftest.py` (`fake_bank`, `parser_registry`, `db_engine`, `tmp_settings`, `keychain`)

## Starting state

- Phase 16b and the architect changes below are committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `1753` when Phase 16b is the last phase built.
- Architect changes already committed with this spec, which pass before and after this phase: `tests/e2e/test_cli_table_width.py` names its long account with exactly 100 characters (it used 117, which this phase refuses); `docs/testing.md` drops the golden-snapshot layer.
- `hypothesis` is not installed in `.venv`.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `pyproject.toml` | `hypothesis` in the `dev` extras |
| `.gitignore` | one line: `.hypothesis/` |
| `tests/conftest.py` | the property profile (R2), given below |
| `src/finances/domain/matching.py` | `MatchItem.zone`, `period_zone`, the new pairing (R3 to R6) |
| `src/finances/ingest/service.py` | zones when a statement pairs (R7); text cut to fit (R12), with `DESCRIPTION_LIMIT` and `TEXT_LIMIT` |
| `src/finances/sync/service.py` | a pull pairs all its settling transactions at once (R8) |
| `src/finances/domain/models.py` | `validate_currency` (R10) |
| `src/finances/db/repositories.py` | `create_account` checks lengths and the currency (R9, R11) |
| `src/finances/sync/simplefin.py` | `RecursionError` is unreadable (R13) |
| `tests/unit/test_matching.py` | replaced by the given file |
| `tests/unit/test_properties_money.py`, `tests/unit/test_properties_ingest.py`, `tests/unit/test_parser_fuzz.py`, `tests/unit/test_simplefin_fuzz.py`, `tests/integration/test_ledger_properties.py`, `tests/integration/test_text_limits.py` | new: given, do not change |
| `tests/integration/test_migration_chain.py`, `tests/integration/test_log_hygiene.py` | new: yours (R14, R15) |
| `docs/progress.md` | one new entry |

You may add private helpers inside the listed modules. Do not change any other production file, any other existing test, or any migration. This phase adds no migration.

## Out of scope

- **Golden snapshot files.** The parser tests already compare the full list of parsed lines for every fixture; a second copy as JSON adds nothing.
- Any change to the drop rules of Phase 8 (R14, and the "covered by a statement" rule of R19), or to `MATCH_MAX_DAYS`.
- Pairing that uses descriptions, or a pairing within one amount across different amounts.
- A currency option in the web form, currency conversion, or upper-casing a currency for the user.
- A database-level length check, or a migration.
- Mutation testing and per-module coverage gates (Phase 10).
- Changing a parser. The fuzz tests found none to fix.

## Dependencies

Add to the `dev` extras in `pyproject.toml`, after `"httpx2>=2.0"`:

```toml
    "hypothesis>=6.100",
```

Then install:

`.venv/bin/python -m pip install -e ".[dev]"`

## Design

```python
# src/finances/domain/matching.py
@dataclass(frozen=True)
class MatchItem:
    # One transaction as the matcher sees it: the caller's key, an amount, a day, and a zone.
    key: int
    amount_cents: int
    day: date
    zone: int = 0


def period_zone(day: date, periods: list[tuple[date, date]]) -> int: ...


def match_one_to_one(
    left: list[MatchItem], right: list[MatchItem], max_days: int = MATCH_MAX_DAYS
) -> list[tuple[int, int]]: ...   # signature unchanged
```

```python
# src/finances/domain/models.py
def validate_currency(currency: str) -> str: ...
```

```python
# src/finances/ingest/service.py
DESCRIPTION_LIMIT = 500
TEXT_LIMIT = 100
```

Messages, in full:

| Where | Message |
|---|---|
| `create_account`, name longer than 100 after removing outer spaces | `account name must be at most 100 characters` |
| `create_account`, institution longer than 100 after removing outer spaces | `institution must be at most 100 characters` |
| `validate_currency` | `currency must be three capital letters` |

## Requirements

### Part 1: the property tests run the same way every time

- **R1.** `hypothesis>=6.100` is a dev dependency, and `.gitignore` gains the line `.hypothesis/`.
- **R2.** `tests/conftest.py` registers and loads this profile. Add `from hypothesis import HealthCheck, settings` after `import pytest`, and this block right before `_ENV_KEYS = (`:

```python
# Every property test runs the same examples on every run, and keeps no example database.
settings.register_profile(
    "finances",
    database=None,
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
settings.load_profile("finances")
```

No test may set `derandomize=False`, a `database`, or a seed of its own.

### Part 2: pairing

Phase 8's R1 (when two items are compatible), R3 (the result's order and keys), and R4 (the lists are not changed, and the same lists give the same result) stand. R2 is replaced by R5.

- **R3.** `MatchItem` gains a fourth field, `zone: int = 0`. Existing callers that pass three fields keep working.
- **R4.** `period_zone(day, periods)` returns the zone of a day among statement periods given as `(first day, last day)` in any order. With the periods sorted by first day, the days before period `k` (counting from 0) are zone `2k`, the days of period `k` are zone `2k + 1`, and the days after the last period are zone `2n` for `n` periods. With no periods every day is zone `0`. Example: for periods 1 to 31 January and 1 to 31 March, 31 December is zone 0, any day of January zone 1, 15 February zone 2, any day of March zone 3, and 1 April zone 4.
- **R5.** `match_one_to_one` pairs each amount separately. For one amount:
  1. Sort the left items and the right items each by day, then by position in their list.
  2. Consider the pairings of compatible items in which pairs do not cross: when two paired left items are in one order, their partners are in the same order.
  3. Keep those with the **most pairs**; among them, those with the **most pairs whose two items have the same zone**; among them, those with the **smallest total of days apart**.
  4. Of these best pairings, return the one found by walking both sorted lists from the start: at each step, if pairing the two current items still allows a best pairing, pair them and step past both; otherwise, if stepping past the current right item still allows one, do that; otherwise step past the current left item.

  When zones never decrease as days increase and every period is longer than `max_days` days, as `period_zone` gives, no pairing that crosses scores better, so this is the best pairing of all. A dynamic program over the two sorted lists computes it in `O(left × right)` per amount; any method that returns the same pairs is correct.
- **R6.** Examples, with every item of amount -450 in May 2026, written as key/day/zone:
  - left 1/10, 2/13 and right 8/13, 9/16 give `[(1, 8), (2, 9)]` (closest first would give only `(2, 8)`);
  - left 1/10/1 and right 8/9/0, 9/13/1 give `[(1, 9)]`; with right 8/9/0 alone, `[(1, 8)]`;
  - left 1/10/1, 2/5/0 and right 8/9/1, 9/15/2 give `[(1, 9), (2, 8)]`: two pairs across zones beat one pair within a zone;
  - left 1/15, 2/15 and right 7/1, 8/18 give `[(1, 8)]`, and with the left list reversed `[(2, 8)]`.

### Part 3: where pairing is used

- **R7.** When a statement is imported, the pairing of Phase 8's R11 gives each item a zone: `period_zone` of its day among the periods of the account's stored statements plus the period of the statement being imported. The left list is the fresh lines in parse order (keys are their positions), the right list is the candidates in id order (keys are their ids). Everything else of Phase 8's R10 to R16 is unchanged.
- **R8.** `apply_feed` pairs a pull's settled transactions all at once, before it applies any of them, in place of Phase 8's R18 (one transaction at a time, closest first):
  - **Settled** is as Phase 8's Part 4 defines it, unchanged: not pending, and either no stored row was found for it (under its feed id or the id it replaces) or the stored row found is a pending aggregator row.
  - Left: the settled transactions in feed order. Right: for each amount among them, `find_unlinked_statement_transactions` from the earliest settled day of that amount minus `MATCH_MAX_DAYS` to the latest plus `MATCH_MAX_DAYS`, each row once, in id order.
  - Zones: `period_zone` of each day among the periods of the account's stored statements.
  - A settled transaction's statement row is its partner from `match_one_to_one`, or none. Phase 8's R19 to R22 use it as before. Transactions that are not settled take part in no pairing.

  So the order a pull lists its transactions in no longer changes what is stored.

### Part 4: text that fits

- **R9.** `create_account` removes outer spaces from the name and the institution (as now) and refuses either when longer than 100 characters, with the messages above. Its checks run in this order: empty name, empty institution, long name, long institution, a duplicate name, `last4`, the type, the currency. The command `fin accounts add` and the web form already print any `ValueError` from it.
- **R10.** `validate_currency(currency)` returns the text unchanged when it is exactly three ASCII capital letters `A` to `Z`, and otherwise raises `ValueError` with `currency must be three capital letters`. Lower case, spaces, digits, other alphabets, and full-width letters are refused.
- **R11.** `create_account` calls `validate_currency` on its `currency` argument. The default stays `USD`.
- **R12.** When a statement line is stored, whether inserted or upgrading a feed row:
  - `description` is the description with its whitespace collapsed (as now), cut to its first `DESCRIPTION_LIMIT` (500) characters, then stripped of trailing spaces, the same as the feed does;
  - `cardholder` and `external_id` are cut to their first `TEXT_LIMIT` (100) characters; `None` stays `None`.

  Fingerprints are still computed from the line as parsed, so a re-import of the same statement finds the same lines.

### Part 5: SimpleFIN answers

- **R13.** `RecursionError` joins the errors that `fetch_accounts` turns into `SyncError("aggregator answer could not be read")`. Example: a body of 100,000 `[` characters.

### Part 6: tests you write

- **R14.** `tests/integration/test_migration_chain.py`, using migrations only (never `create_all`), with the revisions read from the migrations folder through Alembic's `ScriptDirectory`, never written out by hand, so a later migration is checked without editing the test:
  - starting from an empty database, for each revision in order: upgrade to it, record the tables with their columns (name, type, nullable), unique constraints, and foreign keys, downgrade one revision, upgrade again, and assert the record is the same;
  - from head, downgrading to `base` leaves only the empty `alembic_version` table, and upgrading again to head gives a schema that `alembic.autogenerate.compare_metadata` finds equal to `finances.db.orm.Base.metadata`;
  - an account written with plain SQL at the first revision is read back unchanged through `get_account_by_name` after upgrading one revision at a time to head.
- **R15.** `tests/integration/test_log_hygiene.py`. At the default log level, with `FIN_LOG_LEVEL=INFO` set explicitly, run through Typer's `CliRunner` in order:
  1. `fin db upgrade`;
  2. `fin accounts add`;
  3. `fin import statement` of a fake-bank statement (`fake_bank`, `fake_statement_pdf`) twice;
  4. `fin transactions list`;
  5. `fin sync map`, `fin sync run` with `transport.urllib_transport` replaced by a fake that answers one account delivering the same purchase, and `fin sync status`;
  6. `fin accounts add` with a duplicate name.

  Use one synthetic merchant name, one amount, and one set of account digits throughout, and a fake access URL with a password in the keychain fixture. Assert that the merchant name does appear in the stdout of `fin transactions list`, so the test can see it, and that no run's stderr contains the merchant name, the amount as printed or as cents, the account digits, or the password.

## Given tests

Create these files exactly as shown, replacing `tests/unit/test_matching.py`, and do not change them. If one fails, the production code is wrong. Together they reach every line and branch of the production code this phase changes.

`tests/unit/test_matching.py`

```python
import random
from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from finances.domain.matching import MATCH_MAX_DAYS, MatchItem, match_one_to_one, period_zone


def item(key: int, cents: int, day: int, zone: int = 0) -> MatchItem:
    return MatchItem(key, cents, date(2026, 5, day), zone)


def test_the_default_reach_is_five_days() -> None:
    assert MATCH_MAX_DAYS == 5
    assert type(MATCH_MAX_DAYS) is int


def test_a_match_item_is_frozen_and_its_zone_defaults_to_zero() -> None:
    made = item(7, -450, 3)
    assert (made.key, made.amount_cents, made.day, made.zone) == (7, -450, date(2026, 5, 3), 0)
    assert MatchItem(7, -450, date(2026, 5, 3), 4).zone == 4
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


def test_the_most_pairs_are_made() -> None:
    left = [item(1, -450, 10), item(2, -450, 13)]
    right = [item(8, -450, 13), item(9, -450, 16)]
    assert match_one_to_one(left, right) == [(1, 8), (2, 9)]
    left = [item(1, -450, 21), item(2, -450, 26)]
    right = [item(8, -450, 24), item(9, -450, 31)]
    assert match_one_to_one(left, right) == [(1, 8), (2, 9)]


def test_among_the_most_pairs_the_fewest_days_apart_win() -> None:
    left = [item(1, -450, 10), item(2, -450, 20)]
    right = [item(8, -450, 14), item(9, -450, 12)]
    assert match_one_to_one(left, right) == [(1, 9)]
    left = [item(1, -450, 5), item(2, -450, 9)]
    right = [item(8, -450, 7), item(9, -450, 11), item(7, -450, 13)]
    assert match_one_to_one(left, right) == [(1, 8), (2, 9)]


def test_equally_good_pairings_pair_the_earlier_items() -> None:
    left = [item(1, -450, 10), item(2, -450, 13)]
    right = [item(8, -450, 13), item(9, -450, 15)]
    assert match_one_to_one(left, right) == [(1, 8), (2, 9)]


def test_ties_go_to_the_earlier_day_then_the_earlier_position() -> None:
    left = [item(1, -450, 9), item(2, -450, 11)]
    assert match_one_to_one(left, [item(9, -450, 10)]) == [(1, 9)]
    assert match_one_to_one(list(reversed(left)), [item(9, -450, 10)]) == [(1, 9)]
    right = [item(8, -450, 12), item(9, -450, 8)]
    assert match_one_to_one([item(1, -450, 10)], right) == [(1, 9)]
    assert match_one_to_one([item(1, -450, 10)], list(reversed(right))) == [(1, 9)]
    same_day = [item(1, -450, 3), item(2, -450, 3)]
    assert match_one_to_one(same_day, [item(9, -450, 3)]) == [(1, 9)]
    assert match_one_to_one(list(reversed(same_day)), [item(9, -450, 3)]) == [(2, 9)]
    later = [item(1, -450, 15), item(2, -450, 15)]
    passed_over = [item(7, -450, 1), item(8, -450, 18)]
    assert match_one_to_one(later, passed_over) == [(1, 8)]
    assert match_one_to_one(list(reversed(later)), passed_over) == [(2, 8)]


def test_a_pair_within_one_zone_beats_a_closer_pair_across_zones() -> None:
    left = [item(1, -450, 10, zone=1)]
    assert match_one_to_one(left, [item(8, -450, 9, zone=0), item(9, -450, 13, zone=1)]) == [(1, 9)]
    assert match_one_to_one(left, [item(8, -450, 7, zone=0), item(9, -450, 13, zone=1)]) == [(1, 9)]
    assert match_one_to_one(left, [item(8, -450, 9, zone=0)]) == [(1, 8)]


def test_more_pairs_beat_pairs_within_one_zone() -> None:
    left = [item(1, -450, 10, zone=1), item(2, -450, 14, zone=1)]
    right = [item(8, -450, 12, zone=1), item(9, -450, 17, zone=2)]
    assert match_one_to_one(left, right) == [(1, 8), (2, 9)]
    left = [item(1, -450, 10, zone=1), item(2, -450, 5, zone=0)]
    right = [item(8, -450, 9, zone=1), item(9, -450, 15, zone=2)]
    assert match_one_to_one(left, right) == [(1, 9), (2, 8)]


@pytest.mark.parametrize(
    ("day", "zone"),
    [(1, 0), (4, 0), (5, 1), (12, 1), (13, 2), (14, 2), (15, 3), (20, 3), (21, 4), (31, 4)],
)
def test_the_zone_of_a_day(day: int, zone: int) -> None:
    periods = [(date(2026, 5, 15), date(2026, 5, 20)), (date(2026, 5, 5), date(2026, 5, 12))]
    assert period_zone(date(2026, 5, day), periods) == zone


def test_without_periods_every_day_is_zone_zero() -> None:
    assert period_zone(date(2026, 5, 1), []) == 0


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


# Properties over generated lists. Small lists, so every pairing can be tried. Zones come
# from one statement period of a week, as the services compute them.

PERIOD = [(date(2026, 5, 8), date(2026, 5, 14))]
side = st.lists(
    st.tuples(st.sampled_from([-450, -1299]), st.integers(1, 20)), min_size=0, max_size=5
)


def items(raw: list[tuple[int, int]], first_key: int) -> list[MatchItem]:
    return [
        item(first_key + n, cents, day, period_zone(date(2026, 5, day), PERIOD))
        for n, (cents, day) in enumerate(raw)
    ]


def score(pairs: list[tuple[MatchItem, MatchItem]]) -> tuple[int, int, int]:
    """Pairs, pairs within one zone, and total days apart."""
    return (
        len(pairs),
        sum(one.zone == other.zone for one, other in pairs),
        sum(abs((one.day - other.day).days) for one, other in pairs),
    )


def best_possible(left: list[MatchItem], right: list[MatchItem]) -> tuple[int, int, int]:
    """The best score of any pairing, found by trying every pairing."""
    best = (0, 0, 0)

    def walk(position: int, used: frozenset[int], chosen: list) -> None:
        nonlocal best
        found = score(chosen)
        if (found[0], found[1], -found[2]) > (best[0], best[1], -best[2]):
            best = found
        if position == len(left):
            return
        walk(position + 1, used, chosen)
        for index, other in enumerate(right):
            gap = abs((left[position].day - other.day).days)
            if index not in used and other.amount_cents == left[position].amount_cents:
                if gap <= MATCH_MAX_DAYS:
                    walk(position + 1, used | {index}, [*chosen, (left[position], other)])

    walk(0, frozenset(), [])
    return best


def scored(pairs: list[tuple[int, int]], everything: list[MatchItem]) -> tuple[int, int, int]:
    by_key = {entry.key: entry for entry in everything}
    return score([(by_key[a], by_key[b]) for a, b in pairs])


@settings(max_examples=300)
@given(side, side)
def test_the_pairing_is_valid_and_the_best_possible(
    raw_left: list[tuple[int, int]], raw_right: list[tuple[int, int]]
) -> None:
    left, right = items(raw_left, 1), items(raw_right, 100)
    pairs = match_one_to_one(left, right)
    by_key = {entry.key: entry for entry in left + right}
    assert len({a for a, _ in pairs}) == len({b for _, b in pairs}) == len(pairs)
    for one, other in pairs:
        assert by_key[one].amount_cents == by_key[other].amount_cents
        assert abs((by_key[one].day - by_key[other].day).days) <= MATCH_MAX_DAYS
    assert [a for a, _ in pairs] == [entry.key for entry in left if entry.key in dict(pairs)]
    assert scored(pairs, left + right) == best_possible(left, right)


@settings(max_examples=200)
@given(side, side, st.randoms(use_true_random=False))
def test_the_order_of_the_lists_does_not_change_how_good_the_pairing_is(
    raw_left: list[tuple[int, int]], raw_right: list[tuple[int, int]], shuffler: random.Random
) -> None:
    left, right = items(raw_left, 1), items(raw_right, 100)
    shuffled_left, shuffled_right = list(left), list(right)
    shuffler.shuffle(shuffled_left)
    shuffler.shuffle(shuffled_right)
    expected = scored(match_one_to_one(left, right), left + right)
    assert scored(match_one_to_one(shuffled_left, shuffled_right), left + right) == expected
```

`tests/unit/test_properties_money.py`

```python
from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from finances.domain.money import format_cents, parse_money
from finances.ingest.parsers.helpers import (
    EARLY_DAYS,
    LATE_DAYS,
    infer_year,
    parse_amount,
    parse_month_day,
)
from finances.ingest.statement import StatementError

cents = st.integers(-(10**13), 10**13)
sizes = st.integers(0, 10**13)
periods = st.tuples(st.dates(date(2000, 1, 1), date(2098, 12, 1)), st.integers(20, 40))


def plain(value: int) -> str:
    return f"{value // 100}.{value % 100:02d}"


@settings(max_examples=500)
@given(cents)
def test_formatted_money_reads_back_to_the_same_cents(value: int) -> None:
    assert parse_money(format_cents(value)) == value


@settings(max_examples=300)
@given(sizes)
def test_every_negative_form_gives_the_same_cents(value: int) -> None:
    text = plain(value)
    assert parse_money(f"({text})") == -value
    assert parse_money(f"{text}-") == -value
    assert parse_money(f"-{text}") == -value
    assert parse_money(f"-${text}") == -value
    assert parse_amount(f"- ${text}") == -value
    assert parse_amount(f"+ ${text}") == value
    assert parse_amount(f"= ${text}") == value


@settings(max_examples=300)
@given(sizes)
def test_thousands_separators_change_nothing(value: int) -> None:
    dollars, rest = divmod(value, 100)
    assert parse_money(f"${dollars:,}.{rest:02d}") == value


@settings(max_examples=200)
@given(st.integers(0, 10**9), st.integers(3, 6))
def test_three_or_more_decimals_are_refused(whole: int, places: int) -> None:
    with pytest.raises(ValueError):
        parse_money(f"{whole}." + "5" * places)


@settings(max_examples=500)
@given(st.text(max_size=16))
def test_any_text_gives_cents_or_a_value_error(text: str) -> None:
    try:
        value = parse_money(text)
    except ValueError:
        return
    assert type(value) is int


@settings(max_examples=500)
@given(st.text(alphabet="0123456789.,$()-+= ", max_size=16))
def test_any_amount_text_gives_cents_or_a_value_error(text: str) -> None:
    try:
        value = parse_amount(text)
    except ValueError:
        return
    assert type(value) is int


@settings(max_examples=500)
@given(periods, st.integers(-EARLY_DAYS, 40 + LATE_DAYS))
def test_a_day_near_the_period_gets_its_own_year(period: tuple[date, int], offset: int) -> None:
    start, length = period
    end = start + timedelta(days=length)
    day = start + timedelta(days=offset)
    if day > end + timedelta(days=LATE_DAYS):
        return
    assert infer_year(day.month, day.day, start, end) == day


@settings(max_examples=300)
@given(periods, st.integers(-EARLY_DAYS, 40 + LATE_DAYS))
def test_every_printed_form_of_a_day_gives_the_same_date(
    period: tuple[date, int], offset: int
) -> None:
    start, length = period
    end = start + timedelta(days=length)
    day = start + timedelta(days=offset)
    if day > end + timedelta(days=LATE_DAYS):
        return
    for text in (day.strftime("%b %d"), day.strftime("%m/%d"), f"{day.month}-{day.day}"):
        assert parse_month_day(text, start, end) == day


@settings(max_examples=300)
@given(periods, st.integers(1, 200))
def test_a_day_too_far_from_the_period_is_refused(period: tuple[date, int], beyond: int) -> None:
    start, length = period
    end = start + timedelta(days=length)
    for day in (
        start - timedelta(days=EARLY_DAYS + beyond),
        end + timedelta(days=LATE_DAYS + beyond),
    ):
        if abs((day - start).days) > 300:
            continue
        with pytest.raises(StatementError, match="^date is outside the statement period$"):
            infer_year(day.month, day.day, start, end)
```

`tests/unit/test_properties_ingest.py`

```python
import random
from datetime import date, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from finances.domain.models import AccountType
from finances.ingest.dedup import fingerprint_lines
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementLine

START = date(2026, 3, 1)
END = date(2026, 3, 31)
SECTIONS = [Section.PURCHASES, Section.PAYMENTS_CREDITS, Section.FEES, Section.INTEREST]

lines = st.lists(
    st.builds(
        StatementLine,
        posted_date=st.integers(0, 30).map(lambda days: START + timedelta(days=days)),
        transaction_date=st.none(),
        description=st.sampled_from(["ACME COFFEE", "FOOBAR GROCERY", "acme  coffee", "PAYMENT"]),
        amount_cents=st.integers(-500_000, 500_000),
        section=st.sampled_from(SECTIONS),
        card_last4=st.sampled_from([None, "1111", "2222"]),
        external_ref=st.sampled_from([None, "REF1"]),
    ),
    max_size=12,
)
nonzero = st.integers(-1_000_000, 1_000_000).filter(lambda delta: delta != 0)


def statement(items: list[StatementLine], opening: int, closing: int, totals=None):
    return ParsedStatement(
        parser_name="probe",
        institution="Probe Bank",
        account_type=AccountType.CREDIT_CARD,
        account_last4="1111",
        period_start=START,
        period_end=END,
        opening_balance_cents=opening,
        closing_balance_cents=closing,
        lines=items,
        declared_section_totals=totals or {},
    )


def section_totals(items: list[StatementLine]) -> dict[Section, int]:
    totals: dict[Section, int] = {}
    for item in items:
        totals[item.section] = totals.get(item.section, 0) + item.amount_cents
    return totals


@settings(max_examples=300)
@given(lines, st.integers(-(10**9), 10**9))
def test_a_statement_that_adds_up_reconciles(items: list[StatementLine], opening: int) -> None:
    closing = opening + sum(item.amount_cents for item in items)
    result = reconcile(statement(items, opening, closing, section_totals(items)))
    assert result.ok
    assert (result.expected_closing_cents, result.difference_cents) == (closing, 0)
    assert result.section_mismatches == {}


@settings(max_examples=300)
@given(lines.filter(bool), st.integers(-(10**9), 10**9), nonzero, st.data())
def test_one_changed_line_is_always_caught(
    items: list[StatementLine], opening: int, delta: int, data: st.DataObject
) -> None:
    closing = opening + sum(item.amount_cents for item in items)
    totals = section_totals(items)
    index = data.draw(st.integers(0, len(items) - 1))
    changed = list(items)
    old = changed[index]
    changed[index] = StatementLine(
        old.posted_date, None, old.description, old.amount_cents + delta, old.section
    )
    result = reconcile(statement(changed, opening, closing, totals))
    assert not result.ok
    assert result.difference_cents == -delta
    assert result.section_mismatches == {
        old.section: (totals[old.section], totals[old.section] + delta)
    }


@settings(max_examples=300)
@given(lines, st.integers(-(10**9), 10**9), nonzero)
def test_a_wrong_closing_balance_is_off_by_exactly_its_error(
    items: list[StatementLine], opening: int, delta: int
) -> None:
    closing = opening + sum(item.amount_cents for item in items) + delta
    result = reconcile(statement(items, opening, closing))
    assert not result.ok
    assert result.difference_cents == delta


@settings(max_examples=300)
@given(lines, st.integers(1, 10**6))
def test_fingerprints_are_stable_and_one_per_line(
    items: list[StatementLine], account_id: int
) -> None:
    first = fingerprint_lines(account_id, items)
    assert first == fingerprint_lines(account_id, list(items))
    assert len(set(first)) == len(items)
    assert all(len(value) == 64 for value in first)
    assert set(first).isdisjoint(fingerprint_lines(account_id + 1, items))


@settings(max_examples=300)
@given(lines, st.randoms(use_true_random=False))
def test_the_same_lines_in_another_order_give_the_same_fingerprints(
    items: list[StatementLine], shuffler: random.Random
) -> None:
    shuffled = list(items)
    shuffler.shuffle(shuffled)
    assert set(fingerprint_lines(7, shuffled)) == set(fingerprint_lines(7, items))


@settings(max_examples=100)
@given(st.integers(1, 30))
def test_identical_lines_each_get_their_own_fingerprint(count: int) -> None:
    line = StatementLine(START, None, "ACME COFFEE", -450, Section.PURCHASES)
    assert len(set(fingerprint_lines(7, [line] * count))) == count


@settings(max_examples=200)
@given(lines)
def test_spacing_and_case_of_a_description_do_not_change_its_fingerprint(
    items: list[StatementLine],
) -> None:
    varied = [
        StatementLine(
            item.posted_date,
            item.transaction_date,
            "  " + item.description.lower().replace(" ", "   ") + " ",
            item.amount_cents,
            item.section,
            item.card_last4,
            item.cardholder,
            item.external_ref,
        )
        for item in items
    ]
    assert fingerprint_lines(7, varied) == fingerprint_lines(7, items)
```

`tests/unit/test_parser_fuzz.py`

```python
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from finances.ingest.parsers import detect_parser, registered_parsers
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, StatementError

FIXTURES = Path(__file__).parents[1] / "fixtures" / "statements"
PATHS = sorted(FIXTURES.glob("*/*.txt"))
ODD = [
    " ",
    "−",
    "１",
    "٣",
    "\t",
    "  ",
    "$",
    "-",
    "(",
    ")",
    ",",
    ".",
    "0",
    "9",
    "/",
    "​",
    "é",
    "\x00",
    "+",
    "=",
]


def pages_of(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").split("\f")


def amounts(parsed: ParsedStatement) -> list[tuple[int, str]]:
    return sorted((item.amount_cents, item.section.value) for item in parsed.lines)


def read(pages: list[str]) -> ParsedStatement | None:
    """Parse as an import does. A StatementError means the statement is refused."""
    try:
        return detect_parser(pages).parse(pages)
    except StatementError:
        return None


@st.composite
def damaged(draw: st.DrawFn) -> list[str]:
    pages = [page.split("\n") for page in pages_of(draw(st.sampled_from(PATHS)))]
    for _ in range(draw(st.integers(1, 3))):
        page = draw(st.integers(0, len(pages) - 1))
        lines = pages[page]
        if not lines:
            continue
        index = draw(st.integers(0, len(lines) - 1))
        line = lines[index]
        change = draw(
            st.sampled_from(["drop", "repeat", "swap", "cut", "replace", "insert", "page", "blank"])
        )
        if change == "drop":
            del lines[index]
        elif change == "repeat":
            lines.insert(index, line)
        elif change == "swap":
            other = draw(st.integers(0, len(lines) - 1))
            lines[index], lines[other] = lines[other], lines[index]
        elif change == "cut":
            lines[index] = line[: draw(st.integers(0, len(line)))]
        elif change == "replace" and line:
            at = draw(st.integers(0, len(line) - 1))
            lines[index] = line[:at] + draw(st.sampled_from(ODD)) + line[at + 1 :]
        elif change == "insert":
            at = draw(st.integers(0, len(line)))
            lines[index] = line[:at] + draw(st.sampled_from(ODD)) + line[at:]
        elif change == "page":
            pages.insert(page, [])
        elif change == "blank":
            lines[index] = ""
    return ["\n".join(lines) for lines in pages]


def test_there_is_a_fixture_for_every_parser() -> None:
    names = {parser.name for parser in registered_parsers()}
    found = set()
    for path in PATHS:
        parsed = read(pages_of(path))
        if parsed is not None:
            found.add(parsed.parser_name)
    assert found == names


@settings(max_examples=400)
@given(damaged())
def test_a_damaged_statement_is_read_or_refused_with_a_statement_error(pages: list[str]) -> None:
    for parser in registered_parsers():
        try:
            parsed = parser.parse(pages)
        except StatementError:
            continue
        assert all(type(item.amount_cents) is int for item in parsed.lines)
        assert type(parsed.opening_balance_cents) is int
        assert type(parsed.closing_balance_cents) is int


@pytest.mark.parametrize("path", PATHS, ids=lambda path: f"{path.parent.name}/{path.stem}")
def test_one_edit_never_changes_the_amounts_of_a_statement_that_still_reconciles(
    path: Path,
) -> None:
    pages = pages_of(path)
    original = read(pages)
    if original is None or not reconcile(original).ok:
        return
    expected = amounts(original)
    for page_index, page in enumerate(pages):
        lines = page.split("\n")
        for index, line in enumerate(lines):
            edits = [lines[:index] + lines[index + 1 :]]
            for at, char in enumerate(line):
                if char.isdigit():
                    edited = line[:at] + str((int(char) + 3) % 10) + line[at + 1 :]
                    edits.append(lines[:index] + [edited] + lines[index + 1 :])
            for edit in edits:
                changed = list(pages)
                changed[page_index] = "\n".join(edit)
                parsed = read(changed)
                if parsed is not None and reconcile(parsed).ok:
                    assert amounts(parsed) == expected, (page_index, index)
```

`tests/unit/test_simplefin_fuzz.py`

```python
import json
from datetime import date
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from finances.sync.simplefin import ProviderAnswer, SyncError, fetch_accounts

ACCESS = "https://probe-user:probe-pass@bridge.simplefin.org/simplefin"
FIXTURES = sorted((Path(__file__).parents[1] / "fixtures" / "simplefin").glob("*.json"))
UNREADABLE = "aggregator answer could not be read"

leaf = (
    st.none()
    | st.booleans()
    | st.integers(-(2**70), 2**70)
    | st.floats(allow_nan=True, allow_infinity=True)
    | st.text(max_size=8)
)
documents = st.recursive(
    leaf,
    lambda inner: (
        st.lists(inner, max_size=3) | st.dictionaries(st.text(max_size=6), inner, max_size=3)
    ),
    max_leaves=12,
)


def answer(body: bytes) -> ProviderAnswer:
    return fetch_accounts(ACCESS, date(2026, 5, 1), date(2026, 5, 31), lambda *_: (200, body))


def read_or_refuse(body: bytes) -> None:
    try:
        result = answer(body)
    except SyncError as error:
        assert str(error) == UNREADABLE
        return
    for account in result.accounts:
        assert type(account.balance_cents) is int
        assert all(type(item.amount_cents) is int for item in account.transactions)
        assert all(type(item.feed_id) is str for item in account.transactions)
    assert all(type(message) is str for message in result.messages)


@st.composite
def damaged(draw: st.DrawFn) -> object:
    document = json.loads(draw(st.sampled_from(FIXTURES)).read_text(encoding="utf-8"))
    for _ in range(draw(st.integers(1, 3))):
        node = document
        for _ in range(draw(st.integers(0, 4))):
            if isinstance(node, dict) and node:
                node = node[draw(st.sampled_from(sorted(node)))]
            elif isinstance(node, list) and node:
                node = node[draw(st.integers(0, len(node) - 1))]
            else:
                break
        if isinstance(node, dict) and node:
            key = draw(st.sampled_from(sorted(node)))
            if draw(st.booleans()):
                del node[key]
            else:
                node[key] = draw(leaf)
        elif isinstance(node, list) and node:
            index = draw(st.integers(0, len(node) - 1))
            if draw(st.booleans()):
                del node[index]
            else:
                node[index] = draw(leaf)
    return document


def test_the_fixtures_are_read() -> None:
    for path in FIXTURES:
        assert answer(path.read_bytes()).accounts


@settings(max_examples=400)
@given(documents)
def test_any_json_is_read_or_refused_as_unreadable(document: object) -> None:
    read_or_refuse(json.dumps(document).encode())


@settings(max_examples=400)
@given(damaged())
def test_a_damaged_answer_is_read_or_refused_as_unreadable(document: object) -> None:
    read_or_refuse(json.dumps(document).encode())


@pytest.mark.parametrize(
    "body",
    [
        b"[" * 100_000,
        b'{"accounts": ' + b"[" * 100_000 + b"]" * 100_000 + b"}",
        b"{" * 5_000,
        b"",
        b"\xff\xfe",
        b"null",
        b"1e999999",
        b'{"accounts": [], "errlist": [{"msg": ' + b"[" * 100_000 + b"]}]}",
    ],
    ids=[
        "deep-list",
        "deep-accounts",
        "open-braces",
        "empty",
        "not-utf8",
        "null",
        "huge",
        "deep-msg",
    ],
)
def test_answers_no_parser_can_use_are_unreadable(body: bytes) -> None:
    with pytest.raises(SyncError, match=f"^{UNREADABLE}$"):
        answer(body)
```

`tests/integration/test_ledger_properties.py`

```python
"""Statements and feed pulls arriving in any realistic order store each transaction once.

The household's transactions are generated, then shown to the app two ways: on statements
(each imported a few days after its period ends) and in feed pulls (each delivering the last 30
days). A feed may date a transaction the same day as the statement or up to three days later.
"""

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import select

import finances.ingest.service as ingest
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from finances.ingest.service import ImportStatus, import_statement
from finances.sync.feed import AccountFeed, FeedTransaction
from finances.sync.service import apply_feed

FIRST_DAY = date(2026, 1, 1)
PERIODS = {
    "jan": (date(2026, 1, 1), date(2026, 1, 31)),
    "feb": (date(2026, 2, 1), date(2026, 2, 28)),
}
WINDOW_DAYS = 30
STATEMENT_DELAY_DAYS = 2


@dataclass(frozen=True)
class Spending:
    number: int
    day: date
    amount_cents: int
    feed_day: date


def spending(raw: list[tuple[int, int, int]]) -> list[Spending]:
    return [
        Spending(
            number,
            FIRST_DAY + timedelta(days=offset),
            cents,
            FIRST_DAY + timedelta(days=offset + lag),
        )
        for number, (offset, cents, lag) in enumerate(raw)
    ]


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def statement_text(name: str, everything: list[Spending]) -> bytes:
    start, end = PERIODS[name]
    printed = [item for item in everything if start <= item.day <= end]
    total = sum(item.amount_cents for item in printed)
    lines = [
        "FAKEBANK STATEMENT",
        "ACCOUNT 1111 credit_card",
        f"PERIOD {start} {end}",
        "OPENING 0.00",
        f"CLOSING {money(total)}",
        *(
            f"ROW {item.day}|-|purchases|{money(item.amount_cents)}|-|-|PROBE {item.number}"
            for item in printed
        ),
    ]
    return "\n".join(lines).encode()


@pytest.fixture
def statements_as_text(fake_bank, monkeypatch: pytest.MonkeyPatch) -> None:
    """Statements are plain text here, read by the fake bank parser."""
    monkeypatch.setattr(ingest, "extract_pages", lambda content: [content.decode()])


def pull(engine, account_id: int, everything: list[Spending], today: date, order: str) -> set[int]:
    """Apply the last 30 days of the feed in the order given. Return the numbers delivered."""
    delivered = [
        item for item in everything if today - timedelta(days=WINDOW_DAYS) <= item.feed_day <= today
    ]
    delivered.sort(key=lambda item: (item.feed_day, item.number))
    if order == "newest first":
        delivered.reverse()
    feed = AccountFeed(
        [
            FeedTransaction(f"F{item.number}", item.feed_day, item.amount_cents, "PROBE")
            for item in delivered
        ]
    )
    with session_scope(engine) as session:
        apply_feed(session, account_id, feed)
    return {item.number for item in delivered}


Step = tuple[int, str | None, str | None]


def live(
    folder: Path, everything: list[Spending], steps: list[Step]
) -> tuple[Counter, Counter, dict[str, Counter]]:
    """Run the steps on a new database. Return what is stored, what should be, and per period.

    Each step moves time forward, pulls the feed in the order named (as the daily job does; no
    pull when the order is None), and then imports the statement named, if any, once its period
    ended more than two days before.
    """
    url = f"sqlite:///{(folder / f'{uuid.uuid4().hex}.db').as_posix()}"
    upgrade_to_head(url)
    engine = get_engine(url)
    with session_scope(engine) as session:
        account_id = create_account(
            session, "Probe Card", "Fake Bank", "credit_card", last4="1111"
        ).id
    imported: set[str] = set()
    seen: set[int] = set()
    today = FIRST_DAY
    for days, order, statement in steps:
        today += timedelta(days=days)
        if order is not None:
            seen |= pull(engine, account_id, everything, today, order)
        if statement is None:
            continue
        start, end = PERIODS[statement]
        if today <= end + timedelta(days=STATEMENT_DELAY_DAYS):
            continue
        with session_scope(engine) as session:
            result = import_statement(
                session, filename=f"{statement}.pdf", content=statement_text(statement, everything)
            )
        assert result.status in (ImportStatus.IMPORTED, ImportStatus.ALREADY_IMPORTED)
        imported.add(statement)
        seen |= {item.number for item in everything if start <= item.day <= end}
    with session_scope(engine) as session:
        rows = session.execute(
            select(TransactionRow.posted_date, TransactionRow.amount_cents)
        ).all()
    engine.dispose()

    def covered(day: date) -> bool:
        return any(PERIODS[name][0] <= day <= PERIODS[name][1] for name in imported)

    stored = Counter(cents for _, cents in rows)
    expected = Counter(
        item.amount_cents
        for item in everything
        if item.number in seen and (covered(item.day) or not covered(item.feed_day))
    )
    periods = {}
    for name in imported:
        start, end = PERIODS[name]
        periods[name] = Counter(
            (day, cents) for day, cents in rows if start <= day <= end
        ) - Counter(
            (item.day, item.amount_cents) for item in everything if start <= item.day <= end
        )
    return stored, expected, periods


def assert_each_stored_once(folder: Path, raw, steps) -> None:
    stored, expected, periods = live(folder, spending(raw), steps)
    assert stored == expected
    assert all(not extra for extra in periods.values())


transactions = st.lists(
    st.tuples(
        st.integers(0, 58),
        st.sampled_from([-450, -450, -450, -1299, 2500]),
        st.sampled_from([0, 0, 1, 2, 3]),
    ),
    min_size=1,
    max_size=12,
)
steps = st.lists(
    st.tuples(
        st.integers(1, 20),
        st.sampled_from(["newest first", "oldest first"]),
        st.sampled_from([None, None, "jan", "feb"]),
    ),
    min_size=1,
    max_size=10,
)


@settings(max_examples=150)
@given(transactions, steps)
def test_any_order_of_statements_and_pulls_stores_each_transaction_once(
    statements_as_text: None, tmp_path: Path, raw, order
) -> None:
    assert_each_stored_once(tmp_path, raw, order)


def test_the_order_a_pull_lists_its_transactions_in_changes_nothing(
    statements_as_text: None, tmp_path: Path
) -> None:
    raw = [(28, -450, 0), (31, -450, 0)]
    for order in ("newest first", "oldest first"):
        stored, expected, _ = live(tmp_path, spending(raw), [(33, None, "jan"), (1, order, None)])
        assert stored == expected == Counter({-450: 2})


def test_a_tie_at_import_does_not_push_a_later_transaction_out(
    statements_as_text: None, tmp_path: Path
) -> None:
    raw = [(0, -450, 0)] * 3 + [(15, -450, 3), (23, -450, 0), (28, -450, 3), (9, -450, 3)]
    order = [
        (1, "newest first", None),
        (12, "newest first", None),
        (20, None, "jan"),
        (1, "oldest first", None),
    ]
    assert_each_stored_once(tmp_path, raw, order)


def test_a_statement_pairs_as_many_feed_rows_as_it_can(
    statements_as_text: None, tmp_path: Path
) -> None:
    raw = [(51, -450, 3), (56, -450, 3)]
    assert_each_stored_once(tmp_path, raw, [(59, "newest first", None), (2, "newest first", "feb")])


def test_a_tie_across_a_period_edge_goes_to_the_transaction_inside_the_period(
    statements_as_text: None, tmp_path: Path
) -> None:
    raw = [(25, -450, 3), (31, -450, 3)]
    assert_each_stored_once(
        tmp_path, raw, [(41, "newest first", None), (20, "newest first", "feb")]
    )


def test_a_pull_pairs_only_the_transactions_that_settle_in_it(
    statements_as_text: None, tmp_path: Path
) -> None:
    raw = [(26, -450, 0), (28, -450, 3)]
    order = [(27, "newest first", None), (6, None, "jan"), (1, "newest first", None)]
    assert_each_stored_once(tmp_path, raw, order)


def test_a_pull_breaks_a_tie_across_a_period_edge_in_favour_of_the_period(
    statements_as_text: None, tmp_path: Path
) -> None:
    everything = spending([(29, -450, 0), (32, -450, 3)])
    url = f"sqlite:///{(tmp_path / 'edge.db').as_posix()}"
    upgrade_to_head(url)
    engine = get_engine(url)
    with session_scope(engine) as session:
        account_id = create_account(
            session, "Probe Card", "Fake Bank", "credit_card", last4="1111"
        ).id
        import_statement(session, filename="feb.pdf", content=statement_text("feb", everything))
    for order in ("newest first", "oldest first"):
        pull(engine, account_id, everything, date(2026, 2, 10), order)
    with session_scope(engine) as session:
        rows = session.execute(
            select(TransactionRow.posted_date, TransactionRow.source).order_by(
                TransactionRow.posted_date
            )
        ).all()
    engine.dispose()
    assert rows == [(date(2026, 1, 30), "aggregator"), (date(2026, 2, 2), "statement")]
```

`tests/integration/test_text_limits.py`

```python
"""Every text the app stores fits its column, however long the text it is given."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import Engine, String, func, select
from typer.testing import CliRunner

import finances.ingest.service as ingest
from finances.cli.main import app as cli
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import Base, TransactionRow
from finances.db.repositories import create_account
from finances.domain.models import AccountType
from finances.ingest.parsers import register
from finances.ingest.service import ImportStatus, import_statement
from finances.ingest.statement import ParsedStatement, Section, StatementLine
from finances.sync.feed import AccountFeed, FeedTransaction
from finances.sync.service import apply_feed
from finances.web.app import create_app

runner = CliRunner(env={"COLUMNS": "200"})
NAME_TOO_LONG = "account name must be at most 100 characters"
INSTITUTION_TOO_LONG = "institution must be at most 100 characters"
BAD_CURRENCY = "currency must be three capital letters"


def too_long(session) -> list[str]:
    """Each text column holding a value longer than the column allows."""
    found = []
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if isinstance(column.type, String) and column.type.length:
                longest = session.scalar(select(func.max(func.length(column))))
                if longest is not None and longest > column.type.length:
                    found.append(f"{table.name}.{column.name}")
    return found


# Accounts


@pytest.mark.parametrize(
    ("name", "institution"),
    [("N" * 100, "Probe Bank"), ("Probe", "I" * 100), ("  " + "N" * 100 + "  ", "Probe Bank")],
    ids=["name", "institution", "outer-spaces"],
)
def test_names_up_to_one_hundred_characters_are_kept(
    db_engine: Engine, name: str, institution: str
) -> None:
    with session_scope(db_engine) as session:
        made = create_account(session, name, institution, "other")
    assert (made.name, made.institution) == (name.strip(), institution)


@pytest.mark.parametrize(
    ("name", "institution", "message"),
    [
        ("N" * 101, "Probe Bank", NAME_TOO_LONG),
        ("Probe", "I" * 101, INSTITUTION_TOO_LONG),
        ("N" * 5000, "I" * 5000, NAME_TOO_LONG),
    ],
    ids=["name", "institution", "both"],
)
def test_longer_names_are_refused(
    db_engine: Engine, name: str, institution: str, message: str
) -> None:
    with session_scope(db_engine) as session, pytest.raises(ValueError, match=f"^{message}$"):
        create_account(session, name, institution, "other")


@pytest.mark.parametrize("currency", ["USD", "EUR", "CAD"])
def test_three_capital_letters_are_a_currency(db_engine: Engine, currency: str) -> None:
    with session_scope(db_engine) as session:
        assert (
            create_account(session, "Probe", "Probe Bank", "other", currency).currency == currency
        )


@pytest.mark.parametrize(
    "currency", ["usd", "Usd", "US", "USDX", "", " USD", "U$D", "U1D", "ＵＳＤ", "ÜSD"]
)
def test_anything_else_is_not_a_currency(db_engine: Engine, currency: str) -> None:
    with session_scope(db_engine) as session, pytest.raises(ValueError, match=f"^{BAD_CURRENCY}$"):
        create_account(session, "Probe", "Probe Bank", "other", currency)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--name", "N" * 101], NAME_TOO_LONG),
        (["--name", "Probe", "--institution", "I" * 101], INSTITUTION_TOO_LONG),
        (["--name", "Probe", "--currency", "usd"], BAD_CURRENCY),
    ],
    ids=["name", "institution", "currency"],
)
def test_the_command_reports_each_refusal(
    tmp_settings: Settings, args: list[str], message: str
) -> None:
    upgrade_to_head()
    defaults = ["--institution", "Probe Bank", "--type", "other"]
    result = runner.invoke(cli, ["accounts", "add", *defaults, *args])
    assert (result.exit_code, result.stdout, result.stderr) == (1, "", f"Error: {message}\n")
    assert isinstance(result.exception, SystemExit)


def test_the_web_form_reports_a_long_name(tmp_settings: Settings) -> None:
    upgrade_to_head()
    client = TestClient(create_app(8765), base_url="http://127.0.0.1:8765")
    client.get("/accounts")
    fields = {"name": "N" * 101, "institution": "Probe Bank", "type": "other"}
    response = client.post("/accounts/add", data={"csrf": client.cookies["fin_csrf"], **fields})
    assert response.status_code == 400
    assert f'<p class="error">{NAME_TOO_LONG}</p>' in response.text


# Statements


class LongTextParser:
    """A parser whose one line has a description, cardholder, and reference longer than allowed."""

    name = "long_text"

    def __init__(self, description: str, cardholder: str, reference: str) -> None:
        self.line = StatementLine(
            date(2026, 4, 10),
            None,
            description,
            -450,
            Section.PURCHASES,
            "2222",
            cardholder,
            reference,
        )

    def detect(self, first_page: str) -> bool:
        return first_page == "LONG TEXT"

    def parse(self, pages: list[str]) -> ParsedStatement:
        return ParsedStatement(
            parser_name=self.name,
            institution="Probe Bank",
            account_type=AccountType.CREDIT_CARD,
            account_last4="1111",
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            opening_balance_cents=0,
            closing_balance_cents=-450,
            lines=[self.line],
        )


@pytest.fixture
def long_text(parser_registry: None, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ingest, "extract_pages", lambda content: [content.decode()])

    def use(description: str, cardholder: str, reference: str) -> None:
        register(LongTextParser(description, cardholder, reference))

    return use


def stored_line(engine: Engine) -> tuple[str, str, str, str]:
    with session_scope(engine) as session:
        row = session.scalars(select(TransactionRow)).one()
        assert too_long(session) == []
        return row.description, row.cardholder, row.external_id, row.source


@pytest.mark.parametrize("feed_first", [False, True])
def test_long_statement_text_is_cut_to_fit(db_engine: Engine, long_text, feed_first: bool) -> None:
    words = " ".join(f"WORD{n:03d}" for n in range(100))
    long_text(f"  ACM   {words}  ", "SAM " + "Q" * 200, "R" * 300)
    with session_scope(db_engine) as session:
        account = create_account(session, "Probe Card", "Probe Bank", "credit_card", last4="1111")
        if feed_first:
            apply_feed(
                session,
                account.id,
                AccountFeed([FeedTransaction("F1", date(2026, 4, 11), -450, "ACME")]),
            )
    with session_scope(db_engine) as session:
        result = import_statement(session, filename="april.pdf", content=b"LONG TEXT")
    assert result.status == ImportStatus.IMPORTED
    description, cardholder, reference, source = stored_line(db_engine)
    expected = f"ACM {words}"[:500].rstrip()
    assert (description, cardholder, reference, source) == (
        expected,
        ("SAM " + "Q" * 200)[:100],
        "R" * 100,
        "statement",
    )
    assert len(description) == 499


def test_statement_text_that_fits_is_kept_whole(db_engine: Engine, long_text) -> None:
    long_text("D" * 500, "C" * 100, "R" * 100)
    with session_scope(db_engine) as session:
        create_account(session, "Probe Card", "Probe Bank", "credit_card", last4="1111")
    with session_scope(db_engine) as session:
        import_statement(session, filename="april.pdf", content=b"LONG TEXT")
    assert stored_line(db_engine)[:3] == ("D" * 500, "C" * 100, "R" * 100)


# Web forms


FORMS = {
    "/accounts/add": ["name", "institution", "type", "last4"],
    "/accounts/owner": ["account", "owner"],
    "/people/add": ["name"],
    "/people/alias": ["person", "cardholder"],
    "/sync/unlink": ["link"],
    "/sync/map": ["link", "feed_account", "account"],
    "/sync/create": ["link", "feed_account", "account", "institution", "type", "last4"],
}
field = st.one_of(
    st.text(max_size=12),
    st.text(min_size=95, max_size=300),
    st.sampled_from(
        ["Probe", "Kim", "joint", "other", "credit_card", "1234", "", "kim", "ACT-1", "\x00", "on"]
    ),
)


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory):
    folder = tmp_path_factory.mktemp("site")
    patch = pytest.MonkeyPatch()
    patch.setenv("FIN_DATA_DIR", str(folder))
    from finances.config import get_settings

    get_settings.cache_clear()
    upgrade_to_head()
    client = TestClient(
        create_app(8765), base_url="http://127.0.0.1:8765", raise_server_exceptions=False
    )
    client.get("/accounts")
    yield client
    patch.undo()
    get_settings.cache_clear()


@settings(max_examples=300)
@given(st.sampled_from(sorted(FORMS)), st.data())
def test_no_form_input_breaks_the_site_or_overfills_a_column(site, path: str, data) -> None:
    fields = {name: data.draw(field, label=name) for name in FORMS[path]}
    response = site.post(
        path, data={"csrf": site.cookies["fin_csrf"], **fields}, follow_redirects=False
    )
    assert response.status_code in (303, 400)
    engine = get_engine()
    with session_scope(engine) as session:
        assert too_long(session) == []
    engine.dispose()
```

## Rules for this phase

- **Money stays in integer cents.** No `float` in any changed module.
- **`domain` imports nothing from the project.** `period_zone` and the matcher are pure.
- **Messages carry no data.** The three new messages are constant; nothing echoes a name, an amount, or a description.
- **Tests are synthetic and deterministic.** No real data, no network, no seed of their own (R2).
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.
- Do not run `fin` against the real database in `data/`, and do not run `fin sync` against SimpleFIN.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, no warnings summary, at least N + 98 passed (the given files add 127 tests and replace 29), and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_matching.py tests/unit/test_properties_money.py tests/unit/test_properties_ingest.py tests/unit/test_parser_fuzz.py tests/unit/test_simplefin_fuzz.py tests/integration/test_ledger_properties.py tests/integration/test_text_limits.py --no-cov` | exactly `127 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| each of the four searches below | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain --cov=finances.ingest --cov=finances.sync --cov=finances.db --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances ':!src/finances/sync' ':!src/finances/config.py'`

`git grep -n --untracked -E "float" -- src/finances/domain src/finances/ingest src/finances/sync src/finances/db`

`git grep -n --untracked -E "derandomize=False|database=|use_true_random=True|@seed|HYPOTHESIS" -- tests ':!tests/conftest.py'`

`git grep -n --untracked -E "(^|[^_a-zA-Z.])print\(|logging" -- src/finances/domain src/finances/ingest/service.py src/finances/sync/service.py src/finances/sync/simplefin.py src/finances/db/repositories.py`

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 9: test hardening, and the bugs it found (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count, and list the five fixes. Under "Deviations", list your design choices (how you computed R5, any helpers) and anything you did that the spec did not ask for, or `None`. Under "Follow-ups", copy the three known limits from the Goal.

In your final message, give the output line of each acceptance command, and for each of R1 to R15 the name of a test that covers it.
