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
