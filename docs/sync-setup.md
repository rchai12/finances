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

From the repository root:

```
scripts/install-sync-schedule.sh              # daily at 07:00
scripts/install-sync-schedule.sh 6 30         # or another time
scripts/install-sync-schedule.sh 7 0 --now    # install, then run once straight away to test
```

The script writes a `launchd` job (`~/Library/LaunchAgents/local.finances.sync.plist`) that runs `.venv/bin/fin sync run` as you, inside your login session, so it can read the Keychain. It finds the repository's paths by itself, so the same command works on any Mac (see "Moving to another Mac" below). Running it again replaces the earlier job.

- The Mac must be on and you logged in. If it is asleep at the set time, the run happens when it wakes.
- Output goes to `data/logs/sync.log`, which is never committed. It holds the same table `fin sync run` prints: account names, counts, and drift.
- To stop it: `scripts/uninstall-sync-schedule.sh`.
- To see whether it ran: `launchctl print gui/$(id -u)/local.finances.sync | grep -E "runs =|last exit code"`.

The agent cannot trigger a sync.

## Moving to another Mac

For example, to the Mac Studio. What lives where:

| Thing | Where | Moves with the repository? |
|---|---|---|
| The code | the Git repository | yes |
| The database (accounts, transactions, statements, mappings) | `data/finances.db` | no: `data/` is never committed |
| Real statements | `data/samples/` | no |
| SimpleFIN access, one entry per person | the macOS Keychain | no, and it should not be copied |
| The daily job | `~/Library/LaunchAgents/local.finances.sync.plist` | no: the script writes it |

On the new Mac, from the repository root after cloning it:

1. Install the project:

   ```
   python3 -m venv .venv
   .venv/bin/python -m pip install -e ".[dev]"
   ```

2. Bring the data over, one of two ways:
   - **Copy it:** copy `data/finances.db` (and `data/samples/` if you want the PDFs there too) from the old Mac, over a private connection or a drive you control, never through a cloud folder or email. Your accounts and mappings come with it; skip step 4.
   - **Start fresh:** leave `data/` empty. Steps 3 to 5 rebuild it.
3. Bring the database up to date (this creates it when it does not exist):

   ```
   .venv/bin/fin db upgrade
   ```

4. If you started fresh: add the accounts with `fin accounts add` (same names and last four digits as before), and import the statements with `fin import folder data/samples`.
5. Link each person again, each at the keyboard with a **new** setup token from their own SimpleFIN account (step 1 above). Keychain entries are never copied between machines.
6. If you started fresh, map the accounts again (step 2 above). If you copied the database, the mappings are already there; check with `fin sync status`.
7. Test, then schedule:

   ```
   .venv/bin/fin sync run
   scripts/install-sync-schedule.sh 7 0 --now
   ```

Then retire the old Mac:

- Run `scripts/uninstall-sync-schedule.sh` there, so the two machines do not both sync.
- Run `.venv/bin/fin sync unlink --link <name>` there for each person.
- On SimpleFIN's site, each person deletes the app connection that belonged to the old Mac. Its access stays valid until it is deleted, even after `unlink`.

