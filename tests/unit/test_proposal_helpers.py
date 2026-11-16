from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from finances.db import time as db_time
from finances.db.repositories import audit
from finances.domain.proposals import clean_reason


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        pytest.param("a", "a", id="one"),
        pytest.param(" \tACME\n  reason\u00a0 here \r", "ACME reason here", id="collapse"),
        pytest.param(
            "x" * 200,
            (
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            ),
            id="limit",
        ),
        pytest.param(
            " \n" + "x" * 200 + "\t ",
            (
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            ),
            id="cleaned-limit",
        ),
    ],
)
def test_clean_reason_accepts_cleaned_text(reason, expected):
    assert clean_reason(reason) == expected


@pytest.mark.parametrize("reason", ["", " \n\t\u00a0", "x" * 201], ids=["empty", "blank", "long"])
def test_clean_reason_refuses_without_echo(reason):
    with pytest.raises(ValueError, match="^a reason must be 1 to 200 characters$"):
        clean_reason(reason)


def test_utc_now_reads_aware_utc_each_time(monkeypatch):
    first = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    second = datetime(2026, 1, 2, 3, 4, 6, 654321, tzinfo=UTC)
    source = Mock()
    source.now.side_effect = [first, second]
    monkeypatch.setattr(db_time, "datetime", source)
    assert db_time.utc_now() is first
    assert db_time.utc_now() is second
    assert source.now.call_args_list == [((UTC,), {}), ((UTC,), {})]


def test_audit_reads_shared_clock_per_event(monkeypatch):
    first = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    second = datetime(2026, 1, 2, 3, 4, 6, 654321, tzinfo=UTC)
    clock = Mock(side_effect=[first, second])
    monkeypatch.setattr(db_time, "utc_now", clock)
    monkeypatch.setattr(audit, "to_change", lambda row: row)
    session = Mock()
    one = audit.record_change(
        session, action="category_added", kind="category", record_id=1, after="Synthetic leaf"
    )
    two = audit.record_change(
        session, action="category_added", kind="category", record_id=2, after="Synthetic other"
    )
    assert one.at is first
    assert two.at is second
    assert (one.after, two.after) == ("Synthetic leaf", "Synthetic other")
    assert clock.call_count == 2
