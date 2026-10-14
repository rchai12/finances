import logging
import re

import pytest

from finances.ingest.pdf_text import extract_pages
from finances.ingest.statement import StatementError

UNREADABLE = "could not read PDF"


def test_one_string_per_page_in_order_keeping_an_empty_page(make_pdf) -> None:
    content = make_pdf([["ACME COFFEE"], [], ["FOOBAR GROCERY"]])
    pages = extract_pages(content)
    assert pages[0] == "ACME COFFEE"
    assert pages[1] == ""
    assert pages[2] == "FOOBAR GROCERY"
    assert len(pages) == 3


def test_a_pdf_with_no_pages_gives_an_empty_list(make_pdf) -> None:
    assert extract_pages(make_pdf([])) == []


def test_layout_mode_keeps_wide_gaps_between_columns(make_pdf) -> None:
    content = make_pdf([["03/04\tACME COFFEE\t4.50"]])
    row = extract_pages(content)[0]
    assert re.fullmatch(r"03/04 {2,}ACME COFFEE {2,}4\.50", row)


def test_empty_user_password_opens_an_owner_encrypted_pdf(make_pdf, encrypt_pdf) -> None:
    content = encrypt_pdf(make_pdf([["ACME COFFEE"]]), "")
    assert extract_pages(content) == ["ACME COFFEE"]


def test_a_user_password_raises_the_exact_message(make_pdf, encrypt_pdf) -> None:
    content = encrypt_pdf(make_pdf([["ACME COFFEE"]]), "secret-pass")
    with pytest.raises(StatementError) as excinfo:
        extract_pages(content)
    assert str(excinfo.value) == "PDF is password protected"


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"this is plain text, not a pdf",
        b"%PDF-1.4\n1 0 obj\n<< >>\n",
        bytes(range(256)) * 4,
    ],
    ids=["empty", "plain text", "cut short", "binary noise"],
)
def test_unreadable_bytes_raise_the_exact_message_without_the_library_error(content: bytes) -> None:
    with pytest.raises(StatementError) as excinfo:
        extract_pages(content)
    assert str(excinfo.value) == UNREADABLE
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True


def test_importing_pdf_text_silences_the_pypdf_logger() -> None:
    assert logging.getLogger("pypdf").getEffectiveLevel() >= logging.ERROR
    assert logging.getLogger("pypdf._reader").getEffectiveLevel() >= logging.ERROR
