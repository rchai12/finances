from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

import pytest

from finances.ingest.parsers import helpers
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import StatementError
from tests.unit.test_parser_flatten import CASES

ROOT = Path(__file__).parents[1] / "fixtures/statements"
ERRORS = {
    "capital_one": "capital one: card ending not found",
    "boa": "boa: account number not found",
    "citi": "citi: account number not found",
    "truist": "truist: account line not found",
    "boa_deposit": "boa_deposit: account number not found",
    "marcus": "marcus: account number not found",
}


def pages(bank, fixture):
    return (ROOT / bank / f"{fixture}.txt").read_text(encoding="utf-8").split("\f")


def legacy(pages):
    return [line.strip() for page in pages for line in page.splitlines()]


@pytest.mark.parametrize(
    "source,expected",
    [
        (["same\nsame", "same"], ["same", "same", "same"]),
        (["\u00a0\u2003\n\t\u00a0"], ["", ""]),
        ([" a\u2028 b\u2029 c\x85 d\v e\f f"], ["a", "b", "c", "d", "e", "f"]),
        (["left", "right"], ["left", "right"]),
    ],
)
def test_literal_boundaries_and_repeated_lines(source, expected):
    assert helpers.flatten(source) == expected


def test_empty_and_nonempty_calls_have_no_shared_state():
    empty = helpers.flatten([])
    full = helpers.flatten([" a "])
    empty.append("changed")
    full.clear()
    assert helpers.flatten([""]) == []
    assert helpers.flatten([" a "]) == ["a"]


@pytest.mark.parametrize("bank,class_name,fixture", CASES)
def test_full_statements_and_reconciliation_match_legacy(monkeypatch, bank, class_name, fixture):
    module = import_module("finances.ingest.parsers." + bank)
    parser = getattr(module, class_name)()
    source = pages(bank, fixture)
    with monkeypatch.context() as patch:
        patch.setattr(module, "flatten", legacy)
        expected = parser.parse(source)
    actual = parser.parse(source)
    assert actual == expected
    assert reconcile(actual) == reconcile(expected)
    assert reconcile(actual).ok


@pytest.mark.parametrize("bank,class_name,fixture", CASES)
def test_crlf_repagination_preserves_complete_results(bank, class_name, fixture):
    module = import_module("finances.ingest.parsers." + bank)
    parser = getattr(module, class_name)()
    source = pages(bank, fixture)
    expected = parser.parse(source)
    lines = [line for page in source for line in page.splitlines()]
    first = len(lines) // 3
    second = 2 * len(lines) // 3
    segmented = [
        "\r\n".join(lines[:first]),
        "",
        "\r\n".join(lines[first:second]),
        "\r\n".join(lines[second:]),
    ]
    assert parser.detect(source[0])
    actual = parser.parse(segmented)
    assert actual == expected
    assert reconcile(actual) == reconcile(expected)


@pytest.mark.parametrize("bank,class_name,fixture", CASES)
def test_successful_spy_and_empty_return_use(monkeypatch, bank, class_name, fixture):
    module = import_module("finances.ingest.parsers." + bank)
    parser = getattr(module, class_name)()
    source = pages(bank, fixture)
    expected = parser.parse(source)
    spy = Mock(wraps=module.flatten)
    monkeypatch.setattr(module, "flatten", spy)
    assert parser.detect(source[0])
    spy.assert_not_called()
    actual = parser.parse(source)
    assert actual == expected and reconcile(actual) == reconcile(expected)
    spy.assert_called_once_with(source)
    assert spy.call_args.args[0] is source
    empty = Mock(return_value=[])
    monkeypatch.setattr(module, "flatten", empty)
    with pytest.raises(StatementError) as stopped:
        parser.parse(source)
    assert str(stopped.value) == ERRORS[bank]
    empty.assert_called_once_with(source)
    assert empty.call_args.args[0] is source


@pytest.mark.parametrize("bank,class_name,fixture", CASES)
def test_cross_bank_refusal_matches_legacy(monkeypatch, bank, class_name, fixture):
    module = import_module("finances.ingest.parsers." + bank)
    parser = getattr(module, class_name)()
    source = pages("capital_one", "single_card") if bank == "marcus" else pages("marcus", "basic")
    assert not parser.detect(source[0])
    messages = []
    for flatten in (legacy, helpers.flatten):
        monkeypatch.setattr(module, "flatten", flatten)
        with pytest.raises(StatementError) as stopped:
            parser.parse(source)
        messages.append(str(stopped.value))
    assert messages == [ERRORS[bank], ERRORS[bank]]


def test_marcus_amount_mismatch_is_parse_refusal_not_reconciliation(monkeypatch):
    module = import_module("finances.ingest.parsers.marcus")
    source = pages("marcus", "amount_mismatch")
    for flatten in (legacy, helpers.flatten):
        monkeypatch.setattr(module, "flatten", flatten)
        assert module.MarcusSavingsParser().detect(source[0])
        with pytest.raises(StatementError) as stopped:
            module.MarcusSavingsParser().parse(source)
        assert str(stopped.value) == "marcus: row 2 does not match its balance"
