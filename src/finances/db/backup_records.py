from finances.db.engine import get_engine, session_scope
from finances.db.migrate import current_revision, head_revision
from finances.db.repositories.audit import record_change
from finances.domain.audit import PERSON


def _note(url: str, action: str, *, before: str | None = None, after: str | None = None) -> bool:
    if current_revision(url) != head_revision():
        return False
    engine = get_engine(url)
    try:
        with session_scope(engine) as session:
            record_change(
                session,
                action=action,
                kind="backup",
                record_id=None,
                before=before,
                after=after,
                who=PERSON,
            )
    finally:
        engine.dispose()
    return True


def note_backup_deleted(url: str, name: str) -> bool:
    return _note(url, "backup_deleted", before=name)


def note_backup_restored(url: str, name: str) -> bool:
    return _note(url, "backup_restored", after=name)
