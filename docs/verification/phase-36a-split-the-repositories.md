# Verify Phase 36a: split the repositories, and two more critical modules

Spec: `docs/phases/phase-36a-split-the-repositories.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder turned `src/finances/db/repositories.py` into a package of nine area modules behind a re-exporting `__init__.py`, and added two modules to the critical list. Nothing may behave differently.

These are correct and must not be reported: a different order of definitions inside a module; imports grouped or sorted differently; the facade's import lines wrapped differently.

## 1. Gates

N is `3259` when Phase 14e was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`, including `critical coverage: passed`; at least N + 14 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_repositories_split.py tests/unit/test_check_script.py --no-cov` | all passed |
| `git diff --stat HEAD -- tests` | only `tests/unit/test_check_script.py` |
| `git diff --stat HEAD -- src` | only `src/finances/db/repositories.py`, deleted |

## 2. Scope paths

```
 M docs/progress.md
 M docs/testing.md
 M scripts/critical_modules.txt
 D src/finances/db/repositories.py
 M tests/unit/test_check_script.py
?? src/finances/db/repositories/
?? tests/unit/test_repositories_split.py
```

The critical-modules diff equals the spec's; the test file equals its block.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | the probe | `FAILURES 0` |
| R2 to R4 | gate 2 | pass |
| R5 | gates 1 and 2 | pass |

## 4. Probe

Before anything is committed, save this script outside the repository and run it from the repository root with `.venv/bin/python`. It reads the old module from the last commit and checks that every definition appears exactly once in the package with an identical syntax tree (formatting aside), and that nothing new was defined.

```python
"""Phase 36a probe: every definition of the old repositories.py moved unchanged into the package.

Run from the repository root, after the phase is applied and before it is committed:
    .venv/bin/python <folder>/probe_36a.py
"""

import ast
import subprocess
from pathlib import Path

failures = 0


def check(name: str, ok: bool) -> None:
    global failures
    print(("ok   " if ok else "FAIL ") + name)
    failures += 0 if ok else 1


def definitions(tree: ast.Module) -> dict[str, str]:
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            found[node.name] = ast.dump(node)
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id != "__all__":
                found[node.targets[0].id] = ast.dump(node)
    return found


try:
    old_text = subprocess.run(
        ["git", "show", "HEAD:src/finances/db/repositories.py"],
        capture_output=True, text=True, check=True,
    ).stdout
    old = definitions(ast.parse(old_text))
    new: dict[str, list[str]] = {}
    for path in sorted(Path("src/finances/db/repositories").glob("*.py")):
        if path.stem == "__init__":
            continue
        for name, dump in definitions(ast.parse(path.read_text(encoding="utf-8"))).items():
            new.setdefault(name, []).append(dump)
    check(f"{len(old)} definitions read from HEAD", len(old) > 80)
    for name, dump in sorted(old.items()):
        homes = new.get(name, [])
        check(f"{name}: defined once and unchanged", homes == [dump])
    extra = sorted(set(new) - set(old))
    check(f"no new definitions ({', '.join(extra) or 'none'})", not extra)
except Exception as error:  # the probe never crashes
    check(f"probe ran ({type(error).__name__}: {error})", False)
print(f"FAILURES {failures}")
```

Expected: `FAILURES 0`, with one `ok` line per definition.

## 5. Spot checks

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. Define one function in `__init__.py` instead of its area | `test_the_facade_only_imports` | pass | fail |
| 2. Put `list_budgets` in `categories.py` | `test_each_name_lives_in_its_area[budgets]` | pass | fail |
| 3. An area imports from `finances.db.repositories` | `test_no_area_imports_the_facade` | pass | fail |
| 4. Edit a body while moving it (for example rename a local variable) | the probe | `ok` | `FAIL` for that name |

## 6. Out of scope

Each must be absent: a changed function body or signature; a change to any other source file; a change to `views` or the CLI.
