# Phase 47e: shared parser line flattening

## Goal

Replace six identical page-to-line expressions with one helper, preserving every
parser's records, section totals, detection and reconciliation. The accepted
remediation design section 47e settles the behavior; no new owner choice is needed.
Architect decisions (2026-11-16): one small refactor, one public helper, sixteen
given cases and coder-owned compatibility cases. Production diff is expected to
be a few dozen lines. No fixture-loader extraction is needed for this change.

## Read first

AGENTS.md, docs/architecture.md, docs/phase-conventions.md, docs/testing.md,
docs/progress.md, docs/audit-remediation-design.md (47e), the seven production
files in Scope, tests/unit/test_parser_helpers.py, tests/unit/test_find_labeled_amount.py,
tests/unit/test_marcus_cd.py, and the six parsers' existing synthetic tests.

## Starting state and checked facts

Predecessor 47d is implemented at 949e31d and approved at
`cf3c2c0c10522dbcaf55e5cc7243346d66715b0a`. Progress and independent review agree:
**N = 4514**. **Sections: parsers.** Migration remains 0026_proposal_findings.py.

Each of capital_one, boa, citi, truist, marcus and boa_deposit has exactly one
`[line.strip() for page in pages for line in page.splitlines()]` in parse().
MarcusSavingsParser handles both savings and CD headings through the same parse
method. Detection remains a separate method receiving first_page. Helpers is
already a critical module; existing money/date/labeled-amount tests must remain
unchanged and retain full line/branch coverage alongside the new given tests.

Checked the eight literal line expectations against the existing expression in
a fresh predecessor clone. All match. All seven synthetic bases used by the given
delegation test already parse and reconcile. Sixteen given cases collect: nine
fail for the missing helper attribute and seven for bypassing the patched helper.
They pass lint/format checks. No reference implementation or full suite was run
for this planning assignment; no real statements were inspected.

### Planning baseline and isolation

The owner commits finalized spec/guide before coding. Preserve unrelated untracked
.vscode/settings.json. Start in a fresh isolated clone of that planning commit,
link the existing venv, exclude only its symlink locally, and set PYTHONPATH to
that clone's src on every Python invocation. Record full planning SHA and confirm
finances.__file__ resolves there; spec/guide must equal HEAD and status must start
clean. Use .agents/skills/phase-architect/references/handoffs.md. Do not mix editor
settings or unrelated work into phase scope.

## Scope

| Path | What changes |
|---|---|
| src/finances/ingest/parsers/helpers.py | add flatten only |
| src/finances/ingest/parsers/capital_one.py | import helper, replace one expression |
| src/finances/ingest/parsers/boa.py | import helper, replace one expression |
| src/finances/ingest/parsers/citi.py | import helper, replace one expression |
| src/finances/ingest/parsers/truist.py | import helper, replace one expression |
| src/finances/ingest/parsers/marcus.py | import helper, replace one expression for savings and CD |
| src/finances/ingest/parsers/boa_deposit.py | import helper, replace one expression |
| tests/unit/test_parser_flatten.py | new: given sixteen cases |
| tests/unit/test_parser_flatten_compatibility.py | new: coder compatibility tests |
| docs/progress.md | append phase entry |

Both new files match the existing parsers section pattern; no section-config edit.

## Out of scope

Parsing/detection changes, date/money/sign rules, new bank support, new fixtures,
fixture-loader cleanup, parser inheritance or section-walker frameworks, OCR,
PDF extraction, migrations, dependencies and all later audit-remediation parts.
Existing tests and fixtures stay unchanged; no earlier-test diff or migration.

## Dependencies

None new. Use the existing venv and approved local worker dependency.

## Requirements

- **R1.** Add `flatten(pages: list[str]) -> list[str]` in helpers.py. In page and
  then line order, return each page.splitlines() line stripped with str.strip().
  Preserve interior spaces/tabs, signs, dates, blank lines as empty strings, and
  repeated lines. No page separator is inserted and pages are not joined first.
  Return a fresh list, without mutating input or retaining shared output state.
- **R2.** Empty pages produce no lines. A final newline does not invent a trailing
  blank line, while actual blank lines do remain. Retain Python splitlines()
  behavior including CRLF, CR and Unicode line boundaries; use no new validation,
  normalization, truncation, encoding or exception policy.
- **R3.** All six parse methods import `flatten` into their module and call it once
  with the original pages object at the former expression's position. Remove
  those duplicated expressions; use the helper's returned lines for all later
  parsing. Preserve the patchable module-level flatten seam in the given tests.
  Marcus CD reaches the same helper. detect() stays independent and unchanged.
