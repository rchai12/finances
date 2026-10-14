#!/bin/bash
# Install the pre-commit hook, which checks lint and format before each commit.
#
#   scripts/install-git-hooks.sh
#
# Installing again replaces our own hook. A pre-commit hook that is not ours is left alone.
# Remove the hook with scripts/uninstall-git-hooks.sh.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS="$REPO/.git/hooks"
TARGET="$HOOKS/pre-commit"
MARK="# finances pre-commit hook"

if [[ ! -d "$HOOKS" ]]; then
    echo "Error: no .git/hooks folder; run this inside the repository" >&2
    exit 1
fi
if [[ -e "$TARGET" ]] && ! grep -q "^$MARK" "$TARGET"; then
    echo "Error: another pre-commit hook is already installed; remove it first" >&2
    exit 1
fi

cp "$REPO/scripts/git-hooks/pre-commit" "$TARGET"
chmod +x "$TARGET"
echo "Installed the pre-commit hook: lint and format are checked before each commit."
