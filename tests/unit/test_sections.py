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
