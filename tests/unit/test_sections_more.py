import importlib.util
import json
import sys
from pathlib import Path

import pytest

from tests.unit.test_sections import ROOT, SCRIPT, SMALL, Runner, case, junit


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location("check_script_sections_more", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_command_returns_the_exit_code(check) -> None:
    assert check.run_command([sys.executable, "-c", "raise SystemExit(3)"], ROOT) == 3


def test_a_full_run_without_a_junit_report_prints_no_table(check, capsys) -> None:
    def run(command: list[str], cwd: Path) -> int:
        for part in command:
            if part.startswith("--cov-report=json:"):
                modules = check.read_critical(check.CRITICAL_FILE.read_text(encoding="utf-8"))
                summary = {"summary": {"missing_lines": 0, "missing_branches": 0}}
                files = {f"src/finances/{module}": summary for module in modules}
                Path(part.removeprefix("--cov-report=json:")).write_text(
                    json.dumps({"files": files})
                )
        return 0

    assert check.main([], run=run) == 0
    out = capsys.readouterr().out
    assert "Sections:" not in out
    assert out.splitlines()[-1] == "All checks passed."


def test_section_file_names_use_forward_slashes(check) -> None:
    files = check.section_files(["scripts"])
    assert files
    assert all(name == Path(name).as_posix() for name in files)
    assert all("\\" not in name for name in files)


def test_real_samples_print_the_table_once_after_tests(check, capsys) -> None:
    runner = Runner(check, junit(case("tests.unit.test_money", "test_a")))
    assert check.main(["--real-samples"], run=runner) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines.count("Sections:") == 1
    table = lines.index("Sections:")
    assert lines.index("== tests") < table < lines.index("== critical coverage")
    assert lines.index("== real samples") > lines.index("== critical coverage")


def test_first_with_a_name_twice_runs_the_files_once(check) -> None:
    runner = Runner(check, junit(case("tests.integration.test_web_menus", "test_a")))
    assert check.main(["--first", "web,web"], run=runner) == 0
    first = [command for command in runner.calls if "pytest" in command][0]
    files = [part for part in first if part.startswith("tests/")]
    assert files
    assert len(files) == len(set(files))


def test_first_with_real_samples_keeps_the_later_steps(check, tmp_path: Path) -> None:
    found = check.steps("/py", tmp_path / "c.json", real_samples=True, first=["scripts"])
    assert [step.name for step in found] == [
        "lint",
        "format",
        "tests (scripts)",
        "tests",
        "critical coverage",
        "real samples",
    ]


def test_a_case_with_failure_and_skipped_counts_as_failed(check) -> None:
    report = junit(
        '<testcase classname="tests.unit.test_money" name="test_a" time="0.001">'
        "<failure message='x'/><skipped message='x'/></testcase>"
    )
    assert check.tally(report, check.read_sections(SMALL))["core"] == check.Tally(
        passed=0, failed=1, skipped=0
    )
