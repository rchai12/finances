# Phase 40: test sections

## Goal

`scripts/check.py` runs all 4,000-odd tests as one pytest call, so a failure is one long list with no sign of which part of the app broke. With the owner's choices (2026-10-25):

- every test file belongs to one of eight **sections** named in `tests/sections.toml`, by file-name patterns; no test file moves;
- a full run prints a table after the tests step, one line per section with its passed, failed, and skipped counts, and a ready command to rerun a section that failed;
- `scripts/check.py --first web` (or `--first parsers,sync`) tests the phase's own sections first: if any of their tests fail, the check stops there with those sections' table, and only once they pass does the full run follow. A phase's spec names its sections, and its acceptance command becomes `check.py --first <its sections>`;
- `scripts/check.py --section NAME` runs that section's files alone, in seconds instead of minutes, while a failure is being fixed;
- a file that fails to import no longer stops the whole run, so the table still shows every other section;
- the coverage gates stay on the full run; tests still run one at a time (no parallel runner).

| Section | Holds |
|---|---|
| `migrations` | every Alembic migration test |
| `scripts` | the check script, its sections, and the git hooks |
| `web` | web pages, forms, styles, the session gate |
| `cli` | the terminal commands |
| `mcp` | the agent's tools |
| `parsers` | statement parsers, PDF text, reconciliation, dedup, statement import |
| `sync` | the SimpleFIN client, transport, feed, sync runs |
| `core` | everything else: domain rules, analysis, categorizing, repositories, views |

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `scripts/check.py`, `tests/unit/test_check_script.py` (its `Runner`, and the lines it pins), `docs/testing.md` ("Commands")

## Starting state

N is `4028` when Phase 39 is the last phase built. `check.py` has the steps `lint`, `format`, `tests`, `critical coverage`, and with `--real-samples` a fifth. Its tests load it by path, so everything it uses lives in that one file. No migration; no new dependency (`tomllib` and `xml.etree` are in the standard library).

## Scope

| Path | What changes |
|---|---|
| `tests/sections.toml` | new: given |
| `scripts/check.py` | the sections, the table, `--section` (R1 to R6) |
| `tests/unit/test_check_script.py` | the given diff (R7) |
| `tests/unit/test_sections.py` | new: given |
| `tests/unit/test_sections_more.py` | new: yours ("Tests to write") |
| `docs/testing.md` | the given text (R8) |
| `docs/progress.md` | one new entry |

## Out of scope

- Moving or renaming any test file; markers on tests; changes to `tests/conftest.py` or `pyproject.toml`.
- Parallel runs (`pytest-xdist`); a coverage gate per section; running sections one after another.
- `docs/phase-conventions.md` and the skill files: the architect updates them once this phase passes.

## Dependencies

None new.

## Design

```python
# scripts/check.py
SECTIONS_FILE = ROOT / "tests" / "sections.toml"

@dataclass(frozen=True)
class Tally:
    passed: int
    failed: int
    skipped: int

def read_sections(text: str) -> list[tuple[str, list[str]]]: ...
def section_of(path: str, sections: list[tuple[str, list[str]]]) -> str: ...
def tally(report: str, sections: list[tuple[str, list[str]]]) -> dict[str, Tally]: ...
def section_lines(tallies: dict[str, Tally]) -> list[str]: ...
def section_files(names: list[str]) -> list[str]: ...
def steps(python: str, coverage_json: Path, *, real_samples: bool, first: list[str] | None = None) -> list[Step]: ...
```

| Name | Rule |
|---|---|
| `read_sections` | the `[[section]]` tables of the TOML text, in order, as `(name, patterns)` |
| `section_of` | `path` is relative to `tests/` with forward slashes (`unit/test_money.py`); the first section with a pattern that matches it (`fnmatch.fnmatchcase`) wins; none: `ValueError("no section for <path>")` |
| `tally` | `report` is pytest's JUnit XML. Each `testcase`'s file comes from its `classname` (`tests.unit.test_money`, or `tests.integration.test_web_pages.TestPages` for a test in a class): the two parts after `tests` give `unit/test_money.py`. A case with an empty `classname` is a file that failed to import, and its `name` holds the module (`tests.unit.test_broken`). A case with a `failure` or `error` child is failed, one with `skipped` is skipped, and any other passed. Every section is in the result, in the sections' order, zeros included |
| `section_files` | `tests/<path>` of every test file under `tests/unit`, `tests/integration`, and `tests/e2e` that one of the named sections takes (by `section_of` over `SECTIONS_FILE`), sorted, with forward slashes |
| `section_lines` | `Sections:`, then one line per entry in order: `f"  {name:<11}{passed:>6} passed{failed:>5} failed{skipped:>5} skipped"`, followed by `f"  rerun: .venv/bin/python scripts/check.py --section {name}"` on the same line when failed is not zero |

