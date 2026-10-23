from finances.domain.audit import ACTIONS, KINDS, PERSON, SYSTEM, WHO, pair_text, rule_text
from finances.domain.text import AUDIT_TEXT_LIMIT


def test_the_lists() -> None:
    assert (PERSON, SYSTEM, WHO) == ("person", "system", ("person", "system"))
    assert ACTIONS == (
        "account_added",
        "account_renamed",
        "account_closed",
        "account_reopened",
        "owner_set",
        "person_added",
        "cardholder_set",
        "category_added",
        "category_renamed",
        "category_deleted",
        "rule_added",
        "rule_edited",
        "rule_deleted",
        "category_set",
        "category_cleared",
        "budget_set",
        "budget_removed",
        "transfer_confirmed",
        "transfer_rejected",
        "transfer_unpaired",
        "statement_imported",
        "backup_deleted",
        "backup_restored",
        "proposal_accepted",
        "proposal_declined",
        "alias_added",
        "alias_deleted",
    )
    assert KINDS == (
        "account",
        "person",
        "category",
        "rule",
        "transaction",
        "transfer",
        "statement",
        "backup",
        "proposal",
        "alias",
    )
    assert AUDIT_TEXT_LIMIT == 200


def test_the_texts() -> None:
    assert rule_text("contains", "ACME COFFEE", "Coffee & Dessert", 5) == (
        'contains "ACME COFFEE" -> Coffee & Dessert (priority 5)'
    )
    assert pair_text(2, 3) == "2 -> 3"
