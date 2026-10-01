import sys

from finances.config import Settings, mask_url

Check = tuple[str, bool, str]


def run_checks(settings: Settings) -> list[Check]:
    return [
        _python_version(),
        _environment(settings),
        _data_dir(settings),
        _database_url(settings),
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