| Command | Behaviour |
|---|---|
| `check.py` (full run) | the `tests` step's command gains `--junitxml=<coverage report's folder>/junit.xml` and `--continue-on-collection-errors`; after that step runs, passed or failed, the table is printed from that report, before the next step's `== ` header or the summary. No report (pytest did not write one): no table. Everything else is unchanged |
| `check.py --first A[,B…]` | the names are split on commas; each must be a section, or `argparse` refuses with `unknown section: NAME` (exit 2, through `parser.error`). `steps(..., first=[A, B])` puts one step between `format` and `tests`, named `tests (A,B)` (the names as given, joined by commas), with the command `[python, "-m", "pytest", "--no-cov", "--junitxml=<coverage report's folder>/first.xml", "--continue-on-collection-errors", *section_files([A, B])]`. After it runs, passed or failed, the table of those sections alone (in the sections' order) is printed from its report. A failure stops the check like any step: `Check failed at: tests (A,B)`, the later steps `not run`. Without `--first`, `steps` returns what it returns today. It combines with `--real-samples`, not with `--section` (exit 2) |
| `check.py --section NAME` | `NAME` is one of the sections (`argparse` `choices`, so an unknown name exits 2 with `invalid choice`); one command: `[python, "-m", "pytest", "--no-cov", "--junitxml=<temporary>/junit.xml", "--continue-on-collection-errors", *files]`, where `files` are `section_files([NAME])`; then the table for that section alone, then `Section NAME: passed.` or `Section NAME: FAILED.`; the exit code is 0 or 1. No lint, format, or coverage. With `--real-samples` it is refused by `argparse` (exit 2) |

## Requirements

- **R1.** `read_sections`, `section_of`, `Tally`, `tally`, and `section_lines` as designed.
- **R2.** `SECTIONS_FILE` as designed; the given `tests/sections.toml`.
- **R3.** The full run's `tests` step and its table as designed. The lines the earlier tests of `check.py` pin (the summary, the step headers, the last line) do not change.
- **R4.** `--section` and `--first` as designed, `section_files` among them.
- **R5.** `run_command` returns the command's exit code (a test runs a real one-line command); the `if __name__ == "__main__":` line may carry `# pragma: no cover`. `scripts/check.py` reaches 100% line and branch coverage.
- **R6.** The table and `--section` read `SECTIONS_FILE` each run; a file the sections do not take can only be a bug in `tests/sections.toml`, since its last section takes `*`.
- **R7.** Apply the given diff to `tests/unit/test_check_script.py`. No other earlier test changes.
- **R8.** In `docs/testing.md`, under "Commands", add `.venv/bin/python scripts/check.py --first web     # the web section first; the full check only once it passes` and `.venv/bin/python scripts/check.py --section web   # one section alone, no coverage (names in tests/sections.toml)` to the code block after the `--real-samples` line, and after the block this paragraph: "A phase names its sections, and its check is `check.py --first <its sections>`: their tests run first, and the full run only once they pass. A full run prints a table of the eight sections after the tests, with a rerun command beside any section that failed. A new test file belongs in the section of the code it tests: add a pattern to `tests/sections.toml` when `core` would take it otherwise."

## Given section list

`tests/sections.toml` (do not change):

