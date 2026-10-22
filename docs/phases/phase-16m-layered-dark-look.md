# Phase 16m: a layered dark look

## Goal

The web pages stop running together. Today `app.css` sets `color-scheme: light dark` and no backgrounds, so in dark mode every part of every page is the same black, divided only by faint lines. After this phase the site is **always dark**, built from four shades: the page, a surface for tables and charts, a raised shade for the menu and table headings, and a hover shade. It has one **soft purple** accent (links, the current page, focus, the main buttons), **compact** rows, styled inputs and buttons, and messages shown as banners. Charts take their text, grid, and slice-edge colours from the same stylesheet.

The owner chose this look from a mock-up of the real pages (dark only, several shades, a softer purple instead of bright blue, compact). Cards around sections and coloured amounts need template changes and are Phase 16n.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/web/static/app.css`, `src/finances/web/static/charts.js`; `tests/unit/test_web_security.py` (the stylesheet has no `@import` or `url(`), `tests/unit/test_chart_library.py` (words `charts.js` must not contain), `tests/integration/test_web_nav_sync.py` (the `nav .nav-sync` rule)

## Starting state

N is `3049` when Phase 16l is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/static/app.css` | replaced by the given file |
| `src/finances/web/static/charts.js` | the given diff |
| `tests/unit/test_web_style.py` | new: given |
| `docs/progress.md` | one new entry |

No template, route, or Python module changes.

## Out of scope

- Template changes of any kind: cards around sections, coloured amounts, badges, stat tiles (16n).
- A light theme or a theme switch; web fonts (the app makes no network calls, so the system's fonts stay); new colours in the chart series.

## Dependencies

None new. No migration.

## Requirements

- **R1.** `app.css` is the given file, exactly. Its `:root` holds every colour as a token and sets `color-scheme: dark`; no rule outside `:root` writes a colour literally; there is no `prefers-color-scheme` block. It keeps 16l's `nav .nav-sync { margin: 0 0 0 auto; }` and has no `@import` or `url(`.
- **R2.** `charts.js` gets the given diff: it reads `--muted`, `--line`, and `--surface` from the page's computed style, sets them as Chart.js's default text and border colours, and draws pie slice edges in `--surface` instead of white. Nothing else in it changes, and it still contains none of the words `tests/unit/test_chart_library.py` forbids.
- **R3.** Every earlier test passes unchanged, and 16k's browser probe (its guide, section 4) still prints `FAILURES 0`: the three charts draw under the site's script policy.

## Given files

`src/finances/web/static/app.css` (replace the file with this; do not change it)

```css
/* Layered dark: page < surface < raised < hover. One soft purple accent; compact rows. */
:root {
  color-scheme: dark;
  --bg: #111017;
  --surface: #18171f;
  --raised: #201f29;
  --hover: #292734;
  --line: #2f2d3b;
  --line-soft: #252431;
  --fg: #e6e4ee;
  --muted: #9895a8;
  --faint: #6e6b7e;
  --accent: #b3a1ee;
  --accent-fill: #6f5bc4;
  --accent-tint: #b3a1ee1f;
  --good: #7fcf9f;
  --bad: #ef8f8f;
  --warn: #e2c27e;
  --radius: 8px;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

nav { position: sticky; top: 0; z-index: 5; display: flex; flex-wrap: wrap; align-items: center; gap: .15rem; padding: .5rem 1rem; background: var(--raised); border-bottom: 1px solid var(--line); }
nav .brand { font-weight: 650; letter-spacing: .02em; margin-right: .9rem; color: var(--fg); }
nav a { color: var(--muted); padding: .3rem .6rem; border-radius: 6px; }
nav a:hover { color: var(--fg); background: var(--hover); text-decoration: none; }
nav a[aria-current="page"] { color: var(--accent); background: var(--accent-tint); font-weight: 600; }
nav .nav-sync { margin: 0 0 0 auto; }

main { max-width: 76rem; margin: 0 auto; padding: 1.25rem 1rem 3rem; overflow-x: auto; }
h1 { font-size: 1.35rem; font-weight: 650; margin: .25rem 0 1rem; }
h2 { font-size: .95rem; font-weight: 600; margin: 1.75rem 0 .6rem; }
h3 { font-size: .9rem; font-weight: 600; margin: 1rem 0 .4rem; color: var(--muted); }

table { width: 100%; border-collapse: separate; border-spacing: 0; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; margin: .4rem 0 .75rem; }
th { background: var(--raised); color: var(--muted); font-size: .74rem; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; text-align: left; padding: .45rem .65rem; border-bottom: 1px solid var(--line); white-space: nowrap; }
td { padding: .32rem .65rem; border-bottom: 1px solid var(--line-soft); vertical-align: middle; }
tbody tr:last-child td { border-bottom: 0; }
tbody tr:hover td { background: var(--hover); }
td.amount, th.amount { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
table.detail { width: auto; }
table.detail th { background: none; text-transform: none; letter-spacing: 0; font-size: .85rem; font-weight: 400; padding-right: 1.5rem; }

input, select, button { font: inherit; color: var(--fg); }
input, select { background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: .28rem .5rem; }
input:focus, select:focus, button:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
button { background: var(--accent-fill); border: 1px solid transparent; border-radius: 6px; padding: .3rem .8rem; font-weight: 600; cursor: pointer; }
button:hover { filter: brightness(1.12); }
form.inline button, td button { background: var(--hover); border-color: var(--line); font-weight: 500; padding: .15rem .55rem; font-size: .85rem; }
.fields, .filters { display: flex; flex-wrap: wrap; align-items: end; gap: .6rem; margin: .4rem 0 1rem; }
.fields label, .filters label { display: flex; flex-direction: column; gap: .2rem; font-size: .78rem; color: var(--muted); }
.fields label.check { flex-direction: row; align-items: center; gap: .35rem; }
form.inline { display: inline; }

p { margin: .35rem 0; }
.summary { color: var(--fg); }
.empty, .hint { color: var(--muted); }
.hint { font-size: .88rem; }
.notice, .error, .attention { padding: .45rem .75rem; border-radius: 6px; background: var(--surface); border-left: 3px solid var(--accent); }
.error { border-left-color: var(--bad); color: var(--bad); }
.attention { border-left-color: var(--warn); }
.attention a { color: var(--fg); }
ul.links li { margin: .3rem 0; }
section.map { border-top: 1px solid var(--line); margin-top: 1rem; }
.chart { max-width: 32rem; margin: .5rem 0 1rem; padding: .75rem; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
```

`src/finances/web/static/charts.js`: apply this diff exactly.

```text
diff --git a/src/finances/web/static/charts.js b/src/finances/web/static/charts.js
index 6a32880..65acb58 100644
--- a/src/finances/web/static/charts.js
+++ b/src/finances/web/static/charts.js
@@ -3,6 +3,10 @@
 // "series": [{"name": ..., "cents": [...]}]}. Money stays in whole cents until it is shown.
 (function () {
   "use strict";
+  var styles = getComputedStyle(document.documentElement);
+  var surface = styles.getPropertyValue("--surface").trim();
+  Chart.defaults.color = styles.getPropertyValue("--muted").trim();
+  Chart.defaults.borderColor = styles.getPropertyValue("--line").trim();
   var dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
   var colors = ["#2f6f9f", "#c0612b", "#4b8b3b", "#8a5aa8", "#b8963a", "#3a8f8a", "#a8485a", "#6b6b6b"];
 
@@ -17,7 +21,7 @@
         label: series.name,
         data: series.cents.map(function (cents) { return cents / 100; }),
         backgroundColor: pie ? colors : colors[index % colors.length],
-        borderColor: pie ? "#ffffff" : colors[index % colors.length],
+        borderColor: pie ? surface : colors[index % colors.length],
       };
     });
     var options = {
```

## Given tests

11 tests in one file. They read the two static files: dark only; four shades that lighten from the page to the hover row; every colour from a token; each part on its layer; a soft purple accent; compact rows; charts coloured from the stylesheet. Later phases must keep them passing.

`tests/unit/test_web_style.py`

```python
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
```

## Tests to write

None. The architect ran the whole suite with the given files (all passed) and 16k's probe (`FAILURES 0`).

## Rules for this phase

- No inline style, no `<style>` element, no script outside `charts.js`: the site's policy allows only its own files.
- Every earlier test passes unchanged.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file: `tests/unit/test_web_style.py`, 11 tests; at least N + 11 passed in all;
- `git diff --stat HEAD -- src`: only `app.css` and `charts.js`;
- 16k's probe: `FAILURES 0`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 16m: a layered dark look (YYYY-MM-DD)`.
