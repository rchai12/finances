"""Today's date as the household reads it: the local date of this machine.

Every page and command that shows "today", the current month, or days since something reads
the date here. Callers use `clock.today()` (not `from finances.clock import today`), so a test
can replace `finances.clock.today`. Stored timestamps are UTC and do not come from here.
"""

from datetime import date


def today() -> date:
    return date.today()
