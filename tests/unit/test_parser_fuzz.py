from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from finances.ingest.parsers import detect_parser, registered_parsers
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, StatementError

FIXTURES = Path(__file__).parents[1] / "fixtures" / "statements"
PATHS = sorted(FIXTURES.glob("*/*.txt"))
ODD = [
    " ",
    "−",
    "１",
    "٣",
    "\t",
    "  ",
    "$",
    "-",
    "(",
    ")",
    ",",
    ".",
    "0",
    "9",
    "/",
    "​",
    "é",
    "\x00",
    "+",
    "=",
]


def pages_of(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").split("\f")


def amounts(parsed: ParsedStatement) -> list[tuple[int, str]]:
    return sorted((item.amount_cents, item.section.value) for item in parsed.lines)


def read(pages: list[str]) -> ParsedStatement | None:
    """Parse as an import does. A StatementError means the statement is refused."""
    try:
        return detect_parser(pages).parse(pages)
    except StatementError:
        return None


@st.composite
def damaged(draw: st.DrawFn) -> list[str]:
    pages = [page.split("\n") for page in pages_of(draw(st.sampled_from(PATHS)))]
    for _ in range(draw(st.integers(1, 3))):
        page = draw(st.integers(0, len(pages) - 1))
        lines = pages[page]
        if not lines:
            continue
        index = draw(st.integers(0, len(lines) - 1))
        line = lines[index]
        change = draw(
            st.sampled_from(["drop", "repeat", "swap", "cut", "replace", "insert", "page", "blank"])
        )
        if change == "drop":
            del lines[index]
        elif change == "repeat":
            lines.insert(index, line)
        elif change == "swap":
            other = draw(st.integers(0, len(lines) - 1))
            lines[index], lines[other] = lines[other], lines[index]
        elif change == "cut":
            lines[index] = line[: draw(st.integers(0, len(line)))]
        elif change == "replace" and line:
            at = draw(st.integers(0, len(line) - 1))
            lines[index] = line[:at] + draw(st.sampled_from(ODD)) + line[at + 1 :]
        elif change == "insert":
            at = draw(st.integers(0, len(line)))
            lines[index] = line[:at] + draw(st.sampled_from(ODD)) + line[at:]
        elif change == "page":
            pages.insert(page, [])
        elif change == "blank":
            lines[index] = ""
    return ["\n".join(lines) for lines in pages]


def test_there_is_a_fixture_for_every_parser() -> None:
    names = {parser.name for parser in registered_parsers()}
    found = set()
    for path in PATHS:
        parsed = read(pages_of(path))
        if parsed is not None:
            found.add(parsed.parser_name)
    assert found == names


@settings(max_examples=400)
@given(damaged())
def test_a_damaged_statement_is_read_or_refused_with_a_statement_error(pages: list[str]) -> None:
    for parser in registered_parsers():
        try:
            parsed = parser.parse(pages)
        except StatementError:
            continue
        assert all(type(item.amount_cents) is int for item in parsed.lines)
        assert type(parsed.opening_balance_cents) is int
        assert type(parsed.closing_balance_cents) is int


@pytest.mark.parametrize("path", PATHS, ids=lambda path: f"{path.parent.name}/{path.stem}")
def test_one_edit_never_changes_the_amounts_of_a_statement_that_still_reconciles(
    path: Path,
) -> None:
    pages = pages_of(path)
    original = read(pages)
    if original is None or not reconcile(original).ok:
        return
    expected = amounts(original)
    for page_index, page in enumerate(pages):
        lines = page.split("\n")
        for index, line in enumerate(lines):
            edits = [lines[:index] + lines[index + 1 :]]
            for at, char in enumerate(line):
                if char.isdigit():
                    edited = line[:at] + str((int(char) + 3) % 10) + line[at + 1 :]
                    edits.append(lines[:index] + [edited] + lines[index + 1 :])
            for edit in edits:
                changed = list(pages)
                changed[page_index] = "\n".join(edit)
                parsed = read(changed)
                if parsed is not None and reconcile(parsed).ok:
                    assert amounts(parsed) == expected, (page_index, index)
