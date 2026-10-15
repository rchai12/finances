#!/bin/bash
# Stop the daily `fin backup run` job and remove it. The backups and the log are kept.
set -euo pipefail

LABEL="local.finances.backup"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [[ -f "$PLIST" ]]; then
    rm "$PLIST"
    echo "Removed the daily backup job."
else
    echo "No daily backup job was installed."
fi
