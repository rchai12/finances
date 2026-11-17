# Phase 47i: tighten view import guards and document testing conventions

## Goal

Remove stale file-wide view guard exemptions and document how tests are named,
organized and timed. Preserve every existing behavior case and section assignment.
No owner decision is required: audit-remediation-design section47i already fixes
this scope. Architect decision (2026-11-17): no test moves are justified here;
keep all node ids, filenames and section patterns, and add focused guard tests.

## Read first

AGENTS.md, docs/architecture.md, docs/testing.md, docs/phase-conventions.md,
docs/progress.md, audit-remediation-design/verification section47i; the 47h4 review;
tests/unit/test_views_take_data.py; views/sync.py, backups.py, transfers.py;
tests/sections.toml. No product modules need modification.

## Starting state

47h4 is committed and independently PASS at **4790** tests, no findings or
deviations. Review commit733cbd4790539d55ce76736fec42c00b759419eb; implementation
98188a8. **N=4790; Sections: core.** Latest migration0026_proposal_findings.py.
There are29 Python view files. Current guard scans direct files, forbids imports
from db/sync/keyring/sqlalchemy but exempts backups.py, sync.py and transfers.py
entirely through STILL_LOADING. Only sync.py currently imports a guarded root:
`from finances.sync.runner import LinkRun`, a result dataclass. Analysis imports
in backups/transfers are result types, not database IO. Existing formatting tests
and all source remain unchanged. New unit test names fall in existing core section.

Commit finalized planning docs before coding. Record full planning SHA, confirm
spec/guide match committed bytes; use fresh isolated clone due to unrelated
.vscode/settings.json. Link existing venv, exclude symlink locally, set clone/src
PYTHONPATH and confirm finances.__file__ resolves there. Baseline collection
snapshot must be captured before any implementation, outside repository.

## Scope

| Path | Change |
|---|---|
| docs/testing.md | Naming/layer guidance and honest timing description; result-type coupling explanation |
| tests/unit/test_views_take_data.py | Replace stale constant/guard only; optional private guard helpers |
| tests/unit/test_view_import_guard.py | New given sixteen cases |
| tests/unit/test_view_import_guard_behavior.py | New coder guard cases |
| docs/progress.md | Append phase entry |

## Out of scope

All src files, dependencies/configuration, scripts/check.py and section patterns,
result-type relocation, rename/deduplication campaigns, 47j lock timeout work,
MCP size guard cleanup, changes to any previous behavior assertion or node id.

## Dependencies

None new. No migration, source implementation, service or network access.

## Design

Keep existing function name `test_only_the_frozen_views_still_load_data` and its
VIEWS Path patch point despite its historical name (no test rename this phase).
Replace STILL_LOADING with exact constant:
`PERMITTED_RESULT_IMPORTS = {("sync.py", "finances.sync.runner", "LinkRun")}`.
No file-wide or module-wide exceptions. Scan VIEWS.rglob("*.py") and parse ASTs,
including nested imports and files; paths relative to VIEWS use as_posix().

Reject imports rooted at finances.db, finances.sync, keyring or sqlalchemy,
including submodules, plain imports and from-parent forms (`from finances import
db`/sync). Match root boundaries, not unrelated names beginning with the same
letters. For every imported symbol in an ImportFrom inspect the effective target;
only the exact sync.py/module/LinkRun tuple is permitted, with optional alias.
Mixed imports containing LinkRun plus another symbol must fail. Wildcard, plain
module imports and the same result type imported in another file are forbidden.
Nested relative path sync.py does not inherit root sync.py's exception. Relative
imports resolving to forbidden roots are rejected. Private helper signatures and
diagnostic text are coder-owned; report at least offending relative path/import,
without executing planted code. Malformed Python may fail closed as SyntaxError.
This is an AST import dependency guard, not a sandbox against dynamic Python.
No claim that permitting LinkRun proves arbitrary calling code is IO-free.

Preserve guard against DB access in every view. Existing analysis result-type
imports remain allowed: coupling to a service's return data is not proof of IO.
Do not move result classes or import application services during guard scans.
Keep existing seven formatting tests and fixtures unchanged. Retain every old
collected node id, including guard node; only two new test files add nodes.

Testing docs changes:
- New tests use descriptive behavior names in the appropriate layer. Keep module
  context in filenames; existing *_more.py files stay valid. A bug fix need not
  rename unrelated tests or duplicate a whole workflow at every layer.
- Deliberate future moves require exact old/new node map, updated section/import
  references and no lost cases/assertions. Front-end regressions remain useful.
- Replace '<10s total' unit-layer timing claim: historical aspiration, not measured
  gate. Timing evidence belongs in docs/testing-performance.md; keep deterministic
  offline and appropriate-layer rules, coverage85/critical100 and checks intact.
- Explain exact result-type exception/coupling and guard limits; a type move waits
  until its service/view contract changes. Do not claim all views already lack
  service imports or all tests run in a particular elapsed time.

## Requirements

- R1: exact single-symbol exception replaces three broad exemptions.
- R2: forbidden imports detected across recursive files/scopes and supported import forms.
- R3: result dataclass imports remain valid; view/source/output behavior unchanged.
- R4: docs give descriptive/layer naming, legacy *_more support, exact future move accounting and honest timing/coverage policy.
- R5: existing node ids and section assignments retained; full acceptance and scope hold.

## Given diff to earlier tests

No fixed patch: replacing the old guard is the implementation. Edit only
STILL_LOADING's assignment, the existing guard function body, and any new private
helpers/imports needed for that guard. Keep VIEWS and all existing test names,
formatting assertions and fixture values unchanged. No other earlier test file
changes. No test moves; identity map old node -> same node applies to all4790.

