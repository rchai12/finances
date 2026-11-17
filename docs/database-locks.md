# SQLite lock waiting

Set `FIN_DB_BUSY_TIMEOUT_MS` to an integer from 0 through 120000 milliseconds. The default is 30000 (30 seconds); 0 requests no lock wait and 120000 is the maximum. Settings are cached, so restart the process after changing the setting; newly constructed engines use the cached settings until cleared or restarted.

Each SQLite connection receives this native driver busy timeout, including in-memory, read-only and explicit URL connections. The setting takes precedence over a timeout in the URL. The timeout bounds SQLite's busy handling, not the entire operation: connecting, queries and application work take additional time. SQLite can refuse some lock upgrades or deadlocks immediately.

When waiting is exhausted the existing SQLAlchemy `OperationalError` propagates, and the transaction is rolled back. The app does not automatically retry or replay the transaction. A later transaction may succeed after the lock is released. This setting does not make concurrent restores safe or allow multiple writers to write at once.
