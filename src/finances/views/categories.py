"""The category tree, the rules, and uncategorized transactions, as plain text."""

from dataclasses import dataclass

from finances.analysis.categories import (
    RuleListing,
    TransactionFacts,
    UncategorizedItem,
)
from finances.categorize.service import CategorizeResult, RulePreview
from finances.domain.merchants import MerchantAlias, clean_merchant
from finances.domain.models import MANUAL, Category, CategoryAssignment
from finances.domain.money import format_cents
from finances.views.format import mask_last4


@dataclass(frozen=True)
class CategoryLine:
    group: str
    category: str
    kind: str


@dataclass(frozen=True)
class RuleLine:
    id: str
    priority: str
    match: str
    pattern: str
    category: str


@dataclass(frozen=True)
class UncategorizedLine:
    id: str
    date: str
    account: str
    merchant: str
    amount: str


@dataclass(frozen=True)
class TransactionDetail:
    id: int
    date: str
    account: str
    description: str
    merchant: str
    amount: str
    card: str
    category: str
    set_by: str


def _kind(category: Category) -> str:
    flags = (
        ("transfer", category.is_transfer),
        ("income", category.is_income),
        ("sensitive", category.is_sensitive),
    )
    return ", ".join(word for word, flag in flags if flag)


def category_lines(tree: list[tuple[Category, list[Category]]]) -> list[CategoryLine]:
    """One line per category, or one for an empty group, groups in tree order."""
    lines: list[CategoryLine] = []
    for group, categories in tree:
        if not categories:
            lines.append(CategoryLine(group.name, "", _kind(group)))
            continue
        for category in categories:
            lines.append(CategoryLine(group.name, category.name, _kind(category)))
    return lines


def category_choices(tree: list[tuple[Category, list[Category]]]) -> list[tuple[str, list[str]]]:
    """Each group with its categories' names, both in name order ignoring case."""
    return [(group.name, [category.name for category in categories]) for group, categories in tree]


def rule_lines(listing: list[RuleListing]) -> list[RuleLine]:
    return [
        RuleLine(
            str(item.rule.id),
            str(item.rule.priority),
            item.rule.match,
            item.rule.pattern,
            item.category,
        )
        for item in listing
    ]


CARD_CREDITS = (
    "Money in on a card: {count}, likely a refund or a card payment."
    " Set a category, or pair it on the Transfers page."
)


def card_credits_note(count: int) -> str | None:
    """How many of the uncategorized list are money in on a credit card, or None."""
    return None if count == 0 else CARD_CREDITS.format(count=count)


def uncategorized_lines(items: list[UncategorizedItem]) -> list[UncategorizedLine]:
    return [
        UncategorizedLine(
            str(item.transaction.id),
            item.transaction.posted_date.isoformat(),
            item.account.name,
            clean_merchant(item.transaction.description),
            format_cents(item.transaction.amount_cents),
        )
        for item in items
    ]


def _set_by(assignment: CategoryAssignment | None) -> str:
    if assignment is None:
        return ""
    if assignment.source == MANUAL:
        return "by hand"
    return f"by rule {assignment.rule_id}"


def transaction_detail(facts: TransactionFacts) -> TransactionDetail:
    item = facts.transaction
    return TransactionDetail(
        item.id,
        item.posted_date.isoformat(),
        facts.account,
        item.description,
        clean_merchant(item.description),
        format_cents(item.amount_cents),
        mask_last4(item.card_last4),
        facts.category or "",
        _set_by(facts.assignment),
    )


def categorized_text(result: CategorizeResult) -> str:
    noun = "transaction" if result.total == 1 else "transactions"
    return (
        f"Categorized {result.total} {noun}: {result.changed} changed, "
        f"{result.uncategorized} without a category."
    )


@dataclass(frozen=True)
class AliasRow:
    source: str
    target: str


def alias_rows(aliases: list[MerchantAlias]) -> list[AliasRow]:
    return [AliasRow(item.source, item.target) for item in aliases]


@dataclass(frozen=True)
class PreviewLine:
    id: str
    date: str
    account: str
    merchant: str
    amount: str
    now: str


def preview_lines(preview: RulePreview) -> list[PreviewLine]:
    return [
        PreviewLine(
            str(item.transaction.id),
            item.transaction.posted_date.isoformat(),
            item.account,
            item.merchant,
            format_cents(item.transaction.amount_cents),
            item.now or "",
        )
        for item in preview.examples
    ]


def preview_text(preview: RulePreview) -> str:
    if preview.changes == 0:
        count = "no transactions"
    elif preview.changes == 1:
        count = "1 transaction"
    else:
        count = f"{preview.changes} transactions"
    return f"This rule would put {count} in {preview.category}."


def preview_more(preview: RulePreview) -> str | None:
    if preview.changes <= len(preview.examples):
        return None
    return f"Showing the {len(preview.examples)} newest."