- **R4.** All existing synthetic layouts retain complete ParsedStatement values:
  header/account/period fields, balances, ordered StatementLine values,
  cardholders, sections and section totals. Reconciliation results and existing
  refusal messages remain identical. Do not adjust tests to accommodate changes.
- **R5.** Keep all pre-existing helpers unchanged. helpers.py remains at 100%
  line and branch coverage, with assertions for new behavior. Full previous suite,
  critical gates, privacy and offline operation remain intact.

## Given tests

Sixteen cases, copied unchanged to tests/unit/test_parser_flatten.py. The seven
parser cases use existing synthetic fixture files. A distinct exception proves
entry into the helper even if a missing feature were represented by a stub;
ordinary parsing or schema errors cannot count as success. The nine direct helper
cases pin literal values and nonmutation rather than deriving expected lines from
flatten itself. Existing critical-helper tests remain the complete regression
contract for helpers not changed here.

```python
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
```

## Tests to write

`tests/unit/test_parser_flatten_compatibility.py` (parsers):

- R1/R2: repeated identical lines across pages stay repeated; whitespace-only
  Unicode lines become empty strings; Unicode line separators retain splitlines
  semantics; adjacent non-newline pages such as ["left", "right"] stay two lines.
  Assert literal expected values. Empty and nonempty calls do not share state.
- R3/R4: full-result compatibility matrix for all six parsers, explicitly Marcus
  basic and CD, using the seven given bases. Save a statement obtained by patching
  the parser's flatten lookup to the exact predecessor expression, then restore
  the real helper and compare complete ParsedStatement and reconcile results.
  This is a narrow legacy-expression characterization, not an oracle implemented
  with the new helper. Preserve the existing independent literal fixture assertions
  in earlier tests. Do not compare only counts, total amounts or parser names.
- R4: apply CRLF endings and distribute unchanged fixture lines across several
  pages, including an empty page, without merging/splitting a line. On those seven
  bases assert complete result and reconciliation equal the unmodified base.
  Keep marker/detection checks on original first_page; parser parse accepts the
  page segmentation directly. Preserve internal column whitespace.
- R3: wrap the actual module-level flatten with a spy for all seven bases; assert
  exactly one call with the original pages object and successful complete parsing.
  This complements the given exception case and catches ignoring the helper's
  return. Prove return use by giving that seam an empty list for an otherwise valid
  base: assert its existing parser-specific missing-header StatementError, not a
  successful parse from a second inline flatten operation.
- R4/R5: existing invalid fixtures (Marcus amount_mismatch and cross-bank inputs)
  preserve their documented parse/reconciliation refusals under the old-expression
  and new-helper paths. Distinguish a failed reconciliation from a parse error;
  do not invent a stricter acceptance rule or change existing fixtures.

## Rules for this phase

Synthetic fixtures only; never access data/samples, real databases or Keychain.
No network. Integer cents, existing money/date parsing and reconciliation remain
unchanged. Do not alter critical_modules.txt, test configuration or dependencies.
The only new public name is finances.ingest.parsers.helpers.flatten.

## Acceptance

From the isolated planning-baseline checkout, sequentially with preserved exit
codes and logs:

1. `.venv/bin/python scripts/check.py --first parsers --workers 4`: final
   `All checks passed.`, at least **4530** full-suite passes (4514+16 plus coder
   cases), every section zero failures/skips, no xfails or warnings summary.
   Four workers follow the accepted machine recommendation; a serial override
   requires a documented resource reason. One coverage-producing run per checkout.
2. Immediately `.venv/bin/python -m coverage report --include="*/finances/ingest/parsers/helpers.py" --fail-under=100`:
   exit 0, helper and TOTAL at 100%, no missing line or branch. All other critical
   modules and configured overall coverage must also pass the full check.
3. `.venv/bin/python -m pytest tests/unit/test_parser_flatten.py --no-cov`:
   exactly sixteen passed.
4. Inspect `git status --short --untracked-files=all` and `git diff HEAD`: only
   the ten Scope paths (verifier additionally writes its review), given bytes
   identical, earlier tests/fixtures unchanged. Inspect source for only helper
   addition, imports and six substitutions. No new search gate or probe.

## Report

Follow phase-conventions.md, headed Phase 47e: shared parser line flattening.
Record N/final/given counts, public name, source provenance, six caller/seven-base
coverage and any isolation/environment issue. Do not commit or push.
