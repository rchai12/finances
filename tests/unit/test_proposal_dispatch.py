from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from finances.db.repositories import proposals as repo
from finances.domain import proposals as domain


@pytest.mark.parametrize("registered", [False, True], ids=["unknown", "future"])
@pytest.mark.parametrize("operation", ["accept", "stale"])
def test_unsupported_kind_refuses_without_mutation(monkeypatch, registered, operation):
    kind = "future_kind_PRIVATE_SENTINEL"
    row = SimpleNamespace(
        id=17,
        kind=kind,
        target_id=23,
        other_id=24,
        value="Synthetic category",
        reason="Synthetic reason",
        status=domain.OPEN,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        decided_at=None,
    )
    if registered:
        kinds = (*domain.KINDS, kind)
        monkeypatch.setattr(domain, "KINDS", kinds)
        monkeypatch.setattr(repo, "KINDS", kinds, raising=False)
    session = Mock()
    monkeypatch.setattr(repo, "_open_row", lambda session, number: row)
    monkeypatch.setattr(repo, "to_proposal", lambda item: item)
    waiting = Mock(return_value=None)
    monkeypatch.setattr(repo, "waits_for", waiting)
    category_check = Mock(return_value=False)
    pair_check = Mock(return_value=False)
    monkeypatch.setattr(repo, "category_is_out_of_date", category_check)
    monkeypatch.setattr(repo, "pair_is_out_of_date", pair_check)
    writers = []
    for name in (
        "set_category_by_hand",
        "create_transfer_pair",
        "reject_transfer",
        "record_change",
    ):
        writer = Mock()
        monkeypatch.setattr(repo, name, writer)
        writers.append(writer)
    if operation == "accept":
        # Reach acceptance dispatch for a future inventory member even if staleness
        # dispatch has already been repaired. Unknown kinds still require an early guard.
        monkeypatch.setattr(repo, "proposal_out_of_date", Mock(return_value=False))
    with pytest.raises(ValueError, match="^unsupported proposal kind$"):
        if operation == "accept":
            repo.accept_proposal(session, 17)
        else:
            repo.proposal_out_of_date(session, row)
    assert row.status == domain.OPEN
    assert row.decided_at is None
    for writer in writers:
        writer.assert_not_called()
    session.assert_not_called()
    assert session.mock_calls == []
    category_check.assert_not_called()
    pair_check.assert_not_called()
    if not registered:
        waiting.assert_not_called()
