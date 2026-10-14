# Phase 10: quality gates

## Goal

One command checks everything a phase must pass, and a git hook stops a commit that would fail lint or format.

- `.venv/bin/python scripts/check.py` runs lint, the format check, the full test suite, and a **critical coverage gate**, stopping at the first failure, and ends with a short summary. With `--real-samples` it then runs the opt-in check of the real statements. Coders, verifiers, and the owner all run the same command; later specs will name it in their acceptance.
- The coverage gate requires **every line and every branch** of the modules where a bug silently corrupts money data. They are all fully covered today; the gate keeps them so. The list lives in one file, `scripts/critical_modules.txt`.
- `scripts/install-git-hooks.sh` installs a pre-commit hook that runs lint and the format check (about one second) before each commit; `scripts/uninstall-git-hooks.sh` removes it. Neither touches a hook that is not ours.

This replaces the older draft of Phase 10, written before the project moved to macOS and before Phase 9 dropped golden snapshots.

## Read first

- `AGENTS.md`, `docs/testing.md` ("Critical modules", "Commands")
- `pyproject.toml` (`[tool.pytest.ini_options]` adds `--cov=finances --cov-branch` to every run; `[tool.coverage.report]` has `fail_under = 85`)
- `scripts/install-sync-schedule.sh` and `scripts/uninstall-sync-schedule.sh`: the style for the two new shell scripts
- `tests/real_samples/check_real_samples.py`: what `--real-samples` runs

## Starting state

- Phase 16d is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `1961` when Phase 16d is the last phase built.
- The nine modules of `scripts/critical_modules.txt` below are at 100% line and branch coverage today.
- `.git/hooks/pre-commit` does not exist.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `scripts/check.py` | new: the check command (Part 1) |
| `scripts/critical_modules.txt` | new: given, do not change |
| `scripts/git-hooks/pre-commit` | new: given, do not change; executable |
| `scripts/install-git-hooks.sh`, `scripts/uninstall-git-hooks.sh` | new: executable (Part 2) |
| `docs/testing.md`, `AGENTS.md` | the text of Part 3 |
| `tests/unit/test_check_script.py`, `tests/e2e/test_git_hooks.py` | new: given, do not change |
| `docs/progress.md` | one new entry |

Change no production module under `src/`, no existing test, and no configuration file.

## Out of scope

- Mutation testing, CI, and the `pre-commit` package. No new dependency.
- Running the test suite from the git hook.
- Installing the hook automatically, or any change to `.git/` other than what the install script does when the owner runs it.
- Golden snapshots (dropped in Phase 9).
- Raising or lowering `fail_under`.

## Dependencies

None new.

## Design

```python
# scripts/check.py  (standard library only; run as: .venv/bin/python scripts/check.py)
ROOT: Path            # the repository root: the parent of the folder holding this file
CRITICAL_FILE: Path   # scripts/critical_modules.txt, next to this file


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str] | None   # None for the critical coverage gate, which runs in this process


def read_critical(text: str) -> list[str]: ...
def coverage_gaps(report: dict, modules: list[str]) -> list[str]: ...
def steps(python: str, coverage_json: Path, *, real_samples: bool) -> list[Step]: ...
def run_command(command: list[str], cwd: Path) -> int: ...
def main(
    argv: list[str] | None = None, run: Callable[[list[str], Path], int] = run_command
) -> int: ...
```

The file ends with `if __name__ == "__main__": sys.exit(main())`. It imports nothing from `finances`, so it runs even when the package is broken.

Text, in full:

| Where | Text |
|---|---|
| a step starts | `== NAME` |
| a coverage gap, missing lines or branches | `MODULE: L lines and B branches not covered` |
| a coverage gap, module not in the report | `MODULE: not measured` |
| the summary | `Summary:`, then one line `  NAME: passed`, `  NAME: FAILED`, or `  NAME: not run` per step |
| the last line | `All checks passed.` or `Check failed at: NAME` |
| install, done | `Installed the pre-commit hook: lint and format are checked before each commit.` |
| install, another hook present (stderr) | `Error: another pre-commit hook is already installed; remove it first` |
| uninstall, done | `Removed the pre-commit hook.` |
| uninstall, nothing installed | `No pre-commit hook was installed.` |
| uninstall, another hook present (stderr) | `Error: the pre-commit hook is not ours; it was left in place` |
| either script, no `.git/hooks` folder (stderr) | `Error: no .git/hooks folder; run this inside the repository` |

