#!/bin/bash
# Stop the `fin web serve` job and remove it. The log in data/logs/ is kept.
set -euo pipefail

LABEL="local.finances.web"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [[ -f "$PLIST" ]]; then
    rm "$PLIST"
    echo "Removed the web server job."
else
    echo "No web server job was installed."
fi
