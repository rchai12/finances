from unittest.mock import Mock

import pytest

from finances.db import time as db_time
from finances.db.repositories import (
    category_changes,
    finding_proposals,
    new_categories,
    proposals,
    rule_changes,
    transfers,
)

# Public entry point, helper lookup module, invalid arguments, existing next refusal.
CASES = [
    (proposals.propose_category, proposals, (999, "Missing"), {}, "transaction not found"),
    (proposals.propose_transfer, transfers, (999, 998), {}, "transaction not found"),
    (proposals.propose_not_transfer, transfers, (999, 998), {}, "transaction not found"),
    (
        proposals.propose_rule,
        proposals,
        (999, "", "Missing"),
        {},
        "a rule pattern must be 1 to 100 characters",
    ),
    (proposals.propose_merchant_alias, proposals, (999, "Missing"), {}, "transaction not found"),
    (
        new_categories.propose_group,
        new_categories,
        (999, ""),
        {"kind": "bad"},
        "a group name must be 1 to 50 characters",
    ),
    (
        new_categories.propose_new_category,
        new_categories,
        (999, "", "Missing"),
        {},
        "a category name must be 1 to 50 characters",
    ),
    (rule_changes.propose_rule_change, rule_changes, (999,), {"pattern": ""}, "rule not found"),
    (
        rule_changes.propose_rule_change,
        rule_changes,
        (999,),
        {"delete": True, "pattern": ""},
        "rule not found",
    ),
    (
        category_changes.propose_category_change,
        category_changes,
        ("Missing",),
        {"rename_to": "", "delete": True},
        "category not found",
    ),
    (
        category_changes.propose_category_change,
        category_changes,
        ("Missing",),
        {"delete": True},
        "category not found",
    ),
    (
        finding_proposals.propose_finding_status,
        finding_proposals,
        (None, "bad"),
        {},
        "status must be one of: handled, ignored",
    ),
]


class ReasonSentinel(ValueError):
    pass


@pytest.mark.parametrize("writer,module,args,kwargs,message", CASES)
def test_every_writer_delegates_original_reason_first(
    monkeypatch, writer, module, args, kwargs, message
):
    raw = " \tACME\n original reason "
    error = ReasonSentinel("distinct helper sentinel")
    helper = Mock(side_effect=error)
    clock = Mock()
    monkeypatch.setattr(module, "clean_reason", helper)
    monkeypatch.setattr(db_time, "utc_now", clock)
    session = Mock()
    with pytest.raises(ReasonSentinel) as stopped:
        writer(session, *args, reason=raw, **kwargs)
    assert stopped.value is error
    helper.assert_called_once_with(raw)
    assert session.mock_calls == []
    clock.assert_not_called()


@pytest.mark.parametrize("writer,module,args,kwargs,message", CASES)
@pytest.mark.parametrize("reason", [" \t\n\u00a0", "x" * 201])
def test_invalid_reason_precedes_other_refusals(
    monkeypatch, writer, module, args, kwargs, message, reason
):
    clock = Mock()
    monkeypatch.setattr(db_time, "utc_now", clock)
    session = Mock()
    with pytest.raises(ValueError) as stopped:
        writer(session, *args, reason=reason, **kwargs)
    assert str(stopped.value) == "a reason must be 1 to 200 characters"
    assert session.mock_calls == []
    clock.assert_not_called()


@pytest.mark.parametrize("writer,module,args,kwargs,message", CASES)
def test_valid_reason_preserves_next_refusal(monkeypatch, writer, module, args, kwargs, message):
    session = Mock()
    session.get.return_value = None
    session.scalars.return_value.first.return_value = None
    clock = Mock()
    monkeypatch.setattr(db_time, "utc_now", clock)
    with pytest.raises(ValueError) as stopped:
        writer(session, *args, reason="Synthetic reason", **kwargs)
    assert str(stopped.value) == message
    session.add.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    clock.assert_not_called()


def test_writer_matrix_covers_all_ten_public_entries():
    assert {writer.__name__ for writer, *_ in CASES} == {
        "propose_category",
        "propose_transfer",
        "propose_not_transfer",
        "propose_rule",
        "propose_merchant_alias",
        "propose_group",
        "propose_new_category",
        "propose_rule_change",
        "propose_category_change",
        "propose_finding_status",
    }
