from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FIN_", env_file=".env", extra="ignore")

    environment: Literal["local", "cloud"] = "local"
    data_dir: Path = Path("data")
    database_url: str | None = None
    log_level: str = "INFO"

    @property
    def effective_database_url(self) -> str:
        if self.database_url is not None:
            return self.database_url
        db_path = (self.data_dir / "finances.db").resolve().as_posix()
        return f"sqlite:///{db_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def mask_url(url: str) -> str:
    """Replace a password in a database URL with ***."""
    parts = urlsplit(url)
    if parts.password is None:
        return url
    username = parts.username or ""
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    netloc = f"{username}:***@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
