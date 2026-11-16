import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def check():
    path = Path(__file__).resolve().parents[2] / "scripts/check.py"
    spec = importlib.util.spec_from_file_location("parallel_check_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("workers", [2, 4], ids=["two", "four"])
def test_workers_reach_both_test_steps(check, tmp_path, workers):
    steps = check.steps(
        "/py",
        tmp_path / "coverage.json",
        real_samples=True,
        first=["scripts"],
        workers=workers,
    )
    tests = [step.command for step in steps if step.name.startswith("tests")]
    assert len(tests) == 2
    for command in tests:
        assert command[command.index("-n") + 1] == str(workers)
        assert command[command.index("--dist") + 1] == "load"
    assert "-n" not in steps[-1].command


def test_default_stays_serial(check, tmp_path):
    steps = check.steps("/py", tmp_path / "coverage.json", real_samples=False)
    for step in steps:
        if step.command:
            assert "-n" not in step.command
            assert not any(arg.startswith("--durations") for arg in step.command)


@pytest.mark.parametrize("value", ["0", "-1", "auto"], ids=["zero", "negative", "auto"])
def test_invalid_workers_are_usage_errors(check, value, capsys):
    calls = []
    with pytest.raises(SystemExit) as stopped:
        check.main(["--workers", value], run=lambda cmd, cwd: calls.append(cmd) or 0)
    assert stopped.value.code == 2
    assert calls == []
    assert "--workers must be a positive integer" in capsys.readouterr().err


def test_section_forwards_workers_and_durations(check):
    calls = []
    assert (
        check.main(
            ["--section", "scripts", "--workers", "2", "--durations", "20"],
            run=lambda cmd, cwd: calls.append(cmd) or 0,
        )
        == 0
    )
    assert len(calls) == 1
    command = calls[0]
    assert command[command.index("-n") + 1] == "2"
    assert command[command.index("--dist") + 1] == "load"
    assert "--durations=20" in command
    assert "--no-cov" in command