## Requirements

### Part 1: the check command

- **R1.** `read_critical(text)` returns the module paths of the text in order: on each line everything from `#` on is dropped, outer spaces are removed, and empty lines are skipped.
- **R2.** `coverage_gaps(report, modules)` reads a coverage JSON report (`report["files"]`, keyed `src/finances/MODULE`, each with `summary.missing_lines` and `summary.missing_branches`). It returns, in the order of `modules`, one text per module that is not fully covered: `MODULE: not measured` when the key is absent, `MODULE: L lines and B branches not covered` when either count is above zero. Other modules in the report do not matter.
- **R3.** `steps(python, coverage_json, real_samples=...)` returns, in this order:
  1. `lint`: `[python, "-m", "ruff", "check", "."]`
  2. `format`: `[python, "-m", "ruff", "format", "--check", "."]`
  3. `tests`: `[python, "-m", "pytest", f"--cov-report=json:{coverage_json}"]`
  4. `critical coverage`: no command
  5. only when `real_samples`: `real samples`: `[python, "-m", "pytest", "tests/real_samples/check_real_samples.py", "--no-cov", "-rA"]`
- **R4.** `run_command(command, cwd)` runs the command with `subprocess.run(command, cwd=cwd, check=False)`, its output going straight to the terminal, and returns the exit code.
- **R5.** `main(argv, run)` reads one option, `--real-samples`, with `argparse`; any other argument ends with `argparse`'s usage error (exit code 2). It then:
  - creates a temporary folder outside the repository for the coverage report, removed when `main` returns;
  - builds the steps with `sys.executable`;
  - runs them in order, printing `== NAME` before each. A command step passes when `run(command, ROOT)` returns 0. The critical coverage step reads the report and `CRITICAL_FILE`, prints each gap indented by two spaces, and passes when there is none;
  - stops at the first step that fails; the steps after it are not run;
  - prints an empty line, the summary, and the last line, all from the table above;
  - returns 0 when every step passed, otherwise 1.
- **R6.** `scripts/critical_modules.txt` is the given file below. The check command reads the list only from there.

### Part 2: the git hook

- **R7.** `scripts/git-hooks/pre-commit` is the given file below, committed as executable. It runs `ruff check .` and then `ruff format --check .` from the repository root with the project's interpreter, and on a failure stops the commit with two lines on stderr.
- **R8.** `scripts/install-git-hooks.sh` (bash, `set -euo pipefail`, executable) finds the repository as the parent of its own folder and targets `REPO/.git/hooks/pre-commit`:
  - no `REPO/.git/hooks` folder: the error of the table, exit 1;
  - the target exists and has no line starting with `# finances pre-commit hook`: the error of the table, exit 1, the target unchanged;
  - otherwise it copies `scripts/git-hooks/pre-commit` there, makes it executable, prints the done message, and exits 0. Installing again replaces our own hook.
- **R9.** `scripts/uninstall-git-hooks.sh` (bash, `set -euo pipefail`, executable), with the same repository and target:
  - no `.git/hooks` folder: the error of the table, exit 1;
  - no target: `No pre-commit hook was installed.`, exit 0;
  - a target without our first comment line: the error of the table, exit 1, the target left;
  - otherwise it removes the target, prints `Removed the pre-commit hook.`, and exits 0.

### Part 3: the documents

- **R10.** In `docs/testing.md`, replace these four passages with the given text of R12: the row of the layer table that starts `| Mutation |`; rule 6 of "Rules"; the section "Critical modules", from its heading to the line before `## Commands`; and in "Commands", the code block and the sentence after it.
- **R11.** In `AGENTS.md`, section "Running commands", add this as the new last bullet:

```markdown
- Before reporting a phase, run `.venv/bin/python scripts/check.py`. It must end with `All checks passed.`
```

- **R12.** The given text for `docs/testing.md`:

The row of the layer table:

```markdown
| Mutation | not yet | Whether the tests catch deliberate bugs in critical modules | A later phase |
```

Rule 6:

