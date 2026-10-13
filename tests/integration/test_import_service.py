import hashlib
from collections.abc import Callable
from datetime import date
from pathlib import Path

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import BalanceSnapshotRow, StatementRow, TransactionRow
from finances.db.repositories import (
    create_account,
    find_statement_by_hash,
    latest_balance,
    list_statements,
    list_transactions,
)
from finances.domain.models import DataSource
from finances.ingest.dedup import fingerprint_lines
from finances.ingest.service import (
    ImportStatus,
    StatementImportResult,
    import_folder,
    import_statement,
)
from finances.ingest.statement import Section, StatementLine

PERIOD_START = date(2026, 1, 1)
PERIOD_END = date(2026, 1, 31)
LINES = [
    StatementLine(
        date(2026, 1, 5), date(2026, 1, 4), "ACME COFFEE #12", -450, Section.PURCHASES, "2222"
    ),
    StatementLine(
        date(2026, 1, 6), None, "FOOBAR   GROCERY", -2599, Section.PURCHASES, "2222", None, "7838"
    ),
    StatementLine(
        date(2026, 1, 5), date(2026, 1, 4), "ACME COFFEE #12", -450, Section.PURCHASES, "2222"
    ),
    StatementLine(date(2026, 1, 20), None, "PAYMENT THANK YOU", 5000, Section.PAYMENTS_CREDITS),
]
HINT = (
    'no account ends in 1111; add one with: fin accounts add --name "NAME" '
    '--institution "Fake Bank" --type credit_card --last4 1111'
)
OVERLAP = (
    "2026-01-05|2026-01-04|purchases|-4.50|2222|-|ACME COFFEE #12",
    "2026-01-06|-|purchases|-25.99|2222|7838|FOOBAR   GROCERY",
    "2026-02-08|-|purchases|-10.00|-|-|ACME BOOKS",
)


def test_import_stores_the_statement_both_copies_of_a_line_and_the_balance(
    db_engine: Engine, fake_bank: object, fake_statement_pdf: Callable[..., bytes]
) -> None:
    content = fake_statement_pdf()
    with session_scope(db_engine) as session:
        create_account(session, "Household Card", "Fake Bank", "credit_card", last4="1111")
    with session_scope(db_engine) as session:
        result = import_statement(session, filename="jan.pdf", content=content)
    assert result == StatementImportResult(
        "jan.pdf",
        ImportStatus.IMPORTED,
        "imported",
        "fake_bank",
        "Household Card",
        PERIOD_START,
        PERIOD_END,
        4,
        4,
        0,
    )
    with session_scope(db_engine) as session:
        stored = find_statement_by_hash(session, hashlib.sha256(content).hexdigest())
        assert stored is not None
        assert (stored.account_id, stored.source_filename, stored.parser_name) == (
            1,
            "jan.pdf",
            "fake_bank",
        )
        assert (stored.period_start, stored.period_end) == (PERIOD_START, PERIOD_END)
        assert (
            stored.opening_balance_cents,
            stored.closing_balance_cents,
            stored.lines_parsed,
            stored.rows_inserted,
            stored.rows_duplicate,
        ) == (-10000, -8499, 4, 4, 0)
        rows = sorted(list_transactions(session, account_id=1), key=lambda item: item.id)
        assert [item.amount_cents for item in rows] == [-450, -2599, -450, 5000]
        assert [item.fingerprint for item in rows] == fingerprint_lines(1, LINES)
        assert rows[0].fingerprint != rows[2].fingerprint
        assert rows[1].description == "FOOBAR GROCERY"
        assert (rows[1].card_last4, rows[1].external_id, rows[1].section) == (
            "2222",
            "7838",
            "purchases",
        )
        assert rows[3].section == "payments_credits"
        assert (rows[0].posted_date, rows[0].transaction_date, rows[1].transaction_date) == (
            date(2026, 1, 5),
            date(2026, 1, 4),
            None,
        )
        assert all(
            (item.source, item.is_pending, item.statement_id)
            == (DataSource.STATEMENT, False, stored.id)
            for item in rows
        )
        balance = latest_balance(session, 1)
        assert balance is not None
        assert (balance.as_of_date, balance.balance_cents, balance.source) == (
            PERIOD_END,
            -8499,
            DataSource.STATEMENT,
        )


