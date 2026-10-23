"""PreToolUse tripwire: the architect writing the phase's source in a scratch clone.

A scratch copy of the phase's source is a reference build, whatever it is called (see the
phase-architect skill, "Checking a spec before publishing"). Writes into `src/finances/`
under the scratchpad ask the owner first. Clones named `fail*` (the fail check, which
needs stub files) are allowed.
"""

import json
import re
import sys

WRITES = re.compile(
    r"(>>?\s*|sed\s+-i[^|;&]*|cp\s[^|;&]*|mv\s[^|;&]*|tee\s[^|;&]*|write_text|git\s+apply)"
    r"[^|;&]*src/finances/"
)
CLONES = re.compile(r"(?:scratchpad|\$S|\$\{S\})/([A-Za-z0-9_.-]+)")


def scratch_names(text: str) -> list[str]:
    return CLONES.findall(text)


def tripped(event: dict) -> bool:
    tool = event.get("tool_name", "")
    data = event.get("tool_input", {}) or {}
    cwd = event.get("cwd", "")
    if tool in ("Write", "Edit", "NotebookEdit"):
        path = data.get("file_path", "") or data.get("notebook_path", "")
        names = scratch_names(path)
        return "/src/finances/" in path and bool(names) and not names[0].startswith("fail")
    if tool == "Bash":
        command = data.get("command", "")
        names = scratch_names(command) + scratch_names(cwd)
        if not names or not WRITES.search(command):
            return False
        return not all(name.startswith("fail") for name in names)
    return False


def main() -> None:
    event = json.load(sys.stdin)
    if tripped(event):
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": (
                        "Architect tripwire: this writes the phase's source in a scratch clone, "
                        "which is a reference build. Spikes answer one question in a few lines; "
                        "stub files belong in a clone named fail*."
                    ),
                }
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
