import sys

from sqlalchemy.exc import SQLAlchemyError

from finances.config import Settings, mask_url
from finances.db.migrate import current_revision, head_revision

Check = tuple[str, bool, str]


def run_checks(settings: Settings) -> list[Check]:
    return [
        _python_version(),
        _environment(settings),
        _data_dir(settings),
        _database_url(settings),
        _database_schema(settings),
    ]


def _python_version() -> Check:
    version = sys.version_info
    detail = f"{version.major}.{version.minor}.{version.micro}"
    ok = version >= (3, 11)
    if not ok:
        detail = f"{detail} FAIL"
    return ("Python version", ok, detail)


def _environment(settings: Settings) -> Check:
    return ("Environment", True, settings.environment)


def _data_dir(settings: Settings) -> Check:
    path = settings.data_dir.resolve()
    probe = path / ".fin_write_probe"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError:
        return ("Data dir", False, f"{path} FAIL")
    return ("Data dir", True, f"{path} OK")


def _database_url(settings: Settings) -> Check:
    return ("Database URL", True, mask_url(settings.effective_database_url))


def _database_schema(settings: Settings) -> Check:
    """Say whether the database is at the newest migration."""
    try:
        current = current_revision(settings.effective_database_url)
    except ValueError:
        # Database is not SQLite
        return ("Database schema", False, "unsupported database FAIL")
    except (OSError, SQLAlchemyError):
        # Cannot open database
        return ("Database schema", False, "cannot open database FAIL")

    head = head_revision()

    if current == head:
        return ("Database schema", True, f"{current} OK")
    else:
        # Format "none" instead of "None" for the first revision
        current_display = current if current is not None else "none"
        return ("Database schema", False, f"{current_display} -> {head} FAIL (run: fin db upgrade)")
