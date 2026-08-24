from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    app_env: str
    app_debug: bool
    database_url: str
    log_level: str
    log_dir: Path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        app_name=os.getenv("APP_NAME", "J.A. Finance"),
        app_env=os.getenv("APP_ENV", "development"),
        app_debug=_as_bool(os.getenv("APP_DEBUG", "false")),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./ja_finance.db"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_dir=PROJECT_ROOT / os.getenv("LOG_DIR", "logs"),
    )

