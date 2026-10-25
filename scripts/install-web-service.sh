#!/bin/bash
# Keep `fin web serve` running as the logged-in user, with launchd: it starts at login and
# again whenever it stops.
#
#   scripts/install-web-service.sh
#
# The job runs inside the user's login session, so it can read the web password's hash in the
# Keychain. Set the password first (fin web password); without one the server refuses to start.
# Output goes to data/logs/web.log (data/ is never committed); each start writes a line with
# the local date and time. Installing again replaces the earlier job. Remove it with
# scripts/uninstall-web-service.sh.
set -euo pipefail

LABEL="local.finances.web"
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
    <string>printf '== %s\\n' "\$(date '+%Y-%m-%d %H:%M:%S %Z')"; exec "$FIN" web serve</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$REPO</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>StandardOutPath</key>
  <string>$LOGS/web.log</string>
  <key>StandardErrorPath</key>
  <string>$LOGS/web.log</string>
</dict>
</plist>
PLIST
plutil -lint "$PLIST" >/dev/null

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "The web server now starts at login and again whenever it stops (log: $LOGS/web.log)"
