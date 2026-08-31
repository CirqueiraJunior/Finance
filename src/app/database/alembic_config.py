from __future__ import annotations

from alembic.config import Config


def set_alembic_database_url(config: Config, database_url: str) -> None:
    """Pass a URL through ConfigParser without changing its SQLAlchemy value."""
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
