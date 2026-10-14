"""Opt-in report on the layout of the real statements in data/samples/. Not part of the test run.

Run it yourself, on the machine that holds the statements:

    .venv/bin/python tests/real_samples/describe_layout.py

It answers fixed yes-or-no and how-many questions about each sample, so that a parser spec can be
corrected without anyone reading a statement: can the PDF be read, which parser recognizes it, and
for a Truist statement, where its labels, headings, and rows stand.

Every value it prints is a count, a yes or no, a number of seconds, an exception class name, or a
name written in this file. It never prints a file name, a line of a statement, a description, an
amount, a balance, or a date (AGENTS.md privacy rule 6), and neither may anything added here.
"""

import io
import logging
import re
import sys
import time
from pathlib import Path

from pypdf import PdfReader

from finances.ingest.parsers import registered_parsers
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import StatementError

logging.getLogger("pypdf").setLevel(logging.ERROR)

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"

AMOUNT = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\.[0-9]{2}"
MONEY = rf"(?:[-+=] *)*\$ ?{AMOUNT}"
SHORT_DATE = r"[0-9]{2}/[0-9]{2}"
FULL_DATE = r"[0-9]{2}/[0-9]{2}/[0-9]{4}"
LABELS = {
    "previous_balance": "Your previous balance as of",
    "new_balance": "Your new balance as of",
    "checks_heading": "Checks",
    "withdrawals_heading": "Other withdrawals, debits and service charges",
    "deposits_heading": "Deposits, credits and interest",
    "checks_total": "Total checks",
    "withdrawals_total": "Total other withdrawals, debits and service charges",
    "deposits_total": "Total deposits, credits and interest",
    "withdrawals_heading_first_half": "Other withdrawals, debits and",
    "withdrawals_heading_second_half": "service charges",
    "column_date": "DATE",
    "column_description": "DESCRIPTION",
    "column_amount": "AMOUNT($)",
    "column_check_number": "CHECK #",
    "continued": "continued",
}
SECTIONS = {
    "checks": ("Checks", "Total checks"),
    "withdrawals": (
        "Other withdrawals, debits and service charges",
        "Total other withdrawals, debits and service charges",
    ),
    "deposits": ("Deposits, credits and interest", "Total deposits, credits and interest"),
}


def squeeze(text: str) -> str:
    return "".join(text.split())


def yes(value: object) -> str:
    return "yes" if value else "no"


def cents(text: str) -> int:
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits)


def extract(content: bytes, mode: str) -> tuple[list[str] | None, str]:
    """Return the pages, or None, and a status made of fixed words and an exception class name."""
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as error:  # noqa: BLE001
        return None, f"failed_to_open({type(error).__name__})"
    try:
        if reader.is_encrypted and not reader.decrypt(""):
            return None, "password_protected"
        count = len(reader.pages)
    except Exception as error:  # noqa: BLE001
        return None, f"failed_to_list_pages({type(error).__name__})"
    pages = []
    for number in range(count):
        try:
            pages.append(reader.pages[number].extract_text(extraction_mode=mode) or "")
        except Exception as error:  # noqa: BLE001
            return None, f"failed_on_page_{number + 1}_of_{count}({type(error).__name__})"
    return pages, "ok"


def detected(pages: list[str]) -> str:
    names = []
    for parser in registered_parsers():
        try:
            if pages and parser.detect(pages[0]):
                names.append(parser.name)
        except Exception as error:  # noqa: BLE001
            names.append(f"{parser.name}_crashed({type(error).__name__})")
    return "+".join(names) or "none"


def describe_reading(index: int, content: bytes) -> list[str] | None:
    """Print how the sample reads in both extraction modes. Return the layout pages, if any."""
    found = {}
    for mode in ("layout", "plain"):
        started = time.monotonic()
        pages, status = extract(content, mode)
        seconds = time.monotonic() - started
        found[mode] = pages
        if pages is None:
            print(f"sample_{index}: {mode} read={status} seconds={seconds:.1f}")
            continue
        characters = sum(len(page) for page in pages)
        empty = sum(1 for page in pages if not page.strip())
        print(
            f"sample_{index}: {mode} read=ok pages={len(pages)} empty_pages={empty} "
            f"characters={characters} seconds={seconds:.1f} recognized_by={detected(pages)}"
        )
    return found["layout"]