```markdown
6. **Coverage**: branch coverage is measured on every run. Overall `fail_under = 85`. Every line and every branch of each critical module must be covered; `scripts/check.py` checks it.
```

The section "Critical modules":

```markdown
## Critical modules

Bugs here silently corrupt money data, so every line and every branch of each must be covered by tests. The list lives in `scripts/critical_modules.txt`, which `scripts/check.py` reads; a phase that adds a critical module adds it there and here.

- `domain/money.py`
- `ingest/parsers/helpers.py` (year inference, amount parsing)
- `ingest/reconcile.py`
- `ingest/dedup.py`
- `domain/matching.py` (pairing feed rows with statement lines)
- `sync/service.py` (applying a feed, balance drift)
- `sync/simplefin.py` (reading SimpleFIN's answers)
- `domain/feed_setup.py` (guessing how to set up a new SimpleFIN account)
- `analysis/people.py` (whose money a transaction is)
- Later: transfer matching (Phase 11), spending aggregation (Phase 12)
```

The code block of "Commands":

```zsh
.venv/bin/python scripts/check.py                  # everything a phase must pass: lint, format, tests, critical coverage
.venv/bin/python scripts/check.py --real-samples   # the same, then the real statements (opt-in, counts only)
.venv/bin/python -m pytest                         # the tests alone, with coverage
```

The sentence after it:

```markdown
To have lint and format checked before every commit, run `scripts/install-git-hooks.sh` once; `scripts/uninstall-git-hooks.sh` removes the hook.
```

## Given files

Create these files exactly as shown. `scripts/git-hooks/pre-commit` must be executable (`chmod +x`).

`scripts/critical_modules.txt`

```text
# Modules where a bug silently corrupts money data. Every line and every branch of each must be
# covered by tests. One path per line, relative to src/finances/. Read by scripts/check.py.
domain/money.py
ingest/parsers/helpers.py
ingest/reconcile.py
ingest/dedup.py
domain/matching.py
sync/service.py
sync/simplefin.py
domain/feed_setup.py
analysis/people.py
```

`scripts/git-hooks/pre-commit`

```sh
#!/bin/sh
# finances pre-commit hook: installed by scripts/install-git-hooks.sh.
# Checks lint and format before each commit. Remove it with scripts/uninstall-git-hooks.sh.
cd "$(git rev-parse --show-toplevel)" || exit 1
if [ -x .venv/bin/python ]; then
    PY=.venv/bin/python
else
    PY=.venv/Scripts/python.exe
fi
if "$PY" -m ruff check . && "$PY" -m ruff format --check .; then
    exit 0
fi
echo "Commit stopped: fix the lint or format problems above, then commit again." >&2
echo "Formatting is fixed with: $PY -m ruff format ." >&2
exit 1
```

## Given tests

Create these two files exactly as shown and do not change them. If one fails, the code is wrong. `tests/e2e/test_git_hooks.py` builds a throwaway git repository, links it to this project's `.venv`, ignores the machine's own git settings, installs the hook there, and makes real commits. There are no tests for you to write.

`tests/unit/test_check_script.py`