## Given tests

Sixteen cases in tests/unit/test_view_import_guard.py, copied unchanged:

```python
import pytest

from tests.unit import test_views_take_data as guard


@pytest.mark.parametrize(
    "filename,source",
    [
        ("backups.py", "from finances.db import engine"),
        ("sync.py", "from finances.db.engine import get_engine"),
        ("transfers.py", "from sqlalchemy import select"),
        ("accounts.py", "import keyring"),
        ("sync.py", "from finances.sync.runner import run_links"),
        ("sync.py", "from finances.sync.runner import LinkRun, run_links"),
        ("backups.py", "from finances.sync.runner import LinkRun"),
        ("sync.py", "import finances.sync.runner"),
        ("backups.py", "from finances import db"),
        ("transfers.py", "from finances import sync"),
        ("nested/extra.py", "import sqlalchemy.orm"),
        ("sync.py", "def later():\n    import keyring"),
    ],
    ids=[
        "backups-db",
        "sync-db",
        "transfers-sql",
        "keyring",
        "runner-function",
        "mixed-import",
        "wrong-file",
        "module-import",
        "parent-db",
        "parent-sync",
        "nested-file",
        "nested-scope",
    ],
)
def test_forbidden_import_is_rejected(tmp_path, monkeypatch, filename, source):
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source + "\n", encoding="utf-8")
    monkeypatch.setattr(guard, "VIEWS", tmp_path)
    with pytest.raises(AssertionError):
        guard.test_only_the_frozen_views_still_load_data()


@pytest.mark.parametrize(
    "filename,source",
    [
        ("sync.py", "from finances.sync.runner import LinkRun"),
        ("sync.py", "from finances.sync.runner import LinkRun as Result"),
        ("backups.py", "from finances.analysis.backups import BackupFile"),
        ("transfers.py", "from finances.analysis.transfers import PairListing, SuggestionListing"),
    ],
    ids=["linkrun", "alias", "backup-type", "transfer-types"],
)
def test_result_type_import_is_permitted(tmp_path, monkeypatch, filename, source):
    path = tmp_path / filename
    path.write_text(source + "\n", encoding="utf-8")
    monkeypatch.setattr(guard, "VIEWS", tmp_path)
    guard.test_only_the_frozen_views_still_load_data()
```

Fresh fail47i at approved commit: eleven failures and five passes. Existing guard
already rejects keyring in accounts.py; four result import cases pass. The eleven
failures expose stale exemptions, parent/recursive handling. Only synthetic source
strings are written under pytest tmp_path and parsed, never imported/executed.
Lint/format pass. No product or reference guard implementation was authored.

## Tests to write

In tests/unit/test_view_import_guard_behavior.py (core):
- Assert exact PERMITTED_RESULT_IMPORTS set and absence of STILL_LOADING.
- Actual29-view source scan passes. For a copied views directory, inject a DB
  import into backups.py, sync.py or transfers.py independently; each fails.
- Nested/sync.py with LinkRun is forbidden; sync.py LinkRun wildcard or wrong
  module LinkRun forbidden; alias of forbidden function forbidden. Relative
  `from ..db import engine` resolves to finances.db and fails.
- Include allowed similarly prefixed identifiers such as keyringish, sqlalchemyish,
  finances.sync_helpers to prove root-boundary matching. Constant strings/comments
  containing import text are permitted; no parsing by substring.
- Synthetic source containing a forbidden nested import plus top-level raising
  RuntimeError must fail via import guard without executing RuntimeError.
- Compare unchanged formatting test bodies/fixtures against planning baseline;
  do not manufacture new tests solely to restore a reduced count.

R1/R2: given forbidden matrix plus exact exception/edge cases; R3: allowed matrix,
actual source scan and original formatting tests; R4: document review; R5: full
collection identity probe and unchanged section file. New helper tests assert
observable accept/refuse behavior rather than helper algorithm spelling.

## Rules for this phase

Synthetic offline data, no real financial data/Keychain/network/aggregator; no
application business logic changes, dependencies or coverage exemptions. Coder
and verifier do not commit or push. No full reference build in architect scratch.

## Acceptance

Before implementation capture collection baseline using guide script save mode.
After implementation execute sequentially:

1. `.venv/bin/python scripts/check.py --first core --workers 4`: all eight sections
   zero failed/skipped, no xfails/warnings summary; overall/critical gates pass;
   final All checks passed.; at least **4806** tests (4790+16) plus coder cases.
2. `.venv/bin/python -m pytest tests/unit/test_view_import_guard.py --no-cov`:
   exactly sixteen passed.
3. Collection probe compare mode with original snapshot: all4790 original nodes
   retained, additions only two listed new files, no duplicates, FAILURES0.
   tests/sections.toml byte-identical, new files resolve to core by existing rules.
4. Scope/given equality and unchanged src/dependencies/other earlier tests.
   Guard-only edit boundary in existing file; docs satisfy R4 and retain all
   original coverage/privacy/determinism/acceptance obligations.

No new production module or changed critical module: no additional narrow coverage
command applies. Standard full critical/overall coverage remains mandatory;
pytest test code is not added to source coverage to invent a percentage gate.
No additional probe reimplements guard: given tests independently plant violations.

## Report

Standard progress headed `## Phase 47i: tighten view import guards and document testing conventions (YYYY-MM-DD)`.
N4790, given16, exact new count, no moved/lost nodes; public application names None.
Record planning SHA, clone/import provenance, section table, last ten check lines,
other gates and requirement/test mapping. Report actual bounded guard guarantees.
