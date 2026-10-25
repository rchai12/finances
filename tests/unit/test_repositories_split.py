import ast
import importlib
from pathlib import Path

import pytest

import finances.db.repositories as repositories

PACKAGE = Path(repositories.__file__).parent
HOMES = {
    "aliases": [
        "add_alias",
        "alias_map",
        "delete_alias",
        "list_aliases",
    ],
    "assignments": [
        "assign_by_rule",
        "clear_categories_by_hand",
        "clear_category_by_hand",
        "count_uncategorized",
        "list_category_assignments",
        "list_uncategorized",
        "remove_category",
        "set_categories_by_hand",
        "set_category_by_hand",
    ],
    "audit": [
        "list_changes",
        "record_change",
    ],
    "accounts": [
        "AccountExistsError",
        "account_data_span",
        "account_names",
        "add_balance_snapshot",
        "create_account",
        "find_accounts_by_last4",
        "get_account",
        "get_account_by_name",
        "latest_balance",
        "list_accounts",
        "list_balance_snapshots",
        "rename_account",
        "set_account_active",
        "set_balance_snapshot",
    ],
    "statements": [
        "create_statement",
        "find_statement_by_hash",
        "list_statements",
        "statement_covers",
        "statement_periods",
    ],
    "transactions": [
        "existing_fingerprints",
        "get_transaction",
        "insert_transactions",
        "list_transaction_descriptions",
        "list_transactions",
        "list_transactions_between",
        "list_transactions_by_day",
    ],
    "feed": [
        "confirm_transaction",
        "create_feed_pull",
        "delete_feed_transaction",
        "feed_posted_total",
        "find_feed_transactions",
        "find_unlinked_statement_transactions",
        "insert_feed_transaction",
        "latest_feed_pull",
        "link_feed_transaction",
        "list_provisional_transactions",
        "update_feed_transaction",
    ],
    "feed_links": [
        "clear_sync_failure",
        "list_feed_accounts",
        "list_feed_links",
        "list_new_feed_accounts",
        "list_pending_feed_ids",
        "list_sync_failures",
        "map_feed_account",
        "record_seen_feed_account",
        "record_sync_failure",
        "set_feed_account_ignored",
    ],
    "proposals": [
        "accept_proposal",
        "count_open_proposals",
        "decided_by_a_person",
        "decline_proposal",
        "list_advice",
        "list_proposals",
        "log_advice",
        "proposal_out_of_date",
        "propose_category",
        "propose_merchant_alias",
        "propose_not_transfer",
        "propose_rule",
        "propose_transfer",
    ],
    "people": [
        "PersonExistsError",
        "create_person",
        "get_person_by_name",
        "list_account_owners",
        "list_cardholder_aliases",
        "list_people",
        "resolve_owner",
        "set_account_owner",
        "set_cardholder_alias",
    ],
    "categories": [
        "CategoryDeletion",
        "CategoryExistsError",
        "create_category",
        "create_group",
        "check_rule",
        "create_rule",
        "delete_category",
        "delete_rule",
        "edit_rule",
        "set_tax_relevant",
        "get_category_by_name",
        "list_categories",
        "list_rules",
        "rename_category",
    ],
    "budgets": [
        "list_budgets",
        "remove_budget",
        "set_budget",
    ],
    "shared": [
        "delete_settlement",
        "list_settlements",
        "list_shares",
        "record_settlement",
        "share_of",
        "share_transaction",
        "unshare_transaction",
    ],
    "splits": [
        "clear_split",
        "set_split",
        "split_by_sizes",
        "splits_for",
    ],
    "tags": [
        "add_tags",
        "list_tags",
        "note_of",
        "remove_tags",
        "set_note",
        "tagged_with",
        "tags_for",
    ],
    "transfers": [
        "create_transfer_pair",
        "find_transfer_pair",
        "list_transfer_movements",
        "list_transfer_pairs",
        "list_transfer_rejections",
        "reject_transfer",
        "unpair_transfer",
    ],
}


def test_the_package_holds_one_module_per_area() -> None:
    assert (PACKAGE / "__init__.py").is_file()
    assert not (PACKAGE.parent / "repositories.py").exists()
    names = sorted(path.stem for path in PACKAGE.glob("*.py") if path.stem != "__init__")
    assert names == sorted(HOMES)


def test_the_facade_offers_every_name_and_only_those() -> None:
    expected = sorted(name for names in HOMES.values() for name in names)
    assert len(expected) == 126
    assert sorted(repositories.__all__) == expected
    public = sorted(name for name in vars(repositories) if not name.startswith("_"))
    assert sorted(set(public) - set(HOMES)) == expected


@pytest.mark.parametrize("area", sorted(HOMES))
def test_each_name_lives_in_its_area(area: str) -> None:
    module = importlib.import_module(f"finances.db.repositories.{area}")
    for name in HOMES[area]:
        found = getattr(repositories, name)
        assert found is getattr(module, name), name
        assert found.__module__ == f"finances.db.repositories.{area}", name


def test_the_facade_only_imports() -> None:
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, ast.ImportFrom):
            assert node.module is not None and node.module.startswith("finances.db.repositories.")
            continue
        assert isinstance(node, ast.Assign) and [t.id for t in node.targets] == ["__all__"]


def test_no_area_imports_the_facade() -> None:
    for path in PACKAGE.glob("*.py"):
        if path.stem == "__init__":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module != "finances.db.repositories", path.name
            if isinstance(node, ast.Import):
                assert all(alias.name != "finances.db.repositories" for alias in node.names), (
                    path.name
                )


def test_no_module_is_longer_than_400_lines() -> None:
    sizes = {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in PACKAGE.glob("*.py")
    }
    assert {name: size for name, size in sizes.items() if size > 400} == {}