def test_the_same_bytes_are_already_imported_including_a_dry_run(
    db_engine: Engine, fake_bank: object, fake_statement_pdf: Callable[..., bytes]
) -> None:
    content = fake_statement_pdf()
    _card(db_engine)
    with session_scope(db_engine) as session:
        import_statement(session, filename="jan.pdf", content=content)
    with session_scope(db_engine) as session:
        again = import_statement(session, filename="inbox/jan.pdf", content=content)
        dry = import_statement(session, filename="copy.pdf", content=content, dry_run=True)
    assert again == StatementImportResult(
        "jan.pdf", ImportStatus.ALREADY_IMPORTED, "already imported"
    )
    assert dry == StatementImportResult(
        "copy.pdf", ImportStatus.ALREADY_IMPORTED, "already imported"
    )
    assert _counts(db_engine) == (1, 4, 1)


def test_a_later_statement_inserts_only_the_new_line(
    db_engine: Engine, fake_bank: object, fake_statement_pdf: Callable[..., bytes]
) -> None:
    _card(db_engine)
    with session_scope(db_engine) as session:
        import_statement(session, filename="jan.pdf", content=fake_statement_pdf())
        preview = import_statement(
            session,
            filename="feb.pdf",
            content=_overlap_pdf(fake_statement_pdf),
            dry_run=True,
        )
    assert (preview.status, preview.inserted, preview.duplicates, preview.lines_parsed) == (
        ImportStatus.DRY_RUN,
        1,
        2,
        3,
    )
    assert _counts(db_engine) == (1, 4, 1)
    with session_scope(db_engine) as session:
        overlap = import_statement(
            session, filename="feb.pdf", content=_overlap_pdf(fake_statement_pdf)
        )
    assert overlap == StatementImportResult(
        "feb.pdf",
        ImportStatus.IMPORTED,
        "imported",
        "fake_bank",
        "Household Card",
        date(2026, 2, 1),
        date(2026, 2, 28),
        3,
        1,
        2,
    )
    assert _counts(db_engine) == (2, 5, 2)
    with session_scope(db_engine) as session:
        latest = list_statements(session, account_id=1)[0]
        assert (
            latest.period_end,
            latest.lines_parsed,
            latest.rows_inserted,
            latest.rows_duplicate,
        ) == (
            date(2026, 2, 28),
            3,
            1,
            2,
        )


def test_duplicate_lines_are_still_recorded_on_a_new_file(
    db_engine: Engine, fake_bank: object, fake_statement_pdf: Callable[..., bytes]
) -> None:
    _card(db_engine)
    with session_scope(db_engine) as session:
        import_statement(session, filename="jan.pdf", content=fake_statement_pdf())
        again = import_statement(
            session,
            filename="jan-again.pdf",
            content=fake_statement_pdf(totals=("purchases -34.99", "payments_credits 50.00")),
        )
    assert (again.status, again.lines_parsed, again.inserted, again.duplicates) == (
        ImportStatus.IMPORTED,
        4,
        0,
        4,
    )
    assert _counts(db_engine) == (2, 4, 1)
    with session_scope(db_engine) as session:
        stored = list_statements(session)[0]
        assert (stored.rows_inserted, stored.rows_duplicate, stored.source_filename) == (
            0,
            4,
            "jan-again.pdf",
        )


def test_dry_run_on_an_empty_database_writes_nothing(
    db_engine: Engine, fake_bank: object, fake_statement_pdf: Callable[..., bytes]
) -> None:
    _card(db_engine)
    with session_scope(db_engine) as session:
        result = import_statement(
            session, filename="jan.pdf", content=fake_statement_pdf(), dry_run=True
        )
    assert result == StatementImportResult(
        "jan.pdf",
        ImportStatus.DRY_RUN,
        "dry run: nothing written",
        "fake_bank",
        "Household Card",
        PERIOD_START,
        PERIOD_END,
        4,
        4,
        0,
    )
    assert _counts(db_engine) == (0, 0, 0)


def test_unreadable_unrecognized_and_malformed_pdfs_fail_without_writing(
    db_engine: Engine,
    fake_bank: object,
    fake_statement_pdf: Callable[..., bytes],
    make_pdf: Callable[[list[list[str]]], bytes],
) -> None:
    _card(db_engine)
    cases = [
        (b"not a pdf", "could not read PDF"),
        (make_pdf([["OTHER BANK STATEMENT"]]), "unrecognized statement format"),
        (make_pdf([["FAKEBANK STATEMENT", "ACCOUNT"]]), "fake statement is malformed"),
    ]
    with session_scope(db_engine) as session:
        for content, message in cases:
            found = import_statement(session, filename="bad.pdf", content=content)
            assert found == StatementImportResult("bad.pdf", ImportStatus.FAILED, message)
    assert _counts(db_engine) == (0, 0, 0)