```python
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check.py"
CRITICAL = [
    "domain/money.py",
    "ingest/parsers/helpers.py",
    "ingest/reconcile.py",
    "ingest/dedup.py",
    "domain/matching.py",
    "sync/service.py",
    "sync/simplefin.py",
    "domain/feed_setup.py",
    "analysis/people.py",
]


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location("check_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def summary(missing_lines: int = 0, missing_branches: int = 0) -> dict:
    return {
        "summary": {
            "missing_lines": missing_lines,
            "missing_branches": missing_branches,
        }
    }


def report(**files: dict) -> dict:
    return {"files": {f"src/finances/{name}": value for name, value in files.items()}}


class Runner:
    """Stands in for subprocess: records each command and answers with a chosen exit code."""

    def __init__(self, codes: dict[str, int] | None = None, gaps: dict | None = None) -> None:
        self.codes = codes or {}
        self.gaps = gaps or {}
        self.calls: list[tuple[list[str], Path]] = []

    def __call__(self, command: list[str], cwd: Path) -> int:
        self.calls.append((command, cwd))
        if "pytest" in command and "--no-cov" not in command:
            target = next(part for part in command if part.startswith("--cov-report=json:"))
            files = {f"src/finances/{name}": summary() for name in CRITICAL}
            files.update({f"src/finances/{name}": value for name, value in self.gaps.items()})
            Path(target.removeprefix("--cov-report=json:")).write_text(json.dumps({"files": files}))
        for word, code in self.codes.items():
            if word in command:
                return code
        return 0


# The list of critical modules


def test_the_list_skips_comments_and_blank_lines(check) -> None:
    text = "# money first\ndomain/money.py\n\n  ingest/dedup.py  # fingerprints\n   \n#end\n"
    assert check.read_critical(text) == ["domain/money.py", "ingest/dedup.py"]


def test_the_shipped_list(check) -> None:
    modules = check.read_critical(check.CRITICAL_FILE.read_text(encoding="utf-8"))
    assert modules == CRITICAL
    assert check.CRITICAL_FILE == ROOT / "scripts" / "critical_modules.txt"
    for module in modules:
        assert (ROOT / "src" / "finances" / module).is_file(), module


# The coverage gate


def test_fully_covered_modules_have_no_gaps(check) -> None:
    covered = report(**{"domain/money.py": summary(), "ingest/dedup.py": summary()})
    assert check.coverage_gaps(covered, ["domain/money.py", "ingest/dedup.py"]) == []


def test_each_gap_is_named_in_list_order(check) -> None:
    found = report(
        **{
            "ingest/dedup.py": summary(missing_lines=2),
            "domain/money.py": summary(missing_branches=1),
            "ingest/reconcile.py": summary(missing_lines=1, missing_branches=3),
        }
    )
    modules = [
        "domain/money.py",
        "ingest/dedup.py",
        "ingest/reconcile.py",
        "sync/service.py",
    ]
    assert check.coverage_gaps(found, modules) == [
        "domain/money.py: 0 lines and 1 branches not covered",
        "ingest/dedup.py: 2 lines and 0 branches not covered",
        "ingest/reconcile.py: 1 lines and 3 branches not covered",
        "sync/service.py: not measured",
    ]


def test_modules_outside_the_list_do_not_matter(check) -> None:
    found = report(**{"domain/money.py": summary(), "cli/main.py": summary(missing_lines=9)})
    assert check.coverage_gaps(found, ["domain/money.py"]) == []


# The steps


def test_the_steps_in_order(check, tmp_path: Path) -> None:
    target = tmp_path / "coverage.json"
    steps = check.steps("/py", target, real_samples=False)
    assert [(step.name, step.command) for step in steps] == [
        ("lint", ["/py", "-m", "ruff", "check", "."]),
        ("format", ["/py", "-m", "ruff", "format", "--check", "."]),
        ("tests", ["/py", "-m", "pytest", f"--cov-report=json:{target}"]),
        ("critical coverage", None),
    ]


def test_real_samples_are_checked_only_when_asked(check, tmp_path: Path) -> None:
    steps = check.steps("/py", tmp_path / "c.json", real_samples=True)
    assert (steps[-1].name, steps[-1].command) == (
        "real samples",
        [
            "/py",
            "-m",
            "pytest",
            "tests/real_samples/check_real_samples.py",
            "--no-cov",
            "-rA",
        ],
    )
    assert len(steps) == 5


# Running


def test_every_step_passes(check, capsys) -> None:
    runner = Runner()
    assert check.main([], run=runner) == 0
    assert [command[2:4] for command, _ in runner.calls][:2] == [
        ["ruff", "check"],
        ["ruff", "format"],
    ]
    assert runner.calls[2][0][2] == "pytest"
    assert len(runner.calls) == 3
    assert all(cwd == ROOT for _, cwd in runner.calls)
    assert all(command[0] == sys.executable for command, _ in runner.calls)
    out = capsys.readouterr().out
    assert out.splitlines()[-6:] == [
        "Summary:",
        "  lint: passed",
        "  format: passed",
        "  tests: passed",
        "  critical coverage: passed",
        "All checks passed.",
    ]
    assert "== lint" in out and "== tests" in out and "== critical coverage" in out


def test_the_first_failure_stops_the_check(check, capsys) -> None:
    runner = Runner(codes={"check": 1})
    assert check.main([], run=runner) == 1
    assert len(runner.calls) == 1
    assert capsys.readouterr().out.splitlines()[-6:] == [
        "Summary:",
        "  lint: FAILED",
        "  format: not run",
        "  tests: not run",
        "  critical coverage: not run",
        "Check failed at: lint",
    ]


def test_failing_tests_stop_before_the_coverage_gate(check, capsys) -> None:
    runner = Runner(codes={"pytest": 1})
    assert check.main([], run=runner) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[-3:] == [
        "  tests: FAILED",
        "  critical coverage: not run",
        "Check failed at: tests",
    ]


def test_a_gap_in_a_critical_module_fails_the_check(check, capsys) -> None:
    runner = Runner(gaps={"sync/service.py": summary(missing_branches=2)})
    assert check.main([], run=runner) == 1
    out = capsys.readouterr().out
    assert "  sync/service.py: 0 lines and 2 branches not covered" in out.splitlines()
    assert out.splitlines()[-2:] == [
        "  critical coverage: FAILED",
        "Check failed at: critical coverage",
    ]


def test_the_coverage_report_is_written_outside_the_repository(check) -> None:
    runner = Runner()
    check.main([], run=runner)
    target = Path(runner.calls[2][0][-1].removeprefix("--cov-report=json:"))
    assert ROOT not in target.parents
    assert not target.exists()


def test_with_real_samples(check, capsys) -> None:
    runner = Runner()
    assert check.main(["--real-samples"], run=runner) == 0
    assert runner.calls[-1][0][3] == "tests/real_samples/check_real_samples.py"
    assert capsys.readouterr().out.splitlines()[-3:] == [
        "  critical coverage: passed",
        "  real samples: passed",
        "All checks passed.",
    ]


def test_a_failing_real_sample_fails_the_check(check, capsys) -> None:
    runner = Runner(codes={"--no-cov": 1})
    assert check.main(["--real-samples"], run=runner) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "Check failed at: real samples"


def test_an_unknown_option_is_refused(check, capsys) -> None:
    with pytest.raises(SystemExit) as stopped:
        check.main(["--fast"], run=Runner())
    assert stopped.value.code == 2
    assert "--fast" in capsys.readouterr().err
```

