"""Run everything a phase must pass: lint, format, tests, and the critical coverage gate.

Run it as: .venv/bin/python scripts/check.py [--real-samples]
"""

import argparse
import json
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRITICAL_FILE = Path(__file__).resolve().parent / "critical_modules.txt"
COVERAGE_STEP = "critical coverage"


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str] | None


def read_critical(text: str) -> list[str]:
    """Return the module paths in the text, without comments and blank lines."""
    modules = []
    for line in text.splitlines():
        module = line.split("#", 1)[0].strip()
        if module:
            modules.append(module)
    return modules


def coverage_gaps(report: dict, modules: list[str]) -> list[str]:
    """Return one line for each module that is not fully covered, in the order of modules."""
    files = report["files"]
    gaps = []
    for module in modules:
        found = files.get(f"src/finances/{module}")
        if found is None:
            gaps.append(f"{module}: not measured")
            continue
        lines = found["summary"]["missing_lines"]
        branches = found["summary"]["missing_branches"]
        if lines or branches:
            gaps.append(f"{module}: {lines} lines and {branches} branches not covered")
    return gaps


def steps(python: str, coverage_json: Path, *, real_samples: bool) -> list[Step]:
    found = [
        Step("lint", [python, "-m", "ruff", "check", "."]),
        Step("format", [python, "-m", "ruff", "format", "--check", "."]),
        Step("tests", [python, "-m", "pytest", f"--cov-report=json:{coverage_json}"]),
        Step(COVERAGE_STEP, None),
    ]
    if real_samples:
        found.append(
            Step(
                "real samples",
                [
                    python,
                    "-m",
                    "pytest",
                    "tests/real_samples/check_real_samples.py",
                    "--no-cov",
                    "-rA",
                ],
            )
        )
    return found


def run_command(command: list[str], cwd: Path) -> int:
    return subprocess.run(command, cwd=cwd, check=False).returncode


def _critical_coverage(coverage_json: Path) -> bool:
    report = json.loads(coverage_json.read_text(encoding="utf-8"))
    modules = read_critical(CRITICAL_FILE.read_text(encoding="utf-8"))
    gaps = coverage_gaps(report, modules)
    for gap in gaps:
        print(f"  {gap}")
    return not gaps


def main(argv: list[str] | None = None, run: Callable[[list[str], Path], int] = run_command) -> int:
    parser = argparse.ArgumentParser(description="Run every check a phase must pass.")
    parser.add_argument(
        "--real-samples",
        action="store_true",
        help="Then check the real statements in data/samples/ (counts only).",
    )
    options = parser.parse_args(argv)
    results: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as folder:
        coverage_json = Path(folder) / "coverage.json"
        planned = steps(sys.executable, coverage_json, real_samples=options.real_samples)
        failed = None
        for step in planned:
            print(f"== {step.name}", flush=True)
            if step.command is None:
                passed = _critical_coverage(coverage_json)
            else:
                passed = run(step.command, ROOT) == 0
            results[step.name] = "passed" if passed else "FAILED"
            if not passed:
                failed = step.name
                break
    print()
    print("Summary:")
    for step in planned:
        print(f"  {step.name}: {results.get(step.name, 'not run')}")
    print("All checks passed." if failed is None else f"Check failed at: {failed}")
    return 0 if failed is None else 1


if __name__ == "__main__":
    sys.exit(main())
