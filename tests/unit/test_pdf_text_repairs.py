import io
import re

import pypdf
import pytest
from pypdf import PdfReader, PdfWriter

from finances.ingest.pdf_text import extract_pages
from finances.ingest.statement import StatementError


def with_blank_pages(content: bytes, before: int = 0, after: int = 1) -> bytes:
    """Return the PDF with pages that have no content stream at all, as some banks add."""
    writer = PdfWriter()
    for _ in range(before):
        writer.add_blank_page(612, 792)
    for page in PdfReader(io.BytesIO(content)).pages:
        writer.add_page(page)
    for _ in range(after):
        writer.add_blank_page(612, 792)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def test_the_blank_page_is_one_that_layout_mode_cannot_read(make_pdf) -> None:
    content = with_blank_pages(make_pdf([["ACME COFFEE"]]))
    page = PdfReader(io.BytesIO(content)).pages[1]
    with pytest.raises(KeyError):
        page.extract_text(extraction_mode="layout")
    assert page.extract_text() == ""


def test_a_page_without_content_is_an_empty_string(make_pdf) -> None:
    content = with_blank_pages(make_pdf([["ACME COFFEE"], ["FOOBAR GROCERY"]]))
    assert extract_pages(content) == ["ACME COFFEE", "FOOBAR GROCERY", ""]


def test_pages_without_content_anywhere_in_the_file(make_pdf) -> None:
    content = with_blank_pages(make_pdf([["ACME COFFEE"]]), before=2, after=1)
    assert extract_pages(content) == ["", "", "ACME COFFEE", ""]


def test_a_file_of_blank_pages_only(make_pdf) -> None:
    assert extract_pages(with_blank_pages(make_pdf([]), after=2)) == ["", ""]


def test_the_other_pages_are_still_read_in_layout_mode(make_pdf) -> None:
    content = with_blank_pages(make_pdf([["03/04\tACME COFFEE\t4.50", "03/05\tFOOBAR\t12.00"]]))
    assert extract_pages(content)[0] == "03/04  ACME COFFEE  4.50\n03/05  FOOBAR  12.00"


def test_wide_gaps_become_two_spaces(make_pdf) -> None:
    content = make_pdf([["03/04\tACME COFFEE\t4.50", "\tFOOBAR GROCERY", "A B\t\tC"]])
    page = extract_pages(content)[0]
    assert page.split("\n") == ["03/04  ACME COFFEE  4.50", "  FOOBAR GROCERY", "A B  C"]
    assert not re.search(r"[ \t]{3,}", page)


def test_single_spaces_and_line_breaks_are_kept(make_pdf) -> None:
    content = make_pdf([["ACME COFFEE #12 DALLAS TX", "", "FOOBAR"], ["SECOND PAGE"]])
    pages = extract_pages(content)
    assert pages[0].split("\n")[0] == "ACME COFFEE #12 DALLAS TX"
    assert pages[0].split("\n")[-1] == "FOOBAR"
    assert pages[1] == "SECOND PAGE"


@pytest.mark.parametrize("error", [KeyError("/Contents"), RuntimeError("boom"), ValueError("bad")])
def test_any_failure_of_layout_mode_falls_back_to_plain_mode(
    make_pdf, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    calls = []

    def fake(self, *args, **kwargs):
        calls.append(kwargs.get("extraction_mode", "plain"))
        if kwargs.get("extraction_mode") == "layout":
            raise error
        return "PLAIN     TEXT\nOF THE PAGE"

    monkeypatch.setattr(pypdf.PageObject, "extract_text", fake)
    assert extract_pages(make_pdf([["x"], ["y"]])) == ["PLAIN  TEXT\nOF THE PAGE"] * 2
    assert calls == ["layout", "plain", "layout", "plain"]


def test_plain_mode_is_not_used_when_layout_mode_works(
    make_pdf, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def fake(self, *args, **kwargs):
        calls.append(kwargs.get("extraction_mode", "plain"))
        return None

    monkeypatch.setattr(pypdf.PageObject, "extract_text", fake)
    assert extract_pages(make_pdf([["x"]])) == [""]
    assert calls == ["layout"]


def test_a_page_that_neither_mode_can_read_is_an_unreadable_pdf(
    make_pdf, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(self, *args, **kwargs):
        raise KeyError("SECRET TEXT FROM THE PAGE")

    monkeypatch.setattr(pypdf.PageObject, "extract_text", fake)
    with pytest.raises(StatementError) as caught:
        extract_pages(make_pdf([["x"]]))
    assert str(caught.value) == "could not read PDF"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_plain_mode_returning_nothing_is_an_empty_page(
    make_pdf, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(self, *args, **kwargs):
        if kwargs.get("extraction_mode") == "layout":
            raise KeyError("/Contents")
        return None

    monkeypatch.setattr(pypdf.PageObject, "extract_text", fake)
    assert extract_pages(make_pdf([["x"]])) == [""]


def test_a_password_protected_pdf_is_still_refused(make_pdf, encrypt_pdf) -> None:
    content = encrypt_pdf(with_blank_pages(make_pdf([["ACME COFFEE"]])), "secret-pass")
    with pytest.raises(StatementError) as caught:
        extract_pages(content)
    assert str(caught.value) == "PDF is password protected"


def test_runs_of_three_or_more_spaces_and_nothing_else(
    make_pdf, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(self, *args, **kwargs):
        return "A B  C   D    E" + " " * 5000 + "F\n\n\n   G\n \n  H   "

    monkeypatch.setattr(pypdf.PageObject, "extract_text", fake)
    assert extract_pages(make_pdf([["x"]])) == ["A B  C  D  E  F\n\n\n  G\n \n  H  "]
