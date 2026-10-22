# Verify Phase 16m: a layered dark look

Spec: `docs/phases/phase-16m-layered-dark-look.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder replaced `app.css` with a given file and applied a given diff to `charts.js`. One test file was given. No template or Python changes.

## 1. Gates

N is `3049` when Phase 16l was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 11 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_web_style.py tests/unit/test_web_security.py tests/unit/test_chart_library.py tests/integration/test_web_nav_sync.py tests/integration/test_web_charts.py --no-cov` | all passed |
| `git diff --stat HEAD -- src` | only `src/finances/web/static/app.css` and `src/finances/web/static/charts.js` |
| `git diff --stat HEAD -- tests` | nothing (the new test file is untracked) |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/web/static/app.css
 M src/finances/web/static/charts.js
?? tests/unit/test_web_style.py
```

`app.css` equals the spec's block byte for byte; the `charts.js` diff equals the spec's diff; the test file equals its block.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1, R2 | gate 2, and the comparisons in section 2 | pass |
| R3 | gate 1, and the probe | pass |

## 4. Probe

Run Phase 16k's probe unchanged: copy the Python block from `docs/verification/phase-16k-charts.md`, section 4, to a file outside the repository and run it from the repository root with `.venv/bin/python`. Expected: `FAILURES 0` (the three charts draw with the new `charts.js`).

Then look once: start `fin web serve` with `FIN_DATA_DIR` set to a new temporary folder (never the owner's `data/`), run `fin db upgrade` there first, and open `http://127.0.0.1:8765/` in a browser. The menu, tables, and page are three visibly different shades of dark, and the current page in the menu is purple. Report what you saw in one line.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. Give `th` the page's background (`var(--bg)`) | `test_each_part_sits_on_its_layer[th---raised]` | pass | fail |
| 2. Write a literal colour in a rule (`color: #fff` on `h1`) | `test_every_colour_comes_from_a_token` | pass | fail |
| 3. Put `#ffffff` back as the pie's border in `charts.js` | `test_charts_take_their_colours_from_the_stylesheet` | pass | fail |

## 6. Out of scope

Each must be absent: a template change; a light theme or `prefers-color-scheme`; a web font or any `url(`; a change to the chart series colours.