def describe_label(index: int, name: str, label: str, lines: list[str]) -> None:
    exact = [number for number, line in enumerate(lines) if label in line]
    squeezed_label = squeeze(label)
    loose = [
        number
        for number, line in enumerate(lines)
        if label not in line and squeezed_label in squeeze(line)
    ]
    after = [lines[number].split(label, 1)[1] for number in exact]
    whole = sum(1 for number in exact if lines[number] == label)
    at_start = sum(1 for number in exact if lines[number].startswith(label))
    two_spaces = sum(1 for number in exact if re.search(r"\s\s" + re.escape(label), lines[number]))
    dated = sum(1 for rest in after if re.match(rf"\s+{FULL_DATE}", rest))
    money_same = sum(1 for rest in after if re.search(MONEY, rest))
    amount_same = sum(1 for rest in after if re.search(AMOUNT, rest) and not re.search(MONEY, rest))
    nothing_after = sum(1 for rest in after if not rest.strip())

    def money_follows(number: int, reach: int) -> bool:
        following = [line for line in lines[number + 1 :] if line][:reach]
        return any(re.fullmatch(MONEY, line) or re.fullmatch(AMOUNT, line) for line in following)

    next_line = sum(1 for number in exact if money_follows(number, 1))
    within_three = sum(1 for number in exact if money_follows(number, 3))
    print(
        f"sample_{index}: label[{name}] lines_with_label={len(exact)} "
        f"lines_with_label_only_when_spaces_are_ignored={len(loose)} whole_line={whole} "
        f"at_line_start={at_start} after_two_spaces={two_spaces} followed_by_full_date={dated} "
        f"money_with_dollar_later_on_line={money_same} amount_without_dollar_later_on_line="
        f"{amount_same} nothing_after_label={nothing_after} money_alone_on_next_line={next_line} "
        f"money_alone_within_three_lines={within_three}"
    )


def describe_rows(index: int, lines: list[str]) -> None:
    dated = [line for line in lines if re.match(SHORT_DATE + r"(?![/0-9])", line)]
    as_parsed = sum(1 for line in dated if re.fullmatch(rf"{SHORT_DATE}\s+.+?\s+{AMOUNT}", line))
    with_dollar = sum(1 for line in dated if re.search(rf"\$ ?{AMOUNT}$", line))
    no_amount = sum(1 for line in dated if not re.search(rf"{AMOUNT}$", line))
    trailing_text = sum(1 for line in dated if re.search(rf"{AMOUNT}\s+\S", line))
    several_dates = sum(
        1 for line in lines if len(re.findall(rf"(?<![0-9/]){SHORT_DATE}(?![/0-9])", line)) > 1
    )
    amount_alone = sum(1 for line in lines if re.fullmatch(AMOUNT, line))
    spaced_date = sum(
        1
        for line in lines
        if not re.match(SHORT_DATE, line)
        and re.match(SHORT_DATE, squeeze(line)[:5])
        and " " in line[:6]
    )
    full_dated = sum(1 for line in lines if re.match(FULL_DATE, line))
    print(
        f"sample_{index}: rows lines={len(lines)} blank_lines={lines.count('')} "
        f"start_with_short_date={len(dated)} of_those_shaped_as_the_parser_expects={as_parsed} "
        f"of_those_ending_in_dollar_money={with_dollar} "
        f"of_those_not_ending_in_an_amount={no_amount} "
        f"of_those_with_text_after_the_amount={trailing_text} lines_with_several_short_dates="
        f"{several_dates} lines_that_are_one_amount={amount_alone} "
        f"lines_starting_with_a_date_split_by_spaces={spaced_date} "
        f"start_with_full_date={full_dated}"
    )


def describe_section(index: int, name: str, heading: str, total: str, lines: list[str]) -> None:
    """Count rows between a loosely found heading and its total, and compare with the total."""
    wanted_heading, wanted_total = squeeze(heading), squeeze(total)
    opened = False
    rows = other = sum_cents = 0
    declared = None
    headings = 0
    for line in lines:
        tight = squeeze(line)
        if tight.startswith(wanted_total):
            found = re.search(AMOUNT, line)
            if found is not None and declared is None:
                declared = cents(found.group(0))
            opened = False
        elif tight.startswith("Total"):
            opened = False
        elif tight.startswith(wanted_heading) and not re.search(AMOUNT, line):
            headings += 1
            opened = True
        elif opened:
            amounts = re.findall(rf"(?<![0-9,.]){AMOUNT}(?![0-9])", line)
            if re.match(SHORT_DATE, line) and amounts:
                rows += 1
                per_line = re.findall(rf"{SHORT_DATE}\s+\*?\s*[0-9]+\s+({AMOUNT})", line)
                picked = per_line if name == "checks" and per_line else amounts[-1:]
                sum_cents += sum(cents(text) for text in picked)
            elif line:
                other += 1
    print(
        f"sample_{index}: section[{name}] headings_without_an_amount_spaces_ignored={headings} "
        f"dated_lines_with_an_amount={rows} other_lines_inside={other} "
        f"total_line_found={yes(declared is not None)} "
        f"rows_add_up_to_the_total={yes(declared is not None and declared == sum_cents)}"
    )


