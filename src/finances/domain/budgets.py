"""Monthly budget targets and progress. Pure: no database."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class BudgetTarget:
    name: str
    is_group: bool
    target_cents: int


@dataclass(frozen=True)
class BudgetLine:
    name: str
    is_group: bool
    target_cents: int
    spent_cents: int
    left_cents: int
    used_percent: int
    month_gone_percent: int


def _half_up(numerator: int, denominator: int) -> int:
    """Divide by a positive denominator, rounding half away from zero."""
    if numerator >= 0:
        return (2 * numerator + denominator) // (2 * denominator)
    return -((2 * (-numerator) + denominator) // (2 * denominator))


def month_gone_percent(start: date, end: date, today: date) -> int:
    """Share of the month from start through today, in whole percent."""
    if today < start:
        return 0
    if today > end:
        return 100
    total = (end - start).days + 1
    elapsed = (today - start).days + 1
    return _half_up(elapsed * 100, total)


def budget_lines(
    targets: Iterable[BudgetTarget],
    spent_by_category: Mapping[str, int],
    spent_by_group: Mapping[str, int],
    start: date,
    end: date,
    today: date,
) -> list[BudgetLine]:
    """One line per target: spent, left, and how far through the month."""
    gone = month_gone_percent(start, end, today)
    lines = []
    for target in targets:
        spent = (
            spent_by_group.get(target.name, 0)
            if target.is_group
            else spent_by_category.get(target.name, 0)
        )
        lines.append(
            BudgetLine(
                name=target.name,
                is_group=target.is_group,
                target_cents=target.target_cents,
                spent_cents=spent,
                left_cents=target.target_cents - spent,
                used_percent=_half_up(spent * 100, target.target_cents),
                month_gone_percent=gone,
            )
        )
    return sorted(lines, key=lambda line: (line.name.lower(), line.name))