def test_a_missing_or_different_named_account_fails_without_writing(
    db_engine: Engine, fake_bank: object, fake_statement_pdf: Callable[..., bytes]
) -> None:
    content = fake_statement_pdf()
    with session_scope(db_engine) as session:
        create_account(session, "Other Card", "Fake Bank", "credit_card", last4="9999")
        missing = import_statement(
            session, filename="jan.pdf", content=content, account_name="Nobody"
        )
        mismatch = import_statement(
            session, filename="jan.pdf", content=content, account_name="Other Card"
        )
    assert missing == StatementImportResult(
        "jan.pdf",
        ImportStatus.FAILED,
        "account not found",
        "fake_bank",
        None,
        PERIOD_START,
        PERIOD_END,
        4,
        0,
        0,
    )
    assert mismatch == StatementImportResult(
        "jan.pdf",
        ImportStatus.FAILED,
        "account does not match the statement",
        "fake_bank",
        None,
        PERIOD_START,
        PERIOD_END,
        4,
        0,
        0,
    )
    assert _counts(db_engine) == (0, 0, 0)


def test_matching_an_account_by_digits_reports_the_exact_failures(
    db_engine: Engine, fake_bank: object, fake_statement_pdf: Callable[..., bytes]
) -> None:
    content = fake_statement_pdf()
    with session_scope(db_engine) as session:
        none = import_statement(session, filename="jan.pdf", content=content)
        create_account(session, "Card A", "Fake Bank", "credit_card", last4="1111")
        create_account(session, "Card B", "Fake Bank", "credit_card", last4="1111")
        shared = import_statement(session, filename="jan.pdf", content=content)
        bad_digits = import_statement(
            session, filename="jan.pdf", content=fake_statement_pdf(last4="12a4")
        )
    assert none == StatementImportResult(
        "jan.pdf",
        ImportStatus.FAILED,
        HINT,
        "fake_bank",
        None,
        PERIOD_START,
        PERIOD_END,
        4,
        0,
        0,
    )
    assert shared == StatementImportResult(
        "jan.pdf",
        ImportStatus.FAILED,
        "more than one account ends in these digits; name the account",
        "fake_bank",
        None,
        PERIOD_START,
        PERIOD_END,
        4,
        0,
        0,
    )
    assert bad_digits == StatementImportResult(
        "jan.pdf",
        ImportStatus.FAILED,
        "statement has no usable account digits",
        "fake_bank",
        None,
        PERIOD_START,
        PERIOD_END,
        4,
        0,
        0,
    )
    assert none.account_name is None
    assert _counts(db_engine) == (0, 0, 0)


def test_a_statement_that_does_not_reconcile_is_not_stored(
    db_engine: Engine, fake_bank: object, fake_statement_pdf: Callable[..., bytes]
) -> None:
    _card(db_engine)
    with session_scope(db_engine) as session:
        off = import_statement(
            session, filename="jan.pdf", content=fake_statement_pdf(closing="-84.96")
        )
        sections = import_statement(
            session,
            filename="jan.pdf",
            content=fake_statement_pdf(totals=("fees -1.00", "interest 0.05")),
        )
        both = import_statement(
            session,
            filename="jan.pdf",
            content=fake_statement_pdf(closing="-85.02", totals=("interest 1.00",)),
        )
    assert off == StatementImportResult(
        "jan.pdf",
        ImportStatus.FAILED,
        "statement does not reconcile: off by 3 cents",
        "fake_bank",
        "Household Card",
        PERIOD_START,
        PERIOD_END,
        4,
        0,
        0,
    )
    assert sections.message == (
        "statement does not reconcile: off by 0 cents; section totals differ: fees, interest"
    )
    assert sections.status is ImportStatus.FAILED
    assert sections.account_name == "Household Card"
    assert both == StatementImportResult(
        "jan.pdf",
        ImportStatus.FAILED,
        "statement does not reconcile: off by -3 cents; section totals differ: interest",
        "fake_bank",
        "Household Card",
        PERIOD_START,
        PERIOD_END,
        4,
        0,
        0,
    )
    assert _counts(db_engine) == (0, 0, 0)


