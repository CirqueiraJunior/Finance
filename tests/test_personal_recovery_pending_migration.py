from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings


def test_pending_key_migration_preserves_users_with_false_default(tmp_path, monkeypatch):
    database = tmp_path / "pending-key.db"
    url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        config = Config("alembic.ini")
        command.upgrade(config, "20260910_20")
        engine = create_engine(url)
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO users (nome, email, username, password_hash, perfil, ativo, "
                "must_change_password) VALUES ('Existente', 'existing@example.com', "
                "'existing', 'hash', 'ADMINISTRADOR', 1, 0)"
            ))
        engine.dispose()

        command.upgrade(config, "20260910_21")
        engine = create_engine(url)
        with engine.connect() as connection:
            columns = {column["name"] for column in inspect(connection).get_columns("users")}
            assert "personal_recovery_key_pending" in columns
            assert connection.scalar(text(
                "SELECT personal_recovery_key_pending FROM users WHERE username='existing'"
            )) == 0
        engine.dispose()
    finally:
        get_settings.cache_clear()
