#!/bin/bash
# Remove the pre-commit hook installed by scripts/install-git-hooks.sh. Another hook is left.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS="$REPO/.git/hooks"
TARGET="$HOOKS/pre-commit"
MARK="# finances pre-commit hook"

if [[ ! -d "$HOOKS" ]]; then
    echo "Error: no .git/hooks folder; run this inside the repository" >&2
    exit 1
fi
if [[ ! -e "$TARGET" ]]; then
    echo "No pre-commit hook was installed."
    exit 0
fi
if ! grep -q "^$MARK" "$TARGET"; then
    echo "Error: the pre-commit hook is not ours; it was left in place" >&2
    exit 1
fi

rm "$TARGET"
echo "Removed the pre-commit hook."
