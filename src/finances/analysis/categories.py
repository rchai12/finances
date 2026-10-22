"""Category tree, rules, and uncategorized items as data, before any view formats them."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.db.repositories import (
    account_names,
    get_transaction,
    list_accounts,
    list_categories,
    list_category_assignments,
    list_rules,
    list_uncategorized,
)
from finances.domain.models import (
    Account,
    AccountType,
    Category,
    CategoryAssignment,
    CategoryRule,
    Transaction,
)


@dataclass(frozen=True)
class RuleListing:
    rule: CategoryRule
    category: str


@dataclass(frozen=True)
class UncategorizedItem:
    transaction: Transaction
    account: Account


@dataclass(frozen=True)
class TransactionFacts:
    transaction: Transaction
    account: str
    category: str | None
    assignment: CategoryAssignment | None


def category_tree(session: Session) -> list[tuple[Category, list[Category]]]:
    found = list_categories(session)
    return [
        (group, [category for category in found if category.group_id == group.id])
        for group in found
        if group.group_id is None
    ]


def rule_listing(session: Session) -> list[RuleListing]:
    names = {category.id: category.name for category in list_categories(session)}
    return [RuleListing(rule, names[rule.category_id]) for rule in list_rules(session)]


def uncategorized_items(session: Session, limit: int) -> list[UncategorizedItem]:
    accounts = {account.id: account for account in list_accounts(session, include_inactive=True)}
    return [
        UncategorizedItem(item, accounts[item.account_id])
        for item in list_uncategorized(session, limit)
    ]


def card_credit_count(items: list[UncategorizedItem]) -> int:
    count = 0
    for item in items:
        if item.account.type == AccountType.CREDIT_CARD and item.transaction.amount_cents > 0:
            count += 1
    return count


def transaction_facts(session: Session, transaction_id: int) -> TransactionFacts | None:
    item = get_transaction(session, transaction_id)
    if item is None:
        return None
    assignment = list_category_assignments(session).get(transaction_id)
    names = {category.id: category.name for category in list_categories(session)}
    category = None if assignment is None else names[assignment.category_id]
    return TransactionFacts(item, account_names(session)[item.account_id], category, assignment)
