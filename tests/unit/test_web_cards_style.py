import re
from pathlib import Path

import pytest

import finances.web
from finances.views.format import amount_class

CSS = (Path(finances.web.__file__).parent / "static" / "app.css").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("text", "classes"),
    [
        ("-$12.00", "amount neg"),
        ("+$189.64", "amount pos"),
        ("$3,000.00", "amount"),
        ("$0.00", "amount"),
        ("", "amount"),
        ("-15%", "amount"),
        ("+20%", "amount"),
        ("81%", "amount"),
    ],
)
def test_the_class_of_an_amount_cell(text: str, classes: str) -> None:
    assert amount_class(text) == classes


@pytest.mark.parametrize(
    ("selector", "declaration"),
    [
        ("section.card", "background: var(--surface)"),
        ("section.card table", "background: var(--bg)"),
        ("td.amount.neg", "color: var(--bad)"),
        ("td.amount.pos", "color: var(--good)"),
    ],
)
def test_the_cards_and_colours_come_from_the_stylesheet(selector: str, declaration: str) -> None:
    plain = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    rules = {name.strip(): body for name, body in re.findall(r"([^{}]+)\{([^}]*)\}", plain)}
    assert declaration in rules[selector]
