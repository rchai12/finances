from unittest.mock import Mock, call

import pytest
from sqlalchemy.orm import Session

from finances.categorize import service


def test_order_session_and_result_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    session = Mock(spec=Session)
    result = service.CategorizeResult(3, 2, 1)
    operations = Mock()
    operations.categorize.return_value = result
    monkeypatch.setattr(service, "categorize", operations.categorize)
    monkeypatch.setattr(service, "pair_transfers", operations.pair)
    assert service.categorize_and_pair(session) is result
    assert operations.mock_calls == [call.categorize(session), call.pair(session)]
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.parametrize("failing", ["categorize", "pair"])
def test_errors_propagate_without_session_management(
    monkeypatch: pytest.MonkeyPatch, failing: str
) -> None:
    session = Mock(spec=Session)
    operations = Mock()
    error = RuntimeError("synthetic failure")
    getattr(operations, failing).side_effect = error
    monkeypatch.setattr(service, "categorize", operations.categorize)
    monkeypatch.setattr(service, "pair_transfers", operations.pair)
    with pytest.raises(RuntimeError) as caught:
        service.categorize_and_pair(session)
    assert caught.value is error
    expected = [call.categorize(session)]
    if failing == "pair":
        expected.append(call.pair(session))
    assert operations.mock_calls == expected
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