def test_a_named_account_is_used_when_digits_are_shared_or_missing(
    db_engine: Engine, fake_bank: object, fake_statement_pdf: Callable[..., bytes]
) -> None:
    content = fake_statement_pdf()
    with session_scope(db_engine) as session:
        create_account(session, "Card A", "Fake Bank", "credit_card", last4="1111")
        create_account(session, "Card B", "Fake Bank", "credit_card", last4="1111")
        create_account(session, "Plain Savings", "Fake Bank", "savings")
        named = import_statement(
            session, filename="jan.pdf", content=content, account_name="  card b "
        )
        plain = import_statement(
            session,
            filename="plain.pdf",
            content=fake_statement_pdf(last4="7777", opening="0.00", closing="0.00", rows=()),
            account_name="Plain Savings",
        )
    assert (named.status, named.account_name, named.inserted) == (
        ImportStatus.IMPORTED,
        "Card B",
        4,
    )
    assert (plain.status, plain.account_name, plain.inserted) == (
        ImportStatus.IMPORTED,
        "Plain Savings",
        0,
    )


def test_a_path_stores_only_the_file_name(
    db_engine: Engine, fake_bank: object, fake_statement_pdf: Callable[..., bytes]
) -> None:
    content = fake_statement_pdf()
    _card(db_engine)
    with session_scope(db_engine) as session:
        result = import_statement(
            session, filename="/inbox/reports/january 2026.pdf", content=content
        )
    assert result.filename == "january 2026.pdf"
    with session_scope(db_engine) as session:
        stored = find_statement_by_hash(session, hashlib.sha256(content).hexdigest())
        assert stored is not None
        assert stored.source_filename == "january 2026.pdf"


def test_import_statement_does_not_commit(
    db_engine: Engine, fake_bank: object, fake_statement_pdf: Callable[..., bytes]
) -> None:
    _card(db_engine)
    session = Session(db_engine)
    result = import_statement(session, filename="jan.pdf", content=fake_statement_pdf())
    session.rollback()
    session.close()
    assert result.status is ImportStatus.IMPORTED
    assert result.inserted == 4
    assert _counts(db_engine) == (0, 0, 0)


def test_import_folder_takes_top_level_pdfs_in_name_order(
    db_engine: Engine,
    fake_bank: object,
    fake_statement_pdf: Callable[..., bytes],
    tmp_path: Path,
) -> None:
    _card(db_engine)
    inbox = tmp_path / "inbox"
    (inbox / "nested").mkdir(parents=True)
    (inbox / "a january.pdf").write_bytes(fake_statement_pdf())
    (inbox / "m broken.pdf").write_bytes(b"not a pdf")
    (inbox / "z march.PDF").write_bytes(
        fake_statement_pdf(
            start="2026-03-01", end="2026-03-31", opening="0.00", closing="0.00", rows=()
        )
    )
    (inbox / "notes.txt").write_text("FAKEBANK STATEMENT", encoding="utf-8")
    (inbox / "pdf").write_bytes(fake_statement_pdf())
    (inbox / "nested" / "e.pdf").write_bytes(fake_statement_pdf())
    dry = import_folder(db_engine, inbox, dry_run=True)
    assert [item.filename for item in dry] == ["a january.pdf", "m broken.pdf", "z march.PDF"]
    assert [item.status for item in dry] == [
        ImportStatus.DRY_RUN,
        ImportStatus.FAILED,
        ImportStatus.DRY_RUN,
    ]
    assert _counts(db_engine) == (0, 0, 0)
    real = import_folder(db_engine, inbox)
    assert [item.status for item in real] == [
        ImportStatus.IMPORTED,
        ImportStatus.FAILED,
        ImportStatus.IMPORTED,
    ]
    assert real[1] == StatementImportResult(
        "m broken.pdf", ImportStatus.FAILED, "could not read PDF"
    )
    assert [(item.inserted, item.duplicates) for item in real] == [(4, 0), (0, 0), (0, 0)]
    assert _counts(db_engine) == (2, 4, 2)
    second = import_folder(db_engine, inbox)
    assert [item.status for item in second] == [
        ImportStatus.ALREADY_IMPORTED,
        ImportStatus.FAILED,
        ImportStatus.ALREADY_IMPORTED,
    ]
    empty = tmp_path / "empty"
    empty.mkdir()
    assert import_folder(db_engine, empty) == []


def _card(engine: Engine) -> None:
    with session_scope(engine) as session:
        create_account(session, "Household Card", "Fake Bank", "credit_card", last4="1111")


def _overlap_pdf(build: Callable[..., bytes]) -> bytes:
    return build(
        start="2026-02-01",
        end="2026-02-28",
        opening="0.00",
        closing="-40.49",
        rows=OVERLAP,
    )


def _counts(engine: Engine) -> tuple[int, int, int]:
    with session_scope(engine) as session:
        return tuple(
            session.scalar(select(func.count()).select_from(table))
            for table in (StatementRow, TransactionRow, BalanceSnapshotRow)
        )
