"""Opt-in check of the real statements in data/samples/. It is not part of the normal test run.

Run it yourself, on the machine that holds the statements:

    .venv/bin/python -m pytest tests/real_samples/check_real_samples.py --no-cov

For each PDF it reads the text, picks a parser, parses, and reconciles. It reports only a sample
number, the parser name, counts, and a difference in cents. It never prints a file name, a line of
a statement, a description, an amount, or a balance (AGENTS.md privacy rule 6), and neither may
anything added to this file.
"""

from pathlib import Path

import pytest

from finances.ingest.parsers import detect_parser
from finances.ingest.pdf_text import extract_pages
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import StatementError

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
FILES = sorted(SAMPLES.glob("*.[pP][dD][fF]")) if SAMPLES.is_dir() else []


def test_there_are_samples_to_check() -> None:
    if not FILES:
        pytest.skip("no PDF files in data/samples")


@pytest.mark.parametrize("index", range(len(FILES)), ids=lambda index: f"sample_{index}")
def test_sample_parses_and_reconciles(index: int) -> None:
    try:
        pages = extract_pages(FILES[index].read_bytes())
        parser = detect_parser(pages)
    except StatementError as error:
        pytest.xfail(f"sample_{index}: {error}")
    try:
        statement = parser.parse(pages)
    except StatementError as error:
        pytest.fail(f"sample_{index}: parser={parser.name} error={error}", pytrace=False)
    except Exception as error:  # noqa: BLE001
        kind = type(error).__name__
        pytest.fail(f"sample_{index}: parser={parser.name} crashed with {kind}", pytrace=False)
    result = reconcile(statement)
    sections = ",".join(section.value for section in result.section_mismatches) or "none"
    summary = (
        f"sample_{index}: parser={parser.name} lines={len(statement.lines)} "
        f"off_by_cents={result.difference_cents} sections_differing={sections}"
    )
    if not result.ok:
        pytest.fail(summary, pytrace=False)
    if statement.opening_balance_cents != statement.closing_balance_cents and not statement.lines:
        pytest.fail(f"{summary} (balance moved but no lines were read)", pytrace=False)
    print(summary)
