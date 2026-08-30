from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_database_url(database_url: str, *, base_dir: Path = PROJECT_ROOT) -> str:
    """Resolve SQLite relativo contra a raiz da aplicação, nunca contra o CWD."""
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return database_url
    database = url.database
    if not database or database == ":memory:":
        return database_url
    database_path = Path(database)
    if database_path.is_absolute():
        return database_url
    absolute_path = (base_dir / database_path).resolve()
    return url.set(database=absolute_path.as_posix()).render_as_string(
        hide_password=False
    )


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    app_env: str
    app_debug: bool
    database_url: str
    log_level: str
    log_dir: Path
    api_url: str = ""
    api_timeout_seconds: float = 10.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(ENV_FILE)
    database_url = resolve_database_url(
        os.getenv("DATABASE_URL", "sqlite:///./ja_finance.db"),
        base_dir=ENV_FILE.parent,
    )
    return Settings(
        app_name=os.getenv("APP_NAME", "Finance"),
        app_env=os.getenv("APP_ENV", "development"),
        app_debug=_as_bool(os.getenv("APP_DEBUG", "false")),
        database_url=database_url,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_dir=PROJECT_ROOT / os.getenv("LOG_DIR", "logs"),
        api_url=os.getenv("FINANCE_API_URL", "").strip().rstrip("/"),
        api_timeout_seconds=float(os.getenv("FINANCE_API_TIMEOUT_SECONDS", "10")),
    )
