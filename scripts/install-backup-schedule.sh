#!/bin/bash
# Run `fin backup run` every day at a set time, as the logged-in user, with launchd.
#
#   scripts/install-backup-schedule.sh              daily at 02:00
#   scripts/install-backup-schedule.sh 3 30         daily at 03:30
#   scripts/install-backup-schedule.sh 2 0 --now    install, then run once straight away
#
# Backups go to FIN_BACKUP_DIR (data/backups unless set; see docs/backups.md). Paths are worked
# out from where this repository is, so the same command works on any Mac. Output goes to
# data/logs/backup.log (data/ is never committed). Each run starts with a line giving the
# local date and time.
# Installing again replaces the earlier job.
# Remove it with scripts/uninstall-backup-schedule.sh.
set -euo pipefail

LABEL="local.finances.backup"
HOUR="${1:-2}"
MINUTE="${2:-0}"
RUN_NOW="${3:-}"

if ! [[ "$HOUR" =~ ^[0-9]{1,2}$ ]] || ((10#$HOUR > 23)); then
    echo "Error: the hour must be 0 to 23" >&2
    exit 1
fi
if ! [[ "$MINUTE" =~ ^[0-9]{1,2}$ ]] || ((10#$MINUTE > 59)); then
    echo "Error: the minute must be 0 to 59" >&2
    exit 1
fi
if [[ -n "$RUN_NOW" && "$RUN_NOW" != "--now" ]]; then
    echo "Error: the only third argument is --now" >&2
    exit 1
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIN="$REPO/.venv/bin/fin"
LOGS="$REPO/data/logs"
AGENTS="$HOME/Library/LaunchAgents"
PLIST="$AGENTS/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if [[ ! -x "$FIN" ]]; then
    echo "Error: $FIN not found; install the project first" >&2
    exit 1
fi
mkdir -p "$LOGS" "$AGENTS"

cat >"$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>printf '== %s\\n' "\$(date '+%Y-%m-%d %H:%M:%S %Z')"; exec "$FIN" backup run</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$REPO</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>$((10#$HOUR))</integer>
    <key>Minute</key>
    <integer>$((10#$MINUTE))</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOGS/backup.log</string>
  <key>StandardErrorPath</key>
  <string>$LOGS/backup.log</string>
</dict>
</plist>
PLIST
plutil -lint "$PLIST" >/dev/null

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
printf 'Scheduled fin backup run daily at %02d:%02d (log: %s)\n' "$((10#$HOUR))" "$((10#$MINUTE))" "$LOGS/backup.log"

if [[ "$RUN_NOW" == "--now" ]]; then
    launchctl kickstart "$DOMAIN/$LABEL"
    echo "Started one run now; see the log when it finishes."
fi
