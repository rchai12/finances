"""Check that a parsed statement adds up to its own closing balance."""

from dataclasses import dataclass

from finances.ingest.statement import ParsedStatement, Section


@dataclass(frozen=True)
class ReconcileResult:
    ok: bool
    expected_closing_cents: int
    actual_closing_cents: int
    difference_cents: int
    section_mismatches: dict[Section, tuple[int, int]]


def reconcile(statement: ParsedStatement) -> ReconcileResult:
    expected = statement.opening_balance_cents + sum(item.amount_cents for item in statement.lines)
    actual = statement.closing_balance_cents
    difference = actual - expected
    mismatches: dict[Section, tuple[int, int]] = {}
    for section, declared in statement.declared_section_totals.items():
        computed = sum(item.amount_cents for item in statement.lines if item.section == section)
        if computed != declared:
            mismatches[section] = (declared, computed)
    return ReconcileResult(
        ok=difference == 0 and not mismatches,
        expected_closing_cents=expected,
        actual_closing_cents=actual,
        difference_cents=difference,
        section_mismatches=mismatches,
    )
