"""Run earlier tests against new templates before the routes that fill them exist.

A phase that replaces a template must not break the earlier tests that read the page. Before
publishing, run those tests in the scratch copy with the new templates, giving every page the
new context values the template expects (the coder's routes will supply them later):

    .venv/bin/python .claude/skills/phase-architect/template_check.py \
        --root <scratch copy> \
        --defaults '{"rename_form": {"name": "", "to": ""}, "select_all": false}' \
        tests/integration/test_web_pages.py tests/integration/test_web_categories.py -k web

Anything after the options goes to pytest (test paths, -k, -x).

It runs pytest in the scratch copy against the copy's own source (PYTHONPATH), with a small
plugin that wraps `finances.web.render._render` (route modules
import it by name when `create_app` first runs, after the plugin has replaced it)
so each page's context starts from the defaults.
Nothing in the copy is changed. Failures left are real: a template that breaks an earlier
test, or a template bug.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN = """
import json
import os

import finances.web.render as render

_DEFAULTS = json.loads(os.environ["FIN_TEMPLATE_DEFAULTS"])
_original = render._render


def _render(request, name, context, status_code=200):
    return _original(request, name, {**_DEFAULTS, **context}, status_code)


render._render = _render
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True, type=Path, help="the scratch copy")
    parser.add_argument("--defaults", default="{}", help="JSON object of context values")
    args, tests = parser.parse_known_args()
    json.loads(args.defaults)
    root = args.root.resolve()
    with tempfile.TemporaryDirectory() as folder:
        Path(folder, "_template_shim.py").write_text(PLUGIN, encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([folder, str(root / "src")])
        env["FIN_TEMPLATE_DEFAULTS"] = args.defaults
        command = [
            str(root / ".venv" / "bin" / "python"),
            "-m",
            "pytest",
            "-q",
            "--no-cov",
            "-p",
            "_template_shim",
            *(tests or ["tests/integration"]),
        ]
        return subprocess.run(command, cwd=root, env=env, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