```toml
# Which section each test file belongs to, for `scripts/check.py --section NAME` and the table a
# full run prints. Paths are relative to tests/ and matched with fnmatch. Sections are tried in this
# order and the first that matches wins; the last, core, takes every file the others leave.

[[section]]
name = "migrations"
patterns = ["integration/test_migrat*.py"]

[[section]]
name = "scripts"
patterns = ["unit/test_check_script.py", "unit/test_sections*.py", "e2e/test_git_hooks.py"]

[[section]]
name = "web"
patterns = [
    "*/test_web_*.py",
    "unit/test_session.py",
    "unit/test_chart_*.py",
    "integration/test_account_page_more.py",
    "integration/test_backups_page_more.py",
    "integration/test_dashboard_more.py",
]

[[section]]
name = "cli"
patterns = ["e2e/test_cli*.py", "unit/test_print_table.py"]

[[section]]
name = "mcp"
patterns = ["*/test_mcp_*.py"]

[[section]]
name = "parsers"
patterns = [
    "unit/test_*parser*.py",
    "unit/test_find_labeled_amount.py",
    "unit/test_pdf_text*.py",
    "unit/test_reconcile.py",
    "unit/test_dedup.py",
    "unit/test_statement*.py",
    "unit/test_properties_ingest.py",
    "integration/test_*import*.py",
    "integration/test_statement*.py",
    "integration/test_supersede_repositories.py",
]

[[section]]
name = "sync"
patterns = [
    "unit/test_simplefin*.py",
    "unit/test_transport*.py",
    "unit/test_links.py",
    "unit/test_run_links.py",
    "unit/test_link_run_failures.py",
    "unit/test_feed_*.py",
    "integration/test_feed_*.py",
    "integration/test_sync_*.py",
    "integration/test_seen_feed_accounts.py",
]

[[section]]
name = "core"
patterns = ["*"]
```

## Given diff to an earlier test

```text
diff --git a/tests/unit/test_check_script.py b/tests/unit/test_check_script.py
index 46ed073..3273946 100644
--- a/tests/unit/test_check_script.py
+++ b/tests/unit/test_check_script.py
@@ -127,7 +127,17 @@ def test_the_steps_in_order(check, tmp_path: Path) -> None:
     assert [(step.name, step.command) for step in steps] == [
         ("lint", ["/py", "-m", "ruff", "check", "."]),
         ("format", ["/py", "-m", "ruff", "format", "--check", "."]),
-        ("tests", ["/py", "-m", "pytest", f"--cov-report=json:{target}"]),
+        (
+            "tests",
+            [
+                "/py",
+                "-m",
+                "pytest",
+                f"--cov-report=json:{target}",
+                f"--junitxml={target.with_name('junit.xml')}",
+                "--continue-on-collection-errors",
+            ],
+        ),
         ("critical coverage", None),
     ]
 
```

## Given tests

34 tests in one file. Do not change them.

`tests/unit/test_sections.py`