`tests/e2e/test_git_hooks.py`

```python
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "scripts" / "git-hooks" / "pre-commit"
INSTALLED = "Installed the pre-commit hook: lint and format are checked before each commit.\n"
NOT_OURS = "Error: another pre-commit hook is already installed; remove it first\n"
FOREIGN = "#!/bin/sh\necho someone else's hook\n"
ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=Probe",
            "-c",
            "user.email=probe@example.invalid",
            "-c",
            "core.hooksPath=.git/hooks",
            *args,
        ],
        check=False,
        cwd=root,
        env=ENV,
        capture_output=True,
        text=True,
    )


def script(root: Path, name: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", f"scripts/{name}"],
        check=False,
        cwd=root,
        env=ENV,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A new git repository holding the hook scripts, using this project's virtual environment."""
    root = tmp_path / "repo"
    (root / "scripts" / "git-hooks").mkdir(parents=True)
    for name in ("install-git-hooks.sh", "uninstall-git-hooks.sh"):
        shutil.copy(ROOT / "scripts" / name, root / "scripts" / name)
    shutil.copy(HOOK, root / "scripts" / "git-hooks" / "pre-commit")
    (root / ".venv").symlink_to(ROOT / ".venv")
    assert git(root, "init", "-q").returncode == 0
    return root


def installed(root: Path) -> Path:
    return root / ".git" / "hooks" / "pre-commit"


def commit(root: Path, name: str, text: str) -> subprocess.CompletedProcess:
    (root / name).write_text(text)
    git(root, "add", name)
    return git(root, "commit", "-q", "-m", f"add {name}")


def test_the_hook_is_executable_and_runs_lint_then_format() -> None:
    text = HOOK.read_text()
    assert text.startswith("#!/bin/sh\n# finances pre-commit hook")
    assert '"$PY" -m ruff check . && "$PY" -m ruff format --check .' in text
    assert HOOK.stat().st_mode & stat.S_IXUSR


def test_install_copies_the_hook(repo: Path) -> None:
    result = script(repo, "install-git-hooks.sh")
    assert (result.returncode, result.stdout, result.stderr) == (0, INSTALLED, "")
    assert installed(repo).read_text() == HOOK.read_text()
    assert installed(repo).stat().st_mode & stat.S_IXUSR


def test_install_again_replaces_our_own_hook(repo: Path) -> None:
    script(repo, "install-git-hooks.sh")
    result = script(repo, "install-git-hooks.sh")
    assert (result.returncode, result.stdout) == (0, INSTALLED)
    assert installed(repo).read_text() == HOOK.read_text()


def test_install_leaves_another_hook_alone(repo: Path) -> None:
    installed(repo).write_text(FOREIGN)
    result = script(repo, "install-git-hooks.sh")
    assert (result.returncode, result.stdout, result.stderr) == (1, "", NOT_OURS)
    assert installed(repo).read_text() == FOREIGN


def test_a_clean_commit_goes_through(repo: Path) -> None:
    script(repo, "install-git-hooks.sh")
    result = commit(repo, "clean.py", "VALUE = 1\n")
    assert result.returncode == 0, result.stderr
    assert git(repo, "log", "--oneline").stdout.count("\n") == 1


@pytest.mark.parametrize(
    ("text", "reason"),
    [("import os\n", "lint"), ("VALUE=1\n", "format")],
)
def test_a_commit_with_a_problem_is_stopped(repo: Path, text: str, reason: str) -> None:
    script(repo, "install-git-hooks.sh")
    result = commit(repo, "bad.py", text)
    assert result.returncode != 0, reason
    assert "Commit stopped: fix the lint or format problems above, then commit again." in (
        result.stderr
    )
    assert "Formatting is fixed with: .venv/bin/python -m ruff format ." in result.stderr
    assert git(repo, "log", "--oneline").returncode != 0


def test_without_the_hook_nothing_is_checked(repo: Path) -> None:
    assert commit(repo, "bad.py", "VALUE=1\n").returncode == 0


def test_uninstall_removes_only_our_hook(repo: Path) -> None:
    script(repo, "install-git-hooks.sh")
    result = script(repo, "uninstall-git-hooks.sh")
    assert (result.returncode, result.stdout, result.stderr) == (
        0,
        "Removed the pre-commit hook.\n",
        "",
    )
    assert not installed(repo).exists()
    result = script(repo, "uninstall-git-hooks.sh")
    assert (result.returncode, result.stdout) == (
        0,
        "No pre-commit hook was installed.\n",
    )


def test_uninstall_leaves_another_hook_alone(repo: Path) -> None:
    installed(repo).write_text(FOREIGN)
    result = script(repo, "uninstall-git-hooks.sh")
    assert (result.returncode, result.stdout, result.stderr) == (
        1,
        "",
        "Error: the pre-commit hook is not ours; it was left in place\n",
    )
    assert installed(repo).read_text() == FOREIGN
```

