# Review: Phase 16m

- Verdict: PASS
- Passed: 3060
- Findings: 0
- Approved deviations: None
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `3060 passed`, `All checks passed.` (N + 11 = 3060)
- Given tests plus security, chart library, nav-sync, and charts: `62 passed`
- `git diff --stat HEAD -- src`: only `app.css` and `charts.js`
- `git diff --stat HEAD -- tests`: empty (new test file untracked)
- Given files match the spec blocks (`app.css`, the `charts.js` diff, `test_web_style.py`)

## Requirement checklist

- R1: `test_always_dark`; `test_four_shades_of_dark_from_page_to_hover`; `test_every_colour_comes_from_a_token`; `test_each_part_sits_on_its_layer`; `test_a_soft_purple_accent`; `test_compact_rows`
- R2: `test_charts_take_their_colours_from_the_stylesheet`; `tests/unit/test_chart_library.py`
- R3: full suite 3060 passed; 16k probe `FAILURES 0`

## Probe

16k probe copied outside the repository, run from the root, then deleted.

- `ok   site: started on 127.0.0.1`
- `ok   browser: Chrome or Chromium is installed`
- `ok   browser: three charts drawn`
- `ok   browser: no security policy refusals`
- `FAILURES 0`

Browser look on `fin web serve --port 18766` with a temporary `FIN_DATA_DIR` (8765 was already in use; never the owner's `data/`): the page is near-black, the menu a shade lighter, tables a third shade with raised headings, and Home/Reports in the menu are a soft purple.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. `th` uses `var(--bg)`: `test_each_part_sits_on_its_layer[th---raised]` fails.
2. `h1 { color: #fff; }`: `test_every_colour_comes_from_a_token` finds `#fff`.
3. Pie border `#ffffff`: `test_charts_take_their_colours_from_the_stylesheet` fails.

## Out of scope

Absent: a template change; a light theme or `prefers-color-scheme`; a web font or any `url(`; a change to the chart series colours.