def describe_parse(index: int, pages: list[str]) -> None:
    parser = next((item for item in registered_parsers() if item.name == "truist_deposit"), None)
    if parser is None:
        print(f"sample_{index}: parse parser_missing=yes")
        return
    try:
        statement = parser.parse(pages)
    except StatementError as error:
        print(f"sample_{index}: parse error={error}")
        return
    except Exception as error:  # noqa: BLE001
        print(f"sample_{index}: parse crashed={type(error).__name__}")
        return
    result = reconcile(statement)
    by_section = {}
    for line in statement.lines:
        by_section[line.section.value] = by_section.get(line.section.value, 0) + 1
    counts = ",".join(f"{name}:{count}" for name, count in sorted(by_section.items())) or "none"
    declared = ",".join(sorted(item.value for item in statement.declared_section_totals)) or "none"
    differing = ",".join(sorted(item.value for item in result.section_mismatches)) or "none"
    print(
        f"sample_{index}: parse lines={len(statement.lines)} lines_by_section={counts} "
        f"totals_declared={declared} sections_differing={differing} "
        f"balance_moved={yes(statement.opening_balance_cents != statement.closing_balance_cents)} "
        f"reconciles={yes(result.ok)} account_type={statement.account_type.value} "
        f"period_days={(statement.period_end - statement.period_start).days + 1}"
    )


def loose_pattern(label: str) -> re.Pattern[str]:
    """Match the label with any whitespace, or none, between any two of its characters."""
    return re.compile(r"\s*".join(re.escape(character) for character in squeeze(label)))


def describe_spacing(index: int, name: str, label: str, lines: list[str]) -> None:
    """Say how the spacing of a label differs from the way this file writes it."""
    words = re.compile(r"\s+".join(re.escape(word) for word in label.split()))
    tight = squeeze(label)
    exact = sum(1 for line in lines if label in line)
    gaps = sum(1 for line in lines if label not in line and words.search(line))
    inside = sum(
        1
        for line in lines
        if label not in line and not words.search(line) and tight in squeeze(line)
    )
    whole = sum(1 for line in lines if squeeze(line) == tight)
    continued = sum(
        1 for line in lines if squeeze(line) in (tight + "(continued)", tight + "continued")
    )
    starts = [line for line in lines if squeeze(line).startswith(tight)]
    no_amount = sum(1 for line in starts if not re.search(AMOUNT, line))
    one_money = sum(1 for line in starts if len(re.findall(rf"\$ ?{AMOUNT}", line)) == 1)
    print(
        f"sample_{index}: spacing[{name}] as_written={exact} "
        f"only_with_wider_gaps_between_words={gaps} "
        f"only_with_spaces_inside_words={inside} whole_line_spaces_ignored={whole} "
        f"whole_line_plus_continued_spaces_ignored={continued} "
        f"line_starts_with_it_spaces_ignored={len(starts)} of_those_without_an_amount={no_amount} "
        f"of_those_with_exactly_one_dollar_money={one_money}"
    )


def describe_balance_line(index: int, name: str, label: str, lines: list[str]) -> None:
    """Say what stands between a balance label and its money, as counts of character kinds."""
    pattern = loose_pattern(label)
    months = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
    for line in lines:
        found = pattern.search(line)
        if found is None:
            continue
        rest = line[found.end() :]
        between = rest.split("$", 1)[0]
        tight = squeeze(between)
        print(
            f"sample_{index}: balance_line[{name}] characters_before_label={found.start()} "
            f"dollar_signs_after_label={rest.count('$')} between_label_and_dollar: "
            f"digits={sum(c.isdigit() for c in between)} slashes={between.count('/')} "
            f"dashes={between.count('-')} dots={between.count('.')} commas={between.count(',')} "
            f"letters={sum(c.isalpha() for c in between)} "
            f"equals_signs={between.count('=')} spaces={sum(c.isspace() for c in between)} "
            f"starts_with_full_date_spaces_ignored={yes(re.match(FULL_DATE, tight))} "
            f"starts_with_date_of_one_or_two_digit_parts_and_four_digit_year="
            f"{yes(re.match(r'[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}', tight))} "
            f"starts_with_date_with_two_digit_year="
            f"{yes(re.match(r'[0-9]{1,2}/[0-9]{1,2}/[0-9]{2}(?![0-9])', tight))} "
            f"has_a_month_name={yes(any(month in between.lower() for month in months))} "
            f"full_date_as_written_right_after_label={yes(re.match(rf' {FULL_DATE}', rest))}"
        )


