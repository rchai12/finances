# Verify Phase 45c: a link for every History record

Spec: `docs/phases/phase-45c-history-links.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder gave `change_link` a link for the four kinds it lacked (proposal, alias, settlement, finding), made it give None for any other kind, and applied the given template diff so such a record shows as plain text. One test file and the template diff were given.

These are correct and must not be reported: a module-level regular expression for the month; the finding case written apart from the table of fixed links.

## 1. Gates

N is `4291` when Phase 45b was the last phase built. Sections: web.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first web` | last line `All checks passed.`; the summary lists `tests (web): passed`; at least N + 11 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table |
| `.venv/bin/python -m pytest tests/integration/test_web_history_links.py --no-cov` | exactly `11 passed` |
| `.venv/bin/python -m coverage report --include="*/finances/views/audit.py,*/finances/web/routes/history.py" --fail-under=100` | exit 0, `TOTAL` at `100%` |
| `git diff --stat HEAD -- tests` | nothing |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, `src/finances/views/audit.py`, the template, and the given test file. The template diff and the given test file equal the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_the_kinds_that_had_no_link`, `test_every_kind_has_a_link`, `test_the_page_shows_a_proposal_and_a_finding`); gate 1 (`test_web_history.py`) | pass |
| R2 | gate 2 (`test_a_kind_with_no_link_gives_none`) | pass |
| R3 | gate 2 (`test_a_kind_with_no_link_shows_as_plain_text`) | pass |

## 4. Probe

None.

## 5. Spot checks

Each row below is one change to the named function. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. the finding's month read from `after` only | given `test_the_kinds_that_had_no_link` (before `interest in 2026-06`, after None) | `/insights?month=2026-06` | `/insights` |
| 2. the month taken as the text's last seven characters | the same test (`interest in every month`) | `/insights` | `/insights?month=y month` |
| 3. an unknown kind still looked up in the table | given `test_a_kind_with_no_link_gives_none` | None | `KeyError` |
| 4. the template links every cell | given `test_a_kind_with_no_link_shows_as_plain_text` | `<td>nope 9</td>` | `<td><a href="None">nope 9</a></td>` |

## 6. Out of scope

Each must be absent: a link to one proposal, alias, or settlement; a change to `fin audit`; an earlier test changed.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
