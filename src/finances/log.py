import logging
import re
import sys

_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_DIGIT_RUN = re.compile(r"\d(?:[ -]*\d){5,}")


def _redact(text: str) -> str:
    text = _EMAIL.sub("[REDACTED-EMAIL]", text)
    return _DIGIT_RUN.sub("[REDACTED-NUM]", text)


class RedactingFilter(logging.Filter):
    """Rewrite log messages so long digit runs and email addresses are removed."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(record.getMessage())
        record.args = ()
        return True


def setup_logging(level: str) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)
    root.setLevel(level.upper())
