from unittest.mock import Mock

import pytest
from sqlalchemy import Engine

from finances.categorize import service
from finances.db.engine import session_scope
from finances.db.repositories import (
    create_rule,
    list_category_assignments,
    list_transfer_pairs,
    propose_category,
    propose_merchant_alias,
    propose_rule,
    propose_rule_change,
)
from tests.integration.test_web_pair_after_rules_more import add_pair


@pytest.mark.parametrize("kind", ["rule", "alias", "rule_edit", "rule_delete"])
def test_submission_is_inert_acceptance_categorizes_and_pairs(
    db_engine: Engine, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    with session_scope(db_engine) as session:
        add_pair(session)
        if kind == "alias":
            create_rule(session, "EXAMPLE MOVEMENT", "Groceries")
            proposal = propose_merchant_alias(session, 1, "EXAMPLE MOVEMENT", "same merchant")
        elif kind == "rule":
            proposal = propose_rule(session, 1, "SYNTHETIC", "Groceries", "example rule")
        else:
            rule = create_rule(session, "SYNTHETIC", "Dining")
            proposal = propose_rule_change(
                session,
                rule.id,
                "example change",
                delete=kind == "rule_delete",
                **({"category": "Groceries"} if kind == "rule_edit" else {}),
            )
        assert list_transfer_pairs(session) == []
        assert list_category_assignments(session) == {}
        categorizing = Mock(wraps=service.categorize)
        pairing = Mock(wraps=service.pair_transfers)
        monkeypatch.setattr(service, "categorize", categorizing)
        monkeypatch.setattr(service, "pair_transfers", pairing)
        accepted = service.accept_proposals(session, [proposal.id])
        expected = (
            service.CategorizeResult(2, 0, 2)
            if kind == "rule_delete"
            else service.CategorizeResult(2, 2, 0)
        )
        assert accepted.categorized == expected
        assert categorizing.call_args.args == (session,)
        assert categorizing.call_count == pairing.call_count == 1
        assert pairing.call_args.args == (session,)
        assert [(item.id, item.status) for item in accepted.proposals] == [
            (proposal.id, "accepted")
        ]
    with session_scope(db_engine) as session:
        assert len(list_transfer_pairs(session)) == 1
        assert len(list_category_assignments(session)) == (0 if kind == "rule_delete" else 2)


def test_other_acceptance_kind_does_not_categorize_or_pair(
    db_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_scope(db_engine) as session:
        add_pair(session)
        proposal = propose_category(session, 1, "Groceries", "example category")
        categorizing = Mock()
        pairing = Mock()
        monkeypatch.setattr(service, "categorize", categorizing)
        monkeypatch.setattr(service, "pair_transfers", pairing)
        accepted = service.accept_proposals(session, [proposal.id])
        assert accepted.categorized is None
        assert accepted.proposals[0].status == "accepted"
        categorizing.assert_not_called()
        pairing.assert_not_called()
    with session_scope(db_engine) as session:
        assert list_transfer_pairs(session) == []
        assert 1 in list_category_assignments(session)
