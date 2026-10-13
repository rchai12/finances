"""Read a statement, check it, and store what is new."""

import hashlib
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.repositories import (
    add_balance_snapshot,
    create_statement,
    existing_fingerprints,
    find_accounts_by_last4,
    find_statement_by_hash,
    get_account_by_name,
    insert_transactions,
)
from finances.domain.models import Account, DataSource, NewTransaction
from finances.ingest.dedup import fingerprint_lines
from finances.ingest.parsers import detect_parser
from finances.ingest.parsers.helpers import collapse_ws
from finances.ingest.pdf_text import extract_pages
from finances.ingest.reconcile import ReconcileResult, reconcile
from finances.ingest.statement import ParsedStatement, StatementError, StatementLine


class ImportStatus(StrEnum):
    """How an attempt to import one statement ended."""

    IMPORTED = "imported"
    DRY_RUN = "dry_run"
    ALREADY_IMPORTED = "already_imported"
    FAILED = "failed"


@dataclass(frozen=True)
class StatementImportResult:
    """What happened to one statement. Counts and names only, never a line or a balance."""

    filename: str
    status: ImportStatus
    message: str
    parser_name: str | None = None
    account_name: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    lines_parsed: int = 0
    inserted: int = 0
    duplicates: int = 0


def import_statement(
    session: Session,
    *,
    filename: str,
    content: bytes,
    account_name: str | None = None,
    dry_run: bool = False,
) -> StatementImportResult:
    """Read one statement and store what is new. The caller commits."""
    stored_name = Path(filename).name
    digest = hashlib.sha256(content).hexdigest()
    if find_statement_by_hash(session, digest) is not None:
        return StatementImportResult(stored_name, ImportStatus.ALREADY_IMPORTED, "already imported")

    try:
        pages = extract_pages(content)
        parser = detect_parser(pages)
        parsed = parser.parse(pages)
    except StatementError as error:
        return StatementImportResult(stored_name, ImportStatus.FAILED, str(error))

    read = {
        "parser_name": parsed.parser_name,
        "period_start": parsed.period_start,
        "period_end": parsed.period_end,
        "lines_parsed": len(parsed.lines),
    }
    matched = _match_account(session, parsed, account_name)
    if isinstance(matched, str):
        return StatementImportResult(stored_name, ImportStatus.FAILED, matched, **read)

    account = matched
    read["account_name"] = account.name
    checked = reconcile(parsed)
    if not checked.ok:
        return StatementImportResult(
            stored_name, ImportStatus.FAILED, _reconcile_message(checked), **read
        )

    fingerprints = fingerprint_lines(account.id, parsed.lines)
    known = existing_fingerprints(session, account.id, fingerprints)
    fresh = [
        (line, fingerprint)
        for line, fingerprint in zip(parsed.lines, fingerprints, strict=True)
        if fingerprint not in known
    ]
    inserted = len(fresh)
    duplicates = len(parsed.lines) - inserted
    if dry_run:
        return StatementImportResult(
            stored_name,
            ImportStatus.DRY_RUN,
            "dry run: nothing written",
            inserted=inserted,
            duplicates=duplicates,
            **read,
        )

    statement = create_statement(
        session,
        account_id=account.id,
        source_filename=stored_name,
        file_sha256=digest,
        parser_name=parsed.parser_name,
        period_start=parsed.period_start,
        period_end=parsed.period_end,
        opening_balance_cents=parsed.opening_balance_cents,
        closing_balance_cents=parsed.closing_balance_cents,
        lines_parsed=len(parsed.lines),
        rows_inserted=inserted,
        rows_duplicate=duplicates,
    )
    insert_transactions(
        session,
        [
            _new_transaction(account.id, statement.id, line, fingerprint)
            for line, fingerprint in fresh
        ],
    )
    add_balance_snapshot(
        session,
        account.id,
        parsed.period_end,
        parsed.closing_balance_cents,
        DataSource.STATEMENT,
    )
    return StatementImportResult(
        stored_name,
        ImportStatus.IMPORTED,
        "imported",
        inserted=inserted,
        duplicates=duplicates,
        **read,
    )


def import_folder(
    engine: Engine, folder: Path, *, dry_run: bool = False
) -> list[StatementImportResult]:
    """Import each top-level PDF in file-name order. One failure does not stop the rest."""
    paths = sorted(
        (path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: path.name,
    )
    results = []
    for path in paths:
        with session_scope(engine) as session:
            results.append(
                import_statement(
                    session,
                    filename=path.name,
                    content=path.read_bytes(),
                    dry_run=dry_run,
                )
            )
    return results


def _match_account(
    session: Session, parsed: ParsedStatement, account_name: str | None
) -> Account | str:
    if account_name is not None:
        account = get_account_by_name(session, account_name)
        if account is None:
            return "account not found"
        if account.last4 is not None and account.last4 != parsed.account_last4:
            return "account does not match the statement"
        return account
    try:
        matches = find_accounts_by_last4(session, parsed.account_last4)
    except ValueError:
        return "statement has no usable account digits"
    if len(matches) == 1:
        return matches[0]
    if not matches:
        last4 = parsed.account_last4
        return (
            f'no account ends in {last4}; add one with: fin accounts add --name "NAME" '
            f'--institution "{parsed.institution}" --type {parsed.account_type.value} '
            f"--last4 {last4}"
        )
    return "more than one account ends in these digits; name the account"


def _reconcile_message(result: ReconcileResult) -> str:
    message = f"statement does not reconcile: off by {result.difference_cents} cents"
    if result.section_mismatches:
        names = ", ".join(section.value for section in result.section_mismatches)
        message = f"{message}; section totals differ: {names}"
    return message


def _new_transaction(
    account_id: int, statement_id: int, line: StatementLine, fingerprint: str
) -> NewTransaction:
    return NewTransaction(
        account_id=account_id,
        statement_id=statement_id,
        posted_date=line.posted_date,
        transaction_date=line.transaction_date,
        amount_cents=line.amount_cents,
        description=collapse_ws(line.description),
        section=line.section.value,
        card_last4=line.card_last4,
        cardholder=line.cardholder,
        external_id=line.external_ref,
        source=DataSource.STATEMENT,
        is_pending=False,
        fingerprint=fingerprint,
    )
