"""Statement list, gaps, and an import's result, as plain text for the page."""

from dataclasses import dataclass

from finances.analysis.statements import StatementGap
from finances.domain.models import Statement
from finances.domain.money import format_cents
from finances.ingest.service import ImportStatus, StatementImportResult

_STATUS = {
    ImportStatus.IMPORTED: "imported",
    ImportStatus.DRY_RUN: "dry run, nothing written",
    ImportStatus.ALREADY_IMPORTED: "already imported",
}


@dataclass(frozen=True)
class StatementRow:
    account: str
    file: str
    parser: str
    period: str
    opening: str
    closing: str
    lines: str
    new: str


@dataclass(frozen=True)
class GapRow:
    account: str
    start: str
    end: str


def statement_rows(statements: list[Statement], names: dict[int, str]) -> list[StatementRow]:
    """Each statement as `fin statements list` shows it, in list order."""
    return [
        StatementRow(
            names[item.account_id],
            item.source_filename,
            item.parser_name,
            f"{item.period_start.isoformat()} to {item.period_end.isoformat()}",
            format_cents(item.opening_balance_cents),
            format_cents(item.closing_balance_cents),
            str(item.lines_parsed),
            str(item.rows_inserted),
        )
        for item in statements
    ]


def gap_rows(gaps: list[StatementGap]) -> list[GapRow]:
    """Each gap with ISO dates."""
    return [GapRow(gap.account, gap.start.isoformat(), gap.end.isoformat()) for gap in gaps]


def import_rows(result: StatementImportResult) -> list[tuple[str, str]]:
    """Label and value pairs for a finished upload, or none when it failed."""
    if result.status is ImportStatus.FAILED:
        return []
    if result.status is ImportStatus.ALREADY_IMPORTED:
        return [("File", result.filename), ("Status", _STATUS[result.status])]
    period = ""
    if result.period_start is not None and result.period_end is not None:
        period = f"{result.period_start.isoformat()} to {result.period_end.isoformat()}"
    return [
        ("File", result.filename),
        ("Parser", result.parser_name or ""),
        ("Account", result.account_name or ""),
        ("Period", period),
        ("Lines", str(result.lines_parsed)),
        ("Inserted", str(result.inserted)),
        ("Duplicates", str(result.duplicates)),
        ("Status", _STATUS[result.status]),
    ]
