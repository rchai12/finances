"""Turn PDF bytes into one string of text per page."""

import io
import logging

from pypdf import PdfReader

from finances.ingest.statement import StatementError

logging.getLogger("pypdf").setLevel(logging.ERROR)


def extract_pages(content: bytes) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted and not reader.decrypt(""):
            raise StatementError("PDF is password protected")
        return [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    except StatementError:
        raise
    except Exception:
        raise StatementError("could not read PDF") from None
