import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def check():
    spec = importlib.util.spec_from_file_location(
        "parallel_behavior_check", ROOT / "scripts/check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Runner:
    def __init__(self, check, *, fail_first=False, code=0, coverage="valid"):
        self.check = check
        self.fail_first = fail_first
        self.code = code
        self.coverage = coverage
        self.calls = []
        self.reports = []

    def __call__(self, command, cwd):
        self.calls.append((command, cwd))
        if "pytest" not in command:
            return 0
        first = "--no-cov" in command
        for arg in command:
            if arg.startswith("--junitxml="):
                path = Path(arg.split("=", 1)[1])
                path.write_text(
                    "<testsuites><testsuite>"
                    '<testcase classname="tests.unit.test_check_parallel" name="test_a"/>'
                    + (
                        ""
                        if first
                        else '<testcase classname="tests.integration.test_web_pages" '
                        'name="test_b"/>'
                        '<testcase classname="tests.unit.test_money" name="test_c"/>'
                    )
                    + "</testsuite></testsuites>",
                    encoding="utf-8",
                )
                self.reports.append(path)
            if arg.startswith("--cov-report=json:"):
                path = Path(arg.split(":", 1)[1])
                self.reports.append(path)
                if self.coverage == "missing":
                    continue
                if self.coverage == "valid":
                    modules = self.check.read_critical(self.check.CRITICAL_FILE.read_text())
                    data = {
                        "files": {
                            f"src/finances/{module}": {
                                "summary": {"missing_lines": 0, "missing_branches": 0}
                            }
                            for module in modules
                        }
                    }
                    content = json.dumps(data)
                else:
                    content = self.coverage
                path.write_text(content, encoding="utf-8")
        return self.code if not self.fail_first or first else 0


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_positive_workers_accepted(check, workers):
    runner = Runner(check)
    assert check.main(["--section", "scripts", "--workers", str(workers)], run=runner) == 0
    [command] = [cmd for cmd, _ in runner.calls]
    if workers == 1:
        assert "-n" not in command and "--dist" not in command
    else:
        assert command[-4:] == ["-n", str(workers), "--dist", "load"]


@pytest.mark.parametrize(
    "option,value,diagnostic",
    [
        ("--workers", "1.5", "--workers must be a positive integer"),
        ("--workers", "text", "--workers must be a positive integer"),
        ("--durations", "-1", "--durations must be a nonnegative integer"),
        ("--durations", "text", "--durations must be a nonnegative integer"),
        ("--durations", "1.5", "--durations must be a nonnegative integer"),
    ],
)
def test_invalid_options_launch_nothing(check, capsys, option, value, diagnostic):
    runner = Runner(check)
    with pytest.raises(SystemExit) as stopped:
        check.main([option, value], run=runner)
    assert stopped.value.code == 2
    assert runner.calls == []
    assert diagnostic in capsys.readouterr().err


def test_explicit_zero_durations_omits_flag(check):
    runner = Runner(check)
    assert check.main(["--durations", "0"], run=runner) == 0
    assert not any(arg.startswith("--durations") for cmd, _ in runner.calls for arg in cmd)


def test_flags_reach_first_and_full_only(check, tmp_path):
    steps = check.steps(
        "/py",
        tmp_path / "coverage.json",
        real_samples=True,
        first=["scripts"],
        workers=4,
        durations=20,
    )
    tests = [step for step in steps if step.name.startswith("tests")]
    assert [step.name for step in tests] == ["tests (scripts)", "tests"]
    for step in tests:
        assert step.command[-5:] == ["-n", "4", "--dist", "load", "--durations=20"]
    assert "--no-cov" in tests[0].command and "--no-cov" not in tests[1].command
    assert steps[-1].command == [
        "/py",
        "-m",
        "pytest",
        "tests/real_samples/check_real_samples.py",
        "--no-cov",
        "-rA",
    ]
    assert steps[0].command == ["/py", "-m", "ruff", "check", "."]
    assert steps[1].command == ["/py", "-m", "ruff", "format", "--check", "."]
    assert steps[-2].command is None


def test_section_can_time_serial_tests(check):
    runner = Runner(check)
    assert (
        check.main(["--section", "scripts", "--workers", "1", "--durations", "3"], run=runner) == 0
    )
    [command] = [cmd for cmd, _ in runner.calls]
    assert "-n" not in command and "--dist" not in command
    assert command[-1] == "--durations=3"
    assert "--no-cov" in command


def test_failed_first_prevents_full_tests(check, capsys):
    runner = Runner(check, fail_first=True, code=1)
    assert check.main(["--first", "scripts", "--workers", "4"], run=runner) == 1
    tests = [cmd for cmd, _ in runner.calls if "pytest" in cmd]
    assert len(tests) == 1 and "--no-cov" in tests[0]
    out = capsys.readouterr().out
    assert "  tests: not run" in out
    assert "  critical coverage: not run" in out
    assert out.endswith("Check failed at: tests (scripts)\n")


@pytest.mark.parametrize("code", [1, 2, 3, 4])
def test_pytest_failure_or_worker_crash_stops_coverage(check, capsys, monkeypatch, code):
    def forbidden(_):
        pytest.fail("critical coverage ran after a failed pytest process")

    monkeypatch.setattr(check, "_critical_coverage", forbidden)
    runner = Runner(check, code=code)
    assert check.main(["--workers", "4"], run=runner) == 1
    out = capsys.readouterr().out
    assert "  critical coverage: not run" in out
    assert "All checks passed." not in out


@pytest.mark.parametrize(
    "coverage",
    [
        "missing",
        "{",
        "{}",
        "null",
        '{"files": []}',
        '{"files": {"src/finances/domain/money.py": {}}}',
    ],
)
def test_missing_or_malformed_coverage_fails(check, capsys, coverage):
    runner = Runner(check, coverage=coverage)
    assert check.main(["--workers", "2"], run=runner) == 1
    out = capsys.readouterr().out
    assert "All checks passed." not in out
    assert out.endswith("Check failed at: critical coverage\n")


@pytest.mark.parametrize("count", [None, False, -1])
def test_invalid_coverage_counts_cannot_pass(check, capsys, count):
    coverage = json.dumps(
        {
            "files": {
                "src/finances/domain/money.py": {
                    "summary": {"missing_lines": count, "missing_branches": 0}
                }
            }
        }
    )
    assert check.main(["--workers", "2"], run=Runner(check, coverage=coverage)) == 1
    out = capsys.readouterr().out
    assert "Coverage report missing or malformed." in out
    assert "All checks passed." not in out


def test_parallel_reports_root_interpreter_cleanup_and_summary(check, capsys):
    runner = Runner(check)
    assert (
        check.main(["--first", "scripts", "--workers", "4", "--durations", "20"], run=runner) == 0
    )
    assert len(runner.calls) == 4
    assert all(cmd[0] == sys.executable and cwd == ROOT for cmd, cwd in runner.calls)
    assert runner.reports and all(ROOT not in path.parents for path in runner.reports)
    assert all(not path.exists() for path in runner.reports)
    lines = capsys.readouterr().out.splitlines()
    assert lines.count("Sections:") == 2
    full = lines.index("Sections:", lines.index("== tests") + 1)
    assert lines[full : full + 9] == [
        "Sections:",
        "  migrations      0 passed    0 failed    0 skipped",
        "  scripts         1 passed    0 failed    0 skipped",
        "  web             1 passed    0 failed    0 skipped",
        "  cli             0 passed    0 failed    0 skipped",
        "  mcp             0 passed    0 failed    0 skipped",
        "  parsers         0 passed    0 failed    0 skipped",
        "  sync            0 passed    0 failed    0 skipped",
        "  core            1 passed    0 failed    0 skipped",
    ]
    assert lines[-7:] == [
        "Summary:",
        "  lint: passed",
        "  format: passed",
        "  tests (scripts): passed",
        "  tests: passed",
        "  critical coverage: passed",
        "All checks passed.",
    ]


def test_both_new_files_belong_to_scripts(check):
    sections = check.read_sections(check.SECTIONS_FILE.read_text(encoding="utf-8"))
    for name in ("test_check_parallel.py", "test_check_parallel_behavior.py"):
        assert check.section_of(f"unit/{name}", sections) == "scripts"
        assert f"tests/unit/{name}" in check.section_files(["scripts"])
