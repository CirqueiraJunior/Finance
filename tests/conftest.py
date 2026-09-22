import os

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.database.base import Base
from app import models  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    event.listen(
        engine,
        "connect",
        lambda connection, _record: connection.execute("PRAGMA foreign_keys=ON"),
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture
def isolated_app_database(tmp_path, monkeypatch):
    """Isola testes que instanciam MainWindow do banco persistente da aplica??o."""
    from app.core.config import get_settings
    from app.database.session import get_engine, get_session_factory

    database_path = tmp_path / "finance_test.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"

    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()

    monkeypatch.setenv("DATABASE_URL", database_url)

    engine = get_engine()
    Base.metadata.create_all(engine)

    try:
        yield database_url
    finally:
        get_session_factory.cache_clear()
        get_engine.cache_clear()
        get_settings.cache_clear()
        engine.dispose()
