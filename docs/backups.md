# Backups

Everything the household has entered or the app has worked out (accounts, transactions, categories, rules, transfers, mappings) lives in one file, `data/finances.db`. Back it up.

## Making a backup

```
.venv/bin/fin backup run
```

It copies the database with SQLite's own backup, which is safe while the app is running, checks the copy (it opens, its schema is one this app knows, and it can count the accounts and transactions), and only then gives it its name, `finances-YYYYMMDD-HHMMSS.db` (the time in UTC). It keeps the newest 14 and deletes older ones; files with other names are never touched.

`.venv/bin/fin backup list` shows the backups, newest first.

## On the web

The **Backups** page (`fin web serve`, then Backups in the menu) does the same: **Back up now**, the list with each file's size, **Delete** (after a confirmation page), and **Restore** (after typing the backup's name). The web restore pauses the site's other requests while it works, so the server need not be stopped. Backups are not downloaded through the browser: a full copy in the downloads folder, often synced to the cloud, would break the rule below.

## Where backups go

`data/backups/` unless `FIN_BACKUP_DIR` says otherwise; `FIN_BACKUP_KEEP` sets how many to keep. Both can go in `.env`.

A backup on the same disk protects against mistakes, not against losing the disk. Point `FIN_BACKUP_DIR` at a drive you control (an external disk, preferably encrypted) for that. A backup holds every transaction in plain form, like the database itself, so keep it off cloud folders and email, for the same reason the database is (see `docs/architecture.md`, Privacy boundary). The app never copies anything off the machine.

## Every day

```
scripts/install-backup-schedule.sh              # daily at 02:00
scripts/install-backup-schedule.sh 3 30         # or another time
scripts/install-backup-schedule.sh 2 0 --now    # install, then run once straight away to test
```

Output goes to `data/logs/backup.log`. To stop it: `scripts/uninstall-backup-schedule.sh`. The Mac must be on and you logged in; a run missed while asleep happens when it wakes.

## Restoring

From the terminal, stop `fin web serve` first. Then:

```
.venv/bin/fin backup restore data/backups/finances-20261015-020000.db
```

It checks the backup, asks before replacing anything, keeps the database it replaces as `finances-YYYYMMDD-HHMMSS-before-restore.db` in the backup folder (these are never deleted for you), and copies the backup in. A backup from an older version of the app is restored as it is; run `.venv/bin/fin db upgrade` afterwards, as the command says.

On a new Mac, restoring a backup is another way to bring the data over (see `docs/sync-setup.md`, "Moving to another Mac"): install the project, restore, then `fin db upgrade`. SimpleFIN links are not in the database and must be made again.
