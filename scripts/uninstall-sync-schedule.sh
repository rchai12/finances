#!/bin/bash
# Stop the daily `fin sync run` job and remove it. The log in data/logs/ is kept.
set -euo pipefail

LABEL="local.finances.sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [[ -f "$PLIST" ]]; then
    rm "$PLIST"
    echo "Removed the daily sync job."
else
    echo "No daily sync job was installed."
fi
