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
    "db/backup.py",
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
