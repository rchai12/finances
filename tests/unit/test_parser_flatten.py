from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

import pytest

from finances.ingest.parsers import helpers


@pytest.mark.parametrize(
    ("pages", "expected"),
    [
        pytest.param([], [], id="no-pages"),
        pytest.param([""], [], id="empty-page"),
        pytest.param([" \n\n"], ["", ""], id="blank-lines"),
        pytest.param([" a\r\n b\rc\n"], ["a", "b", "c"], id="line-endings"),
        pytest.param([" one\n\n", "", " two "], ["one", "", "two"], id="page-order"),
        pytest.param(
            [" \tACME  COFFEE\t - $1.00  "],
            ["ACME  COFFEE\t - $1.00"],
            id="internal-columns",
        ),
        pytest.param(["a\nb"], ["a", "b"], id="no-final-newline"),
        pytest.param(["\na\n"], ["", "a"], id="edge-newlines"),
    ],
)
def test_flatten_preserves_lines(pages, expected):
    assert helpers.flatten(pages) == expected


def test_flatten_returns_fresh_list_without_mutating_pages():
    pages = [" one ", "two\n\n"]
    first = helpers.flatten(pages)
    first.append("changed")
    assert pages == [" one ", "two\n\n"]
    assert helpers.flatten(pages) == ["one", "two", ""]


CASES = [
    ("capital_one", "CapitalOneCardParser", "single_card"),
    ("boa", "BoaCardParser", "two_pages"),
    ("citi", "CitiCardParser", "two_cardholders"),
    ("truist", "TruistDepositParser", "checking"),
    ("boa_deposit", "BoaDepositParser", "checking"),
    ("marcus", "MarcusSavingsParser", "basic"),
    ("marcus", "MarcusSavingsParser", "cd"),
]


@pytest.mark.parametrize(
    ("module_name", "class_name", "fixture"),
    CASES,
    ids=["capital-one", "boa-card", "citi", "truist", "boa-deposit", "marcus", "marcus-cd"],
)
def test_parser_uses_shared_flatten(monkeypatch, module_name, class_name, fixture):
    class FlattenReached(Exception):
        pass

    module = import_module("finances.ingest.parsers." + module_name)
    source = (
        Path(__file__).parents[1] / "fixtures" / "statements" / module_name / (fixture + ".txt")
    )
    pages = source.read_text(encoding="utf-8").split("\f")
    error = FlattenReached("shared flatten reached")
    delegate = Mock(side_effect=error)
    monkeypatch.setattr(module, "flatten", delegate, raising=False)
    with pytest.raises(FlattenReached) as stopped:
        getattr(module, class_name)().parse(pages)
    assert stopped.value is error
    delegate.assert_called_once_with(pages)
    assert delegate.call_args.args[0] is pages
