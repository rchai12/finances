# Verify Phase 10: quality gates

Spec: `docs/phases/phase-10-quality-gates.md`

Do not modify any file in the repository, and do not run the install script in this repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder added `scripts/check.py` (lint, format, tests, a critical coverage gate, optional real samples), a pre-commit hook with install and uninstall scripts, and new text in `docs/testing.md` and `AGENTS.md`. Two files and two test files were given.

Judge the code by what it does. These are correct and must not be reported: any private helpers in `scripts/check.py`; `pathlib` or `os.path`; reading the report with `json.loads` or `json.load`.

## 1. Gates

Run each command on its own line from the repository root. Do not activate the virtual environment.

**N** is the passed count before the phase; the coder's entry in `docs/progress.md` states it. It is `1961` when Phase 16d was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | exit code 0; last line `All checks passed.`; the summary lists `lint`, `format`, `tests`, `critical coverage`, each `passed`; in the `tests` step at least N + 25 passed, 0 failed, 0 skipped, 0 xfailed, no warnings summary |
| `.venv/bin/python -m pytest tests/unit/test_check_script.py tests/e2e/test_git_hooks.py --no-cov` | exactly `25 passed` |
| `git grep -n --untracked -E "^ *(import|from) +finances|subprocess\.run\([^)]*shell=True" -- scripts/check.py` | no output |

When this machine holds `data/samples/`, also run `.venv/bin/python scripts/check.py --real-samples` and report only whether its last line is `All checks passed.` and the summary line of `real samples` (privacy rule 6).

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M AGENTS.md
 M docs/progress.md
 M docs/testing.md