def repaired_pages(content: bytes) -> tuple[list[str] | None, int, str]:
    """Read each page in layout mode, or in plain mode when that fails, and narrow wide gaps."""
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted and not reader.decrypt(""):
            return None, 0, "password_protected"
        count = len(reader.pages)
    except Exception as error:  # noqa: BLE001
        return None, 0, f"failed_to_open({type(error).__name__})"
    pages, fallbacks = [], 0
    for number in range(count):
        try:
            text = reader.pages[number].extract_text(extraction_mode="layout") or ""
        except Exception:  # noqa: BLE001
            fallbacks += 1
            try:
                text = reader.pages[number].extract_text() or ""
            except Exception as error:  # noqa: BLE001
                return None, fallbacks, f"failed_on_page_{number + 1}({type(error).__name__})"
        pages.append(re.sub(r"[ \t]{3,}", "  ", text))
    return pages, fallbacks, "ok"


def describe_repaired(index: int, content: bytes) -> None:
    """Say how the sample would parse with the two repairs to PDF reading applied."""
    started = time.monotonic()
    pages, fallbacks, status = repaired_pages(content)
    if pages is None:
        print(f"sample_{index}: repaired read={status}")
        return
    names = detected(pages)
    parser = next((item for item in registered_parsers() if item.name == names), None)
    head = (
        f"sample_{index}: repaired read=ok pages_read_in_plain_mode={fallbacks} "
        f"characters={sum(len(page) for page in pages)} recognized_by={names}"
    )
    if parser is None:
        print(f"{head} seconds={time.monotonic() - started:.1f}")
        return
    try:
        statement = parser.parse(pages)
    except StatementError as error:
        print(f"{head} parse_error={error} seconds={time.monotonic() - started:.1f}")
        return
    except Exception as error:  # noqa: BLE001
        print(
            f"{head} parse_crashed={type(error).__name__} seconds={time.monotonic() - started:.1f}"
        )
        return
    result = reconcile(statement)
    by_section: dict[str, int] = {}
    for line in statement.lines:
        by_section[line.section.value] = by_section.get(line.section.value, 0) + 1
    counts = ",".join(f"{name}:{count}" for name, count in sorted(by_section.items())) or "none"
    declared = ",".join(sorted(item.value for item in statement.declared_section_totals)) or "none"
    differing = ",".join(sorted(item.value for item in result.section_mismatches)) or "none"
    cardholders = len({line.cardholder for line in statement.lines if line.cardholder})
    print(
        f"{head} lines={len(statement.lines)} lines_by_section={counts} totals_declared={declared} "
        f"off_by_cents={result.difference_cents} sections_differing={differing} "
        f"reconciles={yes(result.ok)} cardholders={cardholders} "
        f"seconds={time.monotonic() - started:.1f}"
    )


def describe(index: int, content: bytes) -> None:
    pages = describe_reading(index, content)
    describe_repaired(index, content)
    if pages is None or "truist_deposit" not in detected(pages):
        return
    lines = [line.strip() for page in pages for line in page.splitlines()]
    for name, label in LABELS.items():
        describe_label(index, name, label, lines)
    for name in list(LABELS)[:8]:
        describe_spacing(index, name, LABELS[name], lines)
    for name in ("previous_balance", "new_balance"):
        describe_balance_line(index, name, LABELS[name], lines)
    describe_rows(index, lines)
    for name, (heading, total) in SECTIONS.items():
        describe_section(index, name, heading, total, lines)
    describe_parse(index, pages)


def main(arguments: list[str]) -> int:
    folder = Path(arguments[0]) if arguments else SAMPLES
    files = sorted(folder.glob("*.[pP][dD][fF]")) if folder.is_dir() else []
    if not files:
        print("no PDF files to describe")
        return 0
    for index, path in enumerate(files):
        try:
            describe(index, path.read_bytes())
        except Exception as error:  # noqa: BLE001
            print(f"sample_{index}: report crashed={type(error).__name__}")
    print(f"samples={len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
