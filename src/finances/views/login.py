"""The login page's lock message."""

from datetime import datetime

LOCKED = "Too many wrong passwords: the login is locked until {time}."


def lock_text(until: datetime) -> str:
    local = until.astimezone()
    when = f"{local.hour}:{local.minute:02d} on {local.day} {local.strftime('%B')}"
    return LOCKED.format(time=when)
