import logging

from finances.log import RedactingFilter


def _message(text: str) -> str:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=text,
        args=(),
        exc_info=None,
    )
    assert RedactingFilter().filter(record)
    return record.getMessage()


def test_redacts_long_digit_runs_and_email() -> None:
    message = _message("card 4111 1111 1111 1111 acct 12345678 me@example.com")
    assert "4111" not in message
    assert "12345678" not in message
    assert "me@example.com" not in message
    assert message.count("[REDACTED-NUM]") == 2
    assert "[REDACTED-EMAIL]" in message


def test_leaves_short_digit_runs() -> None:
    assert _message("imported 12 rows") == "imported 12 rows"