```python
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check.py"
NAMES = ["migrations", "scripts", "web", "cli", "mcp", "parsers", "sync", "core"]
SMALL = """
[[section]]
name = "web"
patterns = ["*/test_web_*.py"]

[[section]]
name = "cli"
patterns = ["e2e/test_cli*.py"]

[[section]]
name = "core"
patterns = ["*"]
"""


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location("check_script_sections", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case(classname: str, name: str, outcome: str = "") -> str:
    inner = f"<{outcome} message='x'/>" if outcome else ""
    return f'<testcase classname="{classname}" name="{name}" time="0.001">{inner}</testcase>'


def junit(*cases: str) -> str:
    return f"<testsuites><testsuite name='pytest'>{''.join(cases)}</testsuite></testsuites>"


class Runner:
    """Stands in for subprocess: writes the reports a pytest run would and answers with a code,
    for every pytest command or, with only, for those that hold that word."""

    def __init__(self, check, report: str, code: int = 0, only: str = "") -> None:
        self.check = check
        self.report = report
        self.code = code
        self.only = only
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str], cwd: Path) -> int:
        self.calls.append(command)
        if "pytest" not in command:
            return 0
        for part in command:
            if part.startswith("--junitxml="):
                Path(part.removeprefix("--junitxml=")).write_text(self.report)
            if part.startswith("--cov-report=json:"):
                modules = self.check.read_critical(self.check.CRITICAL_FILE.read_text())
                summary = {"summary": {"missing_lines": 0, "missing_branches": 0}}
                files = {f"src/finances/{module}": summary for module in modules}
                Path(part.removeprefix("--cov-report=json:")).write_text(
                    json.dumps({"files": files})
                )
        return self.code if not self.only or self.only in command else 0


def pytest_calls(runner: Runner) -> list[list[str]]:
    return [command for command in runner.calls if "pytest" in command]


# Reading the sections


def test_the_sections_keep_their_order(check) -> None:
    assert check.read_sections(SMALL) == [
        ("web", ["*/test_web_*.py"]),
        ("cli", ["e2e/test_cli*.py"]),
        ("core", ["*"]),
    ]


def test_the_first_section_that_matches_wins(check) -> None:
    sections = check.read_sections(SMALL)
    assert check.section_of("integration/test_web_pages.py", sections) == "web"
    assert check.section_of("e2e/test_cli_web.py", sections) == "cli"
    assert check.section_of("unit/test_money.py", sections) == "core"


def test_a_file_that_no_section_takes_is_refused(check) -> None:
    with pytest.raises(ValueError) as error:
        check.section_of("unit/test_money.py", [("web", ["*/test_web_*.py"])])
    assert str(error.value) == "no section for unit/test_money.py"


def test_the_shipped_sections(check) -> None:
    assert check.SECTIONS_FILE == ROOT / "tests" / "sections.toml"
    sections = check.read_sections(check.SECTIONS_FILE.read_text(encoding="utf-8"))
    assert [name for name, _ in sections] == NAMES
    assert sections[-1] == ("core", ["*"])


@pytest.mark.parametrize(
    ("path", "section"),
    [
        ("integration/test_migration_0021.py", "migrations"),
        ("integration/test_migrate.py", "migrations"),
        ("unit/test_check_script.py", "scripts"),
        ("unit/test_sections.py", "scripts"),
        ("integration/test_web_menus.py", "web"),
        ("unit/test_web_style.py", "web"),
        ("unit/test_session.py", "web"),
        ("e2e/test_cli_import.py", "cli"),
        ("integration/test_mcp_more.py", "mcp"),
        ("unit/test_boa_deposit_parser.py", "parsers"),
        ("integration/test_truist_marcus_import.py", "parsers"),
        ("unit/test_simplefin.py", "sync"),
        ("integration/test_sync_runner.py", "sync"),
        ("unit/test_money.py", "core"),
        ("integration/test_pairing_gaps.py", "core"),
    ],
)
def test_a_file_in_each_shipped_section(check, path: str, section: str) -> None:
    sections = check.read_sections(check.SECTIONS_FILE.read_text(encoding="utf-8"))
    assert (ROOT / "tests" / path).is_file()
    assert check.section_of(path, sections) == section


def test_every_shipped_section_takes_a_test_file(check) -> None:
    sections = check.read_sections(check.SECTIONS_FILE.read_text(encoding="utf-8"))
    files = [
        path.relative_to(ROOT / "tests").as_posix()
        for layer in ("unit", "integration", "e2e")
        for path in (ROOT / "tests" / layer).glob("test_*.py")
    ]
    taken = {check.section_of(path, sections) for path in files}
    assert taken == set(NAMES)


# Counting by section


def test_each_outcome_is_counted_in_its_files_section(check) -> None:
    report = junit(
        case("tests.integration.test_web_pages", "test_a"),
        case("tests.integration.test_web_pages", "test_b", "failure"),
        case("tests.unit.test_web_style", "test_c", "error"),
        case("tests.unit.test_money", "test_d"),
        case("tests.unit.test_money", "test_e", "skipped"),
        case("tests.integration.test_web_pages.TestPages", "test_f"),
        case("", "tests.unit.test_broken", "error"),
    )
    assert check.tally(report, check.read_sections(SMALL)) == {
        "web": check.Tally(passed=2, failed=2, skipped=0),
        "cli": check.Tally(passed=0, failed=0, skipped=0),
        "core": check.Tally(passed=1, failed=1, skipped=1),
    }


def test_the_table(check) -> None:
    tallies = {
        "migrations": check.Tally(passed=2, failed=0, skipped=0),
        "web": check.Tally(passed=1, failed=2, skipped=0),
        "parsers": check.Tally(passed=1234, failed=0, skipped=0),
        "core": check.Tally(passed=0, failed=0, skipped=1),
    }
    assert check.section_lines(tallies) == [
        "Sections:",
        "  migrations      2 passed    0 failed    0 skipped",
        "  web             1 passed    2 failed    0 skipped"
        "  rerun: .venv/bin/python scripts/check.py --section web",
        "  parsers      1234 passed    0 failed    0 skipped",
        "  core            0 passed    0 failed    1 skipped",
    ]


# A full run


def test_a_full_run_prints_the_table_after_the_tests(check, capsys) -> None:
    runner = Runner(check, junit(case("tests.unit.test_money", "test_a")))
    assert check.main([], run=runner) == 0
    lines = capsys.readouterr().out.splitlines()
    table = lines.index("Sections:")
    assert lines[table : table + 9] == [
        "Sections:",
        "  migrations      0 passed    0 failed    0 skipped",
        "  scripts         0 passed    0 failed    0 skipped",
        "  web             0 passed    0 failed    0 skipped",
        "  cli             0 passed    0 failed    0 skipped",
        "  mcp             0 passed    0 failed    0 skipped",
        "  parsers         0 passed    0 failed    0 skipped",
        "  sync            0 passed    0 failed    0 skipped",
        "  core            1 passed    0 failed    0 skipped",
    ]
    assert lines.index("== tests") < table < lines.index("== critical coverage")
    assert lines[-1] == "All checks passed."


def test_failing_tests_still_print_the_table(check, capsys) -> None:
    report = junit(case("tests.integration.test_mcp_more", "test_a", "failure"))
    assert check.main([], run=Runner(check, report, code=1)) == 1
    lines = capsys.readouterr().out.splitlines()
    assert (
        "  mcp             0 passed    1 failed    0 skipped"
        "  rerun: .venv/bin/python scripts/check.py --section mcp"
    ) in lines
    assert lines[-1] == "Check failed at: tests"


# One section


def test_a_section_runs_only_its_own_files(check, capsys) -> None:
    runner = Runner(check, junit(case("tests.unit.test_check_script", "test_a")))
    assert check.main(["--section", "scripts"], run=runner) == 0
    [command] = runner.calls
    assert command[:4] == [sys.executable, "-m", "pytest", "--no-cov"]
    assert command[4].startswith("--junitxml=")
    assert command[5] == "--continue-on-collection-errors"
    files = command[6:]
    assert files == sorted(files)
    assert {"tests/e2e/test_git_hooks.py", "tests/unit/test_check_script.py"} <= set(files)
    assert "tests/unit/test_money.py" not in files
    assert all(name.startswith("tests/") and name.endswith(".py") for name in files)
    assert capsys.readouterr().out.splitlines()[-3:] == [
        "Sections:",
        "  scripts         1 passed    0 failed    0 skipped",
        "Section scripts: passed.",
    ]


def test_a_failing_section(check, capsys) -> None:
    report = junit(case("tests.unit.test_check_script", "test_a", "failure"))
    assert check.main(["--section", "scripts"], run=Runner(check, report, code=1)) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "Section scripts: FAILED."


def test_an_unknown_section_is_refused(check, capsys) -> None:
    with pytest.raises(SystemExit) as stopped:
        check.main(["--section", "nope"], run=Runner(check, junit()))
    assert stopped.value.code == 2
    assert "invalid choice: 'nope'" in capsys.readouterr().err


def test_a_section_with_real_samples_is_refused(check, capsys) -> None:
    with pytest.raises(SystemExit) as stopped:
        check.main(["--section", "web", "--real-samples"], run=Runner(check, junit()))
    assert stopped.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


# The phase's sections first


def test_the_steps_with_sections_first(check, tmp_path: Path) -> None:
    target = tmp_path / "coverage.json"
    steps = check.steps("/py", target, real_samples=False, first=["web"])
    assert [step.name for step in steps] == [
        "lint",
        "format",
        "tests (web)",
        "tests",
        "critical coverage",
    ]
    command = steps[2].command
    assert command[:6] == [
        "/py",
        "-m",
        "pytest",
        "--no-cov",
        f"--junitxml={target.with_name('first.xml')}",
        "--continue-on-collection-errors",
    ]
    files = command[6:]
    assert files == sorted(files)
    assert "tests/integration/test_web_menus.py" in files
    assert "tests/unit/test_money.py" not in files
    assert steps[3].command == check.steps("/py", target, real_samples=False)[2].command


def test_the_first_sections_pass_then_everything_runs(check, capsys) -> None:
    runner = Runner(check, junit(case("tests.integration.test_web_menus", "test_a")))
    assert check.main(["--first", "web"], run=runner) == 0
    first, full = pytest_calls(runner)
    assert "--no-cov" in first and "--no-cov" not in full
    lines = capsys.readouterr().out.splitlines()
    table = lines.index("Sections:", lines.index("== tests (web)"))
    assert lines[table : table + 3] == [
        "Sections:",
        "  web             1 passed    0 failed    0 skipped",
        "== tests",
    ]
    assert lines[-7:] == [
        "Summary:",
        "  lint: passed",
        "  format: passed",
        "  tests (web): passed",
        "  tests: passed",
        "  critical coverage: passed",
        "All checks passed.",
    ]


def test_a_failing_first_section_stops_the_check(check, capsys) -> None:
    report = junit(case("tests.integration.test_web_menus", "test_a", "failure"))
    runner = Runner(check, report, code=1, only="--no-cov")
    assert check.main(["--first", "web"], run=runner) == 1
    assert len(pytest_calls(runner)) == 1
    lines = capsys.readouterr().out.splitlines()
    assert (
        "  web             0 passed    1 failed    0 skipped"
        "  rerun: .venv/bin/python scripts/check.py --section web"
    ) in lines
    assert lines[-4:] == [
        "  tests (web): FAILED",
        "  tests: not run",
        "  critical coverage: not run",
        "Check failed at: tests (web)",
    ]


def test_two_sections_first(check, capsys) -> None:
    runner = Runner(check, junit())
    assert check.main(["--first", "parsers,sync"], run=runner) == 0
    first = pytest_calls(runner)[0]
    assert {"tests/unit/test_boa_deposit_parser.py", "tests/unit/test_simplefin.py"} <= set(first)
    assert "tests/unit/test_money.py" not in first
    out = capsys.readouterr().out.splitlines()
    assert "  tests (parsers,sync): passed" in out
    table = out.index("Sections:")
    assert out[table + 1].startswith("  parsers ") and out[table + 2].startswith("  sync ")


def test_an_unknown_first_section_is_refused(check, capsys) -> None:
    with pytest.raises(SystemExit) as stopped:
        check.main(["--first", "web,nope"], run=Runner(check, junit()))
    assert stopped.value.code == 2
    assert "unknown section: nope" in capsys.readouterr().err


def test_first_with_one_section_alone_is_refused(check, capsys) -> None:
    with pytest.raises(SystemExit) as stopped:
        check.main(["--first", "web", "--section", "web"], run=Runner(check, junit()))
    assert stopped.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/unit/test_sections_more.py`:

