# Verify Phase 16n: cards and coloured amounts

Spec: `docs/phases/phase-16n-cards-and-coloured-amounts.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a filter that names an amount cell's class by its sign, used it in every amount cell, wrapped every `<h2>` section of every template in a card, and applied a given CSS diff. Two test files were given; no migration.

These are correct and must not be reported: `amount_class` written with `startswith` or a regular expression; a card's closing tag on its own line or not; whitespace changes inside templates.

## 1. Gates

N is `3060` when Phase 16m was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 28 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_cards.py tests/unit/test_web_cards_style.py --no-cov` | exactly `28 passed` |
| `.venv/bin/python -m pytest tests/unit/test_web_style.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.views.format --cov=finances.web.render --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n '<td class="amount">' -- src/finances/web/templates` | no output |
| `git diff --stat HEAD -- tests` | nothing |

## 2. Scope paths

`git status --short` shows `docs/progress.md`, `src/finances/views/format.py`, `src/finances/web/render.py`, `src/finances/web/static/app.css`, templates under `src/finances/web/templates/`, and the three new test files. The `app.css` diff equals the spec's.

Read `git diff HEAD -- src/finances/web/templates`: every added or changed line adds `<section class="card">`, `</section>`, ` card` to an existing section's class, or `|amount_class` with the `{{ }}` it needs. Any other change (text, rows, links, forms) is a finding.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R6 | gates 1 to 6, and the template diff read in section 2 | pass |
| R4 (edges) | the coder's `tests/integration/test_web_cards_more.py` | each item of the spec's "Tests to write" has a test |

## 4. Probe

None. Look once: start `fin web serve` with `FIN_DATA_DIR` set to a new temporary folder (run `fin db upgrade` there first; never the owner's `data/`) and open `http://127.0.0.1:8765/`. Each section is a card a shade lighter than the page. Report what you saw in one line.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `amount_class` marks any text starting with `-` | `test_the_class_of_an_amount_cell[-15%-amount]` | `amount` | `amount neg` |
| 2. Remove the cards from `backups.html` | `test_every_section_is_a_card[/backups]` | pass | an h2 that does not open a card |
| 3. Move the dashboard's last link (`All insights for ...`) after its card | `test_every_section_is_a_card[/]` | pass | a `<p>` outside the cards |
| 4. Drop the filter from the dashboard's Change cell | `test_amounts_are_coloured_by_sign` | pass | `+$...` with `amount` only |
| 5. Colour every positive amount green | the same | Spent `$...` plain | Spent with `amount pos` |

## 6. Out of scope

Each must be absent: a text, row, link, or form change in a template; colours outside table cells; an inline style or a script.
