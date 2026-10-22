# Review: Phase 16n

- Verdict: PASS
- Passed: 3093
- Findings: 0
- Approved deviations: None
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `3093 passed`, `All checks passed.` (N + 28 = 3088; extra 5)
- Given tests: `28 passed`
- `tests/unit/test_web_style.py`: `11 passed`
- Coverage of `finances.views.format` and `finances.web.render`: `Required test coverage of 100% reached`
- `git grep -n '<td class="amount">' -- src/finances/web/templates`: no output
- `git diff --stat HEAD -- tests`: empty (new test files untracked)
- Given files match the spec blocks (`test_web_cards.py`, `test_web_cards_style.py`); `app.css` diff equals the spec's

Also present in the working tree, not part of this implementation: `.claude/skills/phase-architect/SKILL.md`, `docs/roadmap.md`, and the 16n spec and verification files.

## Requirement checklist

- R1: `test_the_class_of_an_amount_cell`
- R2: `test_amounts_are_coloured_by_sign` (the filter is registered on `_TEMPLATES.env`)
- R3: `test_amounts_are_coloured_by_sign`; leftover `<td class="amount">` search empty
- R4: `test_every_section_is_a_card`; extra tests in `tests/integration/test_web_cards_more.py` (map card, error and not-migrated pages, empty Home, Ahead with nothing expected)
- R5: `test_the_cards_and_colours_come_from_the_stylesheet`; `test_web_style.py`
- R6: full suite 3093 passed

## Probe

None.

Browser look on `fin web serve --port 18767` with a temporary `FIN_DATA_DIR` (never the owner's `data/`): each of the six Home sections is a card a shade lighter than the page (`rgb(24, 23, 31)` on `rgb(17, 16, 23)`).

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. `amount_class` marks any text starting with `-`: `test_the_class_of_an_amount_cell[-15%-amount]` fails (`amount neg`).
2. Cards removed from `backups.html`: `test_every_section_is_a_card[/backups]` fails (`an h2 that does not open a card`).
3. Dashboard last insights link after its card: `test_every_section_is_a_card[/]` fails (`a <p> outside the cards`).
4. Filter dropped from the dashboard Change cell: `test_amounts_are_coloured_by_sign` fails (`+$...` with `amount` only).
5. Every `$` amount coloured green: the same test fails (Spent `$...` with `amount pos`).

## Out of scope

Absent: a text, row, link, or form change in a template; colours outside table cells; an inline style or a script added by this phase.
