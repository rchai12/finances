"""Turn PDF bytes into one string of text per page."""

import io
import logging
import re

from pypdf import PageObject, PdfReader

from finances.ingest.statement import StatementError

logging.getLogger("pypdf").setLevel(logging.ERROR)

_WIDE_GAP = re.compile(" {3,}")


def _page_text(page: PageObject) -> str:
    """Read a page in layout mode, or in plain mode when layout mode fails, with gaps narrowed."""
    try:
        text = page.extract_text(extraction_mode="layout")
    except Exception:
        text = page.extract_text()
    return _WIDE_GAP.sub("  ", text or "")


def extract_pages(content: bytes) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted and not reader.decrypt(""):
            raise StatementError("PDF is password protected")
        return [_page_text(page) for page in reader.pages]
    except StatementError:
        raise
    except Exception:
        raise StatementError("could not read PDF") from None