?? scripts/check.py
?? scripts/critical_modules.txt
?? scripts/git-hooks/
?? scripts/install-git-hooks.sh
?? scripts/uninstall-git-hooks.sh
?? tests/e2e/test_git_hooks.py
?? tests/unit/test_check_script.py
```

- The given files are identical to the blocks in the spec. `ls -l scripts/` shows `install-git-hooks.sh`, `uninstall-git-hooks.sh`, and `git-hooks/pre-commit` executable.
- `git diff HEAD -- docs/testing.md AGENTS.md` changes exactly the passages of R10 and R11.
- `.git/hooks/pre-commit` does not exist (the coder did not install the hook here).

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 to R6 | the check command | probe; gate 1 | every line starting `gate:` and `check:` |
| R7 to R9 | the hook and its scripts | probe; gate 2 | every line starting `hook:` |
| R10 to R12 | the documents | probe; section 2 | the two lines starting `gate: the nine` and `gate: docs/testing.md`; `docs: AGENTS.md ...` |

## 4. Independent probe

This script loads `scripts/check.py`, feeds its coverage gate reports it has not seen, and runs it with a stand-in for subprocess. It builds a throwaway git repository in a temporary folder (removed afterwards), with the machine's git settings switched off, installs the hook there, and makes a commit the hook must stop and one it must let through. Last, it runs the real `scripts/check.py`, which takes about a minute, and checks that nothing is left behind in the repository.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

failures = 0
ROOT = Path.cwd()
ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def section(name, run):
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        check(f"{name}: ran to the end (stopped by {type(exc).__name__}: {exc})", False)


def load():
    spec = importlib.util.spec_from_file_location("check_probe", ROOT / "scripts" / "check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def status():
    return subprocess.run(
        ["git", "status", "--porcelain", "--ignored"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=ENV,
        check=False,
    ).stdout


def real_run():
    before = status()
    result = subprocess.run(
        [sys.executable, "scripts/check.py"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    lines = result.stdout.splitlines()
    check(
        "check: the real run passes and says so last",
        result.returncode == 0 and lines[-1:] == ["All checks passed."],
    )
    check(
        "check: the summary lists the four steps in order",
        lines[-6:-1]
        == [
            "Summary:",
            "  lint: passed",
            "  format: passed",
            "  tests: passed",
            "  critical coverage: passed",
        ],
    )
    check(
        "check: each step is announced before it runs",
        [line for line in lines if line.startswith("== ")]
        == ["== lint", "== format", "== tests", "== critical coverage"],
    )
    check(
        "check: nothing is left behind in the repository",
        status() == before and not (ROOT / "coverage.json").exists(),
    )


def gate():
    module = load()
    report = {
        "files": {
            "src/finances/sync/simplefin.py": {
                "summary": {"missing_lines": 0, "missing_branches": 0}
            },
            "src/finances/analysis/people.py": {
                "summary": {"missing_lines": 4, "missing_branches": 0}
            },
            "src/finances/domain/feed_setup.py": {
                "summary": {"missing_lines": 0, "missing_branches": 7}
            },
        }
    }
    gaps = module.coverage_gaps(
        report,
        ["analysis/people.py", "sync/simplefin.py", "domain/feed_setup.py", "domain/money.py"],
    )
    check(
        "gate: gaps are named in list order, and an unmeasured module is a gap",
        gaps
        == [
            "analysis/people.py: 4 lines and 0 branches not covered",
            "domain/feed_setup.py: 0 lines and 7 branches not covered",
            "domain/money.py: not measured",
        ],
    )
    listed = module.read_critical(module.CRITICAL_FILE.read_text(encoding="utf-8"))
    testing = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")
    check(
        "gate: the nine critical modules exist and docs/testing.md names each",
        len(listed) == 9
        and all(
            (ROOT / "src" / "finances" / item).is_file() and f"`{item}`" in testing
            for item in listed
        ),
    )
    check(
        "gate: docs/testing.md asks for every line and branch, not 95%",
        "95%" not in testing and "scripts/critical_modules.txt" in testing,
    )
    calls = []

    def runner(command, cwd):
        calls.append(command)
        return 1 if command[3:4] == ["format"] else 0

    code = module.main([], run=runner)
    check(
        "gate: a failing format check stops the run before the tests", code == 1 and len(calls) == 2
    )
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    check(
        "docs: AGENTS.md tells the coder to run the check command",
        ".venv/bin/python scripts/check.py" in agents,
    )


def hook():
    folder = Path(tempfile.mkdtemp())
    try:
        repo = folder / "repo"
        (repo / "scripts" / "git-hooks").mkdir(parents=True)
        for name in ("install-git-hooks.sh", "uninstall-git-hooks.sh"):
            shutil.copy(ROOT / "scripts" / name, repo / "scripts" / name)
        shutil.copy(
            ROOT / "scripts" / "git-hooks" / "pre-commit",
            repo / "scripts" / "git-hooks" / "pre-commit",
        )
        (repo / ".venv").symlink_to(ROOT / ".venv")
        git = [
            "git",
            "-c",
            "user.name=Probe",
            "-c",
            "user.email=probe@example.invalid",
            "-c",
            "core.hooksPath=.git/hooks",
        ]

        def run(*args):
            return subprocess.run(
                args, cwd=repo, env=ENV, capture_output=True, text=True, check=False
            )

        run(*git, "init", "-q")
        installed = run("bash", "scripts/install-git-hooks.sh")
        check(
            "hook: installs with its message",
            installed.returncode == 0 and "Installed the pre-commit hook" in installed.stdout,
        )
        (repo / "bad.py").write_text("def f( x ):\n    return  x\n")
        run(*git, "add", "bad.py")
        stopped = run(*git, "commit", "-q", "-m", "bad")
        check(
            "hook: a badly formatted file stops the commit",
            stopped.returncode != 0 and "Commit stopped" in stopped.stderr,
        )
        (repo / "bad.py").write_text("def f(x):\n    return x\n")
        run(*git, "add", "bad.py")
        passed = run(*git, "commit", "-q", "-m", "good")
        check("hook: once fixed the commit goes through", passed.returncode == 0)
        removed = run("bash", "scripts/uninstall-git-hooks.sh")
        check(
            "hook: uninstall removes it",
            removed.returncode == 0 and not (repo / ".git" / "hooks" / "pre-commit").exists(),
        )
    finally:
        shutil.rmtree(folder, ignore_errors=True)


for name, step in (("gate", gate), ("hook", hook), ("check", real_run)):
    section(name, step)
print("FAILURES", failures)
```

## 5. The coder's tests

There are none to review. Confirm that the coder added no test file other than the two given ones and changed no existing test (section 2). Then, for each change below, say which given test would fail, by reading the tests. If none would, that is a finding.

1. `coverage_gaps` skips a module that is missing from the report.
2. `main` keeps running steps after one fails.
3. The install script overwrites a hook that is not ours.
4. The hook runs only `ruff format --check .`.

## 6. Out of scope

Each of these must be absent. Report any that is present.

- A new dependency in `pyproject.toml`, a `.pre-commit-config.yaml`, or CI files.
- The test suite run by the hook.
- Any change under `src/`.

## 7. Progress log

`docs/progress.md` ends with an entry headed `## Phase 10: quality gates (YYYY-MM-DD)` with a real date, N, and the passed count.

## Verdict

`PASS`, or `FAIL` followed by one line per finding:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then: `Total passed: <the count from the tests step>`

## If the verdict is FAIL

Send the coder each finding as: the requirement, what was observed, and what is required. Do not prescribe the code.
