# Setting up the daily feed

For the household, after Phase 17c is built and verified. Every command runs from the repository root.

## 1. Link each person's SimpleFIN subscription

Each person does this for their own subscription, on this machine, at the keyboard.

1. Sign in at SimpleFIN Bridge and create a new setup token for an app. Copy it.
2. Run, with your own link name (lowercase letters, digits, or hyphens):

   ```
   .venv/bin/fin sync link --link richard
   ```

   Paste the token at the hidden prompt. It is used once and never stored; the access it gives is kept in the macOS Keychain under `finances-simplefin`.

Never paste a setup token anywhere else: not in a chat, an AI tool, a file, or a note. If one leaks, delete that app connection on SimpleFIN's site.

## 2. Map SimpleFIN accounts to the app's accounts

```
.venv/bin/fin sync accounts --link richard
.venv/bin/fin sync map --link richard --account "Citi Costco" --feed-account <SimpleFIN account id>
```

The account in the app must exist first (`fin accounts list`; add it with `fin accounts add`). Repeat for each account and each link. A link only says whose SimpleFIN subscription the account comes through; who owns the account (one of you, or joint) is set separately once Phase 21 is built.

## 3. Pull

```
.venv/bin/fin sync run
.venv/bin/fin sync status
```

`Drift` should be `$0.00` from the second run on. A card whose drift is about twice the change in its balance means SimpleFIN gives that card's balance the opposite sign; tell the architect.

## 4. Run it every morning

macOS runs a user job with `launchd`. Save this as `~/Library/LaunchAgents/local.finances.sync.plist`, with the two paths changed to this repository:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>local.finances.sync</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/YOU/Desktop/Projects/finances/.venv/bin/fin</string>
    <string>sync</string>
    <string>run</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/YOU/Desktop/Projects/finances</string>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/tmp/finances-sync.log</string>
  <key>StandardErrorPath</key><string>/tmp/finances-sync.log</string>
</dict>
</plist>
```

Then load it once:

```
launchctl load ~/Library/LaunchAgents/local.finances.sync.plist
```

The job runs as you, so it can read your Keychain while you are logged in. The log holds the same table `fin sync run` prints, which includes account names and counts; delete it if you do not want that kept. The agent cannot trigger a sync.