## Rules for this phase

- **Nothing written into the repository by a check.** The coverage report goes to a temporary folder. The hook and the scripts write only `.git/hooks/pre-commit`, and only when the owner runs the install script.
- **No new dependency.** `scripts/check.py` uses the standard library.
- **Privacy rule 6.** `--real-samples` runs the existing opt-in check, which prints counts only. Run it only on the machine that holds `data/samples/`, and report pass or fail, never content.
- **Git.** Do not commit. Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`. Do not run the install script in this repository; the tests use a throwaway repository.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`, with the summary listing `lint`, `format`, `tests`, `critical coverage` as passed |
| `.venv/bin/python -m pytest tests/unit/test_check_script.py tests/e2e/test_git_hooks.py --no-cov` | exactly `25 passed` |
| the test count in the check's `tests` step | 0 failed, 0 skipped, 0 xfailed, no warnings summary, at least N + 25 passed |
| `ls -l scripts/check.py scripts/install-git-hooks.sh scripts/uninstall-git-hooks.sh scripts/git-hooks/pre-commit` | the last three are executable |
| `git grep -n --untracked -E "^ *(import|from) +finances|subprocess\.run\([^)]*shell=True" -- scripts/check.py` | no output |
| `git status --short --ignored coverage.json .coverage.json` | nothing |
| `git status --short` | only the paths in the Scope table |

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 10: quality gates (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. In your final message, give the last ten lines of `scripts/check.py`'s output and the output line of each other acceptance command.
