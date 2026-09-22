from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings


def test_existing_user_is_not_forced_after_migration(tmp_path, monkeypatch):
    database = tmp_path / "existing-user.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database.as_posix()}")
    get_settings.cache_clear()
    try:
        config = Config("alembic.ini")
        command.upgrade(config, "20260907_17")
        engine = create_engine(f"sqlite:///{database.as_posix()}")
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO users (nome, email, username, password_hash, perfil, ativo) "
                "VALUES ('Existente', 'existing@example.com', 'existing', 'hash', "
                "'ADMINISTRADOR', 1)"
            ))
        engine.dispose()

        command.upgrade(config, "20260909_18")
        engine = create_engine(f"sqlite:///{database.as_posix()}")
        with engine.connect() as connection:
            assert "must_change_password" in {
                column["name"] for column in inspect(connection).get_columns("users")
            }
            assert connection.scalar(text(
                "SELECT must_change_password FROM users WHERE username = 'existing'"
            )) == 0
        engine.dispose()
    finally:
        get_settings.cache_clear()


def test_bootstrap_administrator_is_not_forced_to_change_password(tmp_path, monkeypatch):
    from app.database.base import Base
    from finance_server.config import ServerSettings
    from finance_server.models import User
    import finance_server.bootstrap as bootstrap

    database = tmp_path / "bootstrap.db"
    url = f"sqlite:///{database.as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setattr(bootstrap, "get_server_settings", lambda: ServerSettings(url, "s" * 64))
    values = {
        "BOOTSTRAP_ADMIN_NAME": "Administrador",
        "BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
        "BOOTSTRAP_ADMIN_USERNAME": "admin",
        "BOOTSTRAP_ADMIN_PASSWORD": "Finance1",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    assert bootstrap.main() == 0
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT must_change_password FROM users WHERE username = 'admin'"
        )) == 0
    engine.dispose()
