import colorsys
import re
from pathlib import Path

import pytest

import finances.web

STATIC = Path(finances.web.__file__).parent / "static"
CSS = (STATIC / "app.css").read_text(encoding="utf-8")
ROOT = re.search(r":root\s*\{([^}]*)\}", CSS).group(1)
TOKENS = dict(re.findall(r"--([a-z-]+):\s*([^;]+);", ROOT))
RULES = {
    selector.strip(): body
    for selector, body in re.findall(r"([^{}]+)\{([^}]*)\}", CSS.replace(ROOT, ""))
}


def light(token: str) -> float:
    red, green, blue = (int(TOKENS[token][index : index + 2], 16) for index in (1, 3, 5))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def test_always_dark() -> None:
    assert "color-scheme: dark" in ROOT
    assert "prefers-color-scheme" not in CSS


def test_four_shades_of_dark_from_page_to_hover() -> None:
    shades = ["bg", "surface", "raised", "hover"]
    levels = [light(token) for token in shades]
    assert levels == sorted(levels)
    assert len(set(levels)) == 4
    assert levels[-1] < 60


def test_every_colour_comes_from_a_token() -> None:
    assert set(re.findall(r"var\(--([a-z-]+)\)", CSS)) <= set(TOKENS)
    assert re.findall(r"#[0-9a-fA-F]{3,8}|rgba?\(|hsla?\(", CSS.replace(ROOT, "")) == []


@pytest.mark.parametrize(
    ("selector", "layer"),
    [
        ("body", "--bg"),
        ("nav", "--raised"),
        ("table", "--surface"),
        ("th", "--raised"),
        ("tbody tr:hover td", "--hover"),
    ],
)
def test_each_part_sits_on_its_layer(selector: str, layer: str) -> None:
    assert f"background: var({layer})" in RULES[selector]


def test_a_soft_purple_accent() -> None:
    red, green, blue = (int(TOKENS["accent"][index : index + 2], 16) / 255 for index in (1, 3, 5))
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    assert 250 <= hue * 360 <= 290
    assert saturation < 0.8 and lightness > 0.6


def test_compact_rows() -> None:
    assert "14px" in RULES["body"]
    assert "padding: .32rem .65rem" in RULES["td"]


def test_charts_take_their_colours_from_the_stylesheet() -> None:
    script = (STATIC / "charts.js").read_text(encoding="utf-8")
    for token in ("--muted", "--line", "--surface"):
        assert f'getPropertyValue("{token}")' in script
    assert "#ffffff" not in script
