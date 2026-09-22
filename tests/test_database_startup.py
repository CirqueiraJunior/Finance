import sqlite3

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine

from app.core.config import PROJECT_ROOT, Settings, get_settings, resolve_database_url
from app.database.session import get_engine
from app.database.startup import (
    DatabaseStartupError, EXPECTED_SCHEMA_REVISION, effective_sqlite_path,
    validate_database_startup,
)


def test_relative_sqlite_url_is_independent_from_current_working_directory(
    tmp_path, monkeypatch
):
    alternate_cwd = tmp_path / "outside-project"
    alternate_cwd.mkdir()
    unexpected_database = alternate_cwd / "ja_finance.db"
    monkeypatch.chdir(alternate_cwd)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./ja_finance.db")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert effective_sqlite_path(settings.database_url) == (
            PROJECT_ROOT / "ja_finance.db"
        ).resolve()
        assert not unexpected_database.exists()
    finally:
        get_settings.cache_clear()


def test_postgresql_url_is_not_changed():
    url = "postgresql+psycopg://user:password@localhost:5432/finance"
    assert resolve_database_url(url, base_dir=PROJECT_ROOT) == url


def test_absolute_sqlite_url_is_not_changed(tmp_path):
    database = (tmp_path / "absolute.db").resolve()
    url = f"sqlite:///{database.as_posix()}"
    assert resolve_database_url(url, base_dir=PROJECT_ROOT) == url


def test_startup_missing_database_does_not_create_file(tmp_path):
    database = tmp_path / "missing.db"
    settings = Settings(
        "J.A. Finance", "test", False,
        f"sqlite:///{database.as_posix()}", "INFO", tmp_path / "logs",
    )
    engine = create_engine(settings.database_url)
    with pytest.raises(DatabaseStartupError) as captured:
        validate_database_startup(settings, engine)
    message = str(captured.value)
    assert str(database) in message
    assert "python -m alembic upgrade head" in message
    assert not database.exists()
    engine.dispose()


def test_startup_empty_database_reports_missing_migrations(tmp_path):
    database = tmp_path / "empty.db"
    sqlite3.connect(database).close()
    settings = Settings(
        "J.A. Finance", "test", False,
        f"sqlite:///{database.as_posix()}", "INFO", tmp_path / "logs",
    )
    engine = create_engine(settings.database_url)
    with pytest.raises(DatabaseStartupError, match="sem controle de migrations"):
        validate_database_startup(settings, engine)
    engine.dispose()


def test_current_schema_is_ready_after_migration_in_isolated_sqlite(tmp_path, monkeypatch):
    database = tmp_path / "startup-current.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database.as_posix()}")
    get_settings.cache_clear()
    try:
        command.upgrade(Config("alembic.ini"), "head")
        settings = get_settings()
        engine = create_engine(settings.database_url)
        state = validate_database_startup(settings, engine)
        assert state.engine_name == "SQLite"
        assert state.database_path == database.resolve()
        assert state.migration_revision == EXPECTED_SCHEMA_REVISION
        engine.dispose()
    finally:
        get_settings.cache_clear()
