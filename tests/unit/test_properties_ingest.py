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