- `run_command([sys.executable, "-c", "raise SystemExit(3)"], ROOT)` returns `3`;
- a full run whose pytest writes no JUnit report prints no `Sections:` line and still ends with the usual summary;
- the section run's file names use forward slashes on every system (the paths are built with `as_posix()`);
- a full run with `--real-samples` still prints the table once, after the `tests` step and not after the real-samples step;
- `--first web,web` runs the web files once (no file twice in the command);
- `--first scripts --real-samples` has the steps `lint`, `format`, `tests (scripts)`, `tests`, `critical coverage`, `real samples`;
- a `testcase` with both a `failure` and a `skipped` child counts once, as failed.

## Rules for this phase

- `check.py` stays one file: its tests load it by path.
- Earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file above, 34 tests; at least N + 34 passed in all;
- the full run's output shows the `Sections:` table with 0 failed on every line, and the eight counts of passed add up to the tests step's passed count;
- `.venv/bin/python scripts/check.py --section scripts` ends with `Section scripts: passed.`;
- `.venv/bin/python scripts/check.py --first scripts` ends with `All checks passed.`, its summary listing `tests (scripts): passed` before `tests: passed`;
- `git diff --stat HEAD -- tests` lists only `tests/unit/test_check_script.py`;
- the coverage command: `.venv/bin/python -m pytest tests/unit/test_check_script.py tests/unit/test_sections.py tests/unit/test_sections_more.py -o addopts="" --import-mode=importlib --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 40: test sections (YYYY-MM-DD)`.
