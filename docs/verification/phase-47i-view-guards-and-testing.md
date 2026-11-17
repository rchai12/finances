# Verify Phase 47i: view guards and testing conventions

Spec: docs/phases/phase-47i-view-guards-and-testing.md. Follow AGENTS.md and
phase-conventions; write only docs/reviews/phase-47i-view-guards-and-testing.md.

## Baseline

47h4 approved/committed733cbd4, 4790 tests. Confirm implementation98188a8 exists,
finalized planning docs committed/unchanged and new implementation exists. Inspect
status/diff before writing report. Record full planning SHA, clone provenance and
linked venv/PYTHONPATH. Preserve original editor settings. Use independent isolated
review copy and compare reviewed bytes before transporting verdict.

## 1. Gates

Capture baseline collection from a separate unmodified planning checkout, outside
repo. Do not trust a coder snapshot without independently obtaining it.
Run spec's four acceptance steps fresh and sequentially, first
`.venv/bin/python scripts/check.py --first core --workers 4` >=4806 plus coder
cases, all sections clean, no skips/xfails/warnings summary, critical/overall gates
and final All checks passed. Then given-only16, collection compare and scope.
No extra narrow coverage gate for test/doc-only change. Record actual outputs,
section table and final ten lines. Resolve localhost fixture permission failures
as environment errors; never weaken tests or reuse coder receipts.

## 2. Scope and requirements

Five spec paths plus report. Given bytes identical; src, dependencies, sections
and all earlier tests outside the single scoped file byte-identical. Within old
file, formatting/fixture/test names retained, only guard/imports/helpers changed.
No count-preserving test replacement or reduced assertion. All old node ids survive.

| Id | Evidence |
|---|---|
| R1 | exact set assertion, given stale file/mixed/wrong-file import cases |
| R2 | given parent/nested forms and coder alias/relative/root-boundary cases |
| R3 | four allowed cases, actual view scan, retained formatting tests and unchanged source |
| R4 | doc review: behavior/layer naming, legacy *_more valid, future exact move map, historical timing versus measured evidence, no weakened coverage |
| R5 | independent full node identity comparison, same section configuration and scope |

Name a meaningful coder test for every Tests to write item. Guard is bounded AST
inspection; do not demand a dynamic execution sandbox or claim imports prove IO.
Reject a broad file exemption even if given cases happen to pass.

## 3. Collection identity probe

Save script outside repo. In clean planning checkout:
`.venv/bin/python <script> save <outside-baseline.json>` (4790 nodes).
In delivered review checkout:
`.venv/bin/python <script> compare <outside-baseline.json>`.
Use corresponding clone/src PYTHONPATH each time. Collection only; no real data,
application calls, network or coverage. Expected ok lines and FAILURES0. Save and
compare modes validated against predecessor plus16 given nodes. For self-check,
use a disposable snapshot with one fake predecessor node: compare must fail;
remove that snapshot afterwards. Never update baseline to mask missing cases.

```python
import json
import subprocess
import sys
from pathlib import Path


def main():
    mode, file = sys.argv[1:]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-cov"],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(result.returncode)
    nodes = sorted(
        line.strip()
        for line in result.stdout.splitlines()
        if "::" in line and line.startswith("tests/")
    )
    assert nodes and len(nodes) == len(set(nodes))
    path = Path(file)
    if mode == "save":
        path.write_text(json.dumps(nodes), encoding="utf-8")
        print("baseline collection ok", len(nodes))
    else:
        old = json.loads(path.read_text(encoding="utf-8"))
        removed = sorted(set(old) - set(nodes))
        added = sorted(set(nodes) - set(old))
        assert not removed, removed
        assert added and all(
            n.startswith(
                (
                    "tests/unit/test_view_import_guard.py::",
                    "tests/unit/test_view_import_guard_behavior.py::",
                )
            )
            for n in added
        ), added
        print("retained collection ok", len(old))
        print("new guard cases ok", len(added))


failures = 0
try:
    main()
except (Exception, SystemExit) as error:
    failures += 1
    print("collection FAIL", type(error).__name__, str(error))
print("FAILURES", failures)
raise SystemExit(bool(failures))
```

## 4. Spot checks in scratch only

Ids prefix tests/unit/test_view_import_guard.py::. All planted source parsed, not
executed. tmp_path and monkeypatched VIEWS isolate from production source.

| Mutation | Deciding given case | Correct | Broken |
|---|---|---|---|
| restore sync.py blanket exception | test_forbidden_import_is_rejected[sync-db] |AssertionError|passes scan|
| permit LinkRun plus all other names in same import | test_forbidden_import_is_rejected[mixed-import] |AssertionError|passes scan|
| scan direct files only | test_forbidden_import_is_rejected[nested-file] |AssertionError|passes scan|
| deny every sync import | test_result_type_import_is_permitted[linkrun] |passes|AssertionError|

An unexpected failure mechanism needs investigation; never mutate reviewed files.

## 5. Variations and verdict

Private helper names and diagnostic wording may vary; exact permitted tuple and
recursive/alias/parent/boundary behavior are fixed. No test renames or source type
moves. No docs claiming unit suite measured under10seconds. Retain front-end
regressions and old *_more files. Verify standard progress, no application public
names added. Standard verdict header/findings; distinguish baseline/spec/environment
from implementation failure. FAIL handoff gives requirement, observation and
required result; verifier changes only review, no repairs/commit/push.
